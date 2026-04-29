"""
Tests for champion scoring algorithms.

Includes both unit tests and property-based tests for scoring components.
"""

import pytest
from hypothesis import given, strategies as st
from src.models import (
    Champion, Role, ChampionTag, ChampionStats, ScoreWeights,
    SynergyData, CounterData
)
from src.scoring.scorer import StandardScorer


class TestStandardScorer:
    """Test cases for StandardScorer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = StandardScorer()
        self.test_champion = Champion(
            id="ahri",
            name="Ahri",
            role=Role.MIDDLE,
            tags=[ChampionTag.MAGE, ChampionTag.ASSASSIN]
        )
        self.test_stats = ChampionStats(
            champion_id="ahri",
            role=Role.MIDDLE,
            win_rate=0.52,
            pick_rate=0.15,
            ban_rate=0.08,
            patch="14.1",
            rank_tier="GOLD"
        )
    
    def test_meta_score_calculation(self):
        """Test meta score calculation with known values."""
        score = self.scorer.calculate_meta_score(self.test_champion, self.test_stats)
        
        # Score should be normalized to 0-100 range
        assert 0 <= score <= 100
        assert isinstance(score, float)
        
        # With win rate 0.52, should be above 50 (middle of range)
        assert score > 50
    
    def test_meta_score_edge_cases(self):
        """Test meta score calculation with edge cases."""
        # Test with very low win rate
        low_stats = ChampionStats("test", Role.MIDDLE, 0.30, 0.1, 0.05, "14.1", "GOLD")
        low_score = self.scorer.calculate_meta_score(self.test_champion, low_stats)
        assert 0 <= low_score <= 100
        
        # Test with very high win rate
        high_stats = ChampionStats("test", Role.MIDDLE, 0.70, 0.1, 0.05, "14.1", "GOLD")
        high_score = self.scorer.calculate_meta_score(self.test_champion, high_stats)
        assert 0 <= high_score <= 100
        
        # High win rate should give higher score than low win rate
        assert high_score > low_score
    
    def test_synergy_score_no_allies(self):
        """Test synergy score calculation with no allied champions."""
        score = self.scorer.calculate_synergy_score(self.test_champion, [], [])
        assert score == 50.0  # Should return neutral score
    
    def test_counter_score_no_enemies(self):
        """Test counter score calculation with no enemy champions."""
        score = self.scorer.calculate_counter_score(self.test_champion, [], [])
        assert score == 50.0  # Should return neutral score
    
    def test_final_score_without_bonus(self):
        """Test final score calculation without confidence bonus."""
        weights = ScoreWeights()
        meta_score = 70.0
        synergy_score = 60.0
        counter_score = 80.0
        
        expected_score = (
            meta_score * weights.meta +
            synergy_score * weights.synergy +
            counter_score * weights.counter
        )
        
        actual_score = self.scorer.calculate_final_score(
            meta_score, synergy_score, counter_score, weights, 0.0
        )
        
        assert abs(actual_score - expected_score) < 0.001
    
    def test_final_score_with_bonus(self):
        """Test final score calculation with confidence bonus."""
        weights = ScoreWeights()
        meta_score = 70.0
        synergy_score = 60.0
        counter_score = 80.0
        confidence_bonus = 15.0
        
        expected_score = (
            meta_score * weights.meta +
            synergy_score * weights.synergy +
            counter_score * weights.counter
        ) + confidence_bonus
        
        actual_score = self.scorer.calculate_final_score(
            meta_score, synergy_score, counter_score, weights, confidence_bonus
        )
        
        assert abs(actual_score - expected_score) < 0.001
    
    def test_invalid_weights_sum(self):
        """Test that invalid weight sums raise ValueError."""
        invalid_weights = ScoreWeights(meta=0.5, synergy=0.3, counter=0.3)  # Sums to 1.1
        
        with pytest.raises(ValueError, match="Score weights must sum to 1.0"):
            self.scorer.calculate_final_score(70.0, 60.0, 80.0, invalid_weights, 0.0)


class TestScorerProperties:
    """Property-based tests for scorer algorithms."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = StandardScorer()
    
    @given(
        meta_score=st.floats(min_value=0.0, max_value=100.0),
        synergy_score=st.floats(min_value=0.0, max_value=100.0),
        counter_score=st.floats(min_value=0.0, max_value=100.0),
        confidence_bonus=st.floats(min_value=0.0, max_value=50.0)
    )
    def test_property_weighted_score_calculation(
        self, meta_score, synergy_score, counter_score, confidence_bonus
    ):
        """
        Property 5: Weighted Score Calculation
        For any mid lane champion with meta, synergy, and counter component scores,
        the final score should equal (Meta × 0.4) + (Synergy × 0.3) + (Counter × 0.3)
        **Validates: Requirements 8.1**
        **Feature: champion-suggestion-overlay, Property 5: Weighted Score Calculation**
        """
        weights = ScoreWeights()  # Default weights: meta=0.4, synergy=0.3, counter=0.3
        
        # Calculate expected score manually
        expected_base_score = (
            meta_score * weights.meta +
            synergy_score * weights.synergy +
            counter_score * weights.counter
        )
        expected_final_score = expected_base_score + confidence_bonus
        
        # Calculate actual score using scorer
        actual_score = self.scorer.calculate_final_score(
            meta_score, synergy_score, counter_score, weights, confidence_bonus
        )
        
        # Scores should match within floating point precision
        assert abs(actual_score - expected_final_score) < 0.001
        
        # Final score should be non-negative
        assert actual_score >= 0.0
        
        # If no confidence bonus, score should equal weighted sum
        if confidence_bonus == 0.0:
            assert abs(actual_score - expected_base_score) < 0.001
    
    @given(
        meta_score=st.floats(min_value=0.0, max_value=100.0),
        synergy_score=st.floats(min_value=0.0, max_value=100.0),
        counter_score=st.floats(min_value=0.0, max_value=100.0),
        meta_weight=st.floats(min_value=0.1, max_value=0.8),
        synergy_weight=st.floats(min_value=0.1, max_value=0.8),
    )
    def test_property_custom_weights_calculation(
        self, meta_score, synergy_score, counter_score, meta_weight, synergy_weight
    ):
        """
        Test weighted score calculation with custom weights that sum to 1.0.
        Ensures the weighted formula works correctly with any valid weight combination.
        """
        # Ensure weights sum to 1.0
        counter_weight = 1.0 - meta_weight - synergy_weight
        
        # Skip if counter weight would be invalid
        if counter_weight <= 0.0 or counter_weight >= 1.0:
            return
        
        custom_weights = ScoreWeights(
            meta=meta_weight,
            synergy=synergy_weight,
            counter=counter_weight
        )
        
        # Calculate expected score
        expected_score = (
            meta_score * meta_weight +
            synergy_score * synergy_weight +
            counter_score * counter_weight
        )
        
        # Calculate actual score
        actual_score = self.scorer.calculate_final_score(
            meta_score, synergy_score, counter_score, custom_weights, 0.0
        )
        
        # Scores should match within floating point precision
        assert abs(actual_score - expected_score) < 0.001
    
    @given(
        win_rate=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_property_meta_score_normalization(self, win_rate):
        """
        Test that meta score normalization always produces values in 0-100 range.
        """
        champion = Champion("test", "Test", Role.MIDDLE, [ChampionTag.MAGE])
        stats = ChampionStats("test", Role.MIDDLE, win_rate, 0.1, 0.05, "14.1", "GOLD")
        
        meta_score = self.scorer.calculate_meta_score(champion, stats)
        
        # Score should always be in 0-100 range
        assert 0.0 <= meta_score <= 100.0
        assert isinstance(meta_score, float)