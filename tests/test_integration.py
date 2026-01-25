"""
Integration tests for the Champion Draft Assist Tool.

Tests that verify the main components work together correctly.
"""

import pytest
from datetime import datetime
from src.models import (
    Champion, Role, ChampionTag, DraftState, ChampionStats,
    UserPreferences, ScoreWeights
)
from src.scoring.scorer import StandardScorer
from src.data.manager import SimpleCache


def test_standard_scorer_integration():
    """Test that StandardScorer works with real data models."""
    # Create test champion and stats
    champion = Champion(
        id="ahri",
        name="Ahri", 
        role=Role.MIDDLE,
        tags=[ChampionTag.MAGE, ChampionTag.ASSASSIN]
    )
    
    stats = ChampionStats(
        champion_id="ahri",
        role=Role.MIDDLE,
        win_rate=0.52,
        pick_rate=0.15,
        ban_rate=0.08,
        patch="14.1",
        rank_tier="GOLD"
    )
    
    # Create scorer and test meta score calculation
    scorer = StandardScorer()
    meta_score = scorer.calculate_meta_score(champion, stats)
    
    # Score should be normalized to 0-100 range
    assert 0 <= meta_score <= 100
    assert isinstance(meta_score, float)


def test_simple_cache_functionality():
    """Test that SimpleCache works correctly."""
    cache = SimpleCache()
    
    # Test setting and getting data
    test_data = {"champion": "ahri", "score": 85.0}
    cache.set("test_key", test_data, 3600)  # 1 hour TTL
    
    retrieved_data = cache.get("test_key")
    assert retrieved_data == test_data
    
    # Test non-existent key
    assert cache.get("non_existent") is None
    
    # Test cache clearing
    cache.clear()
    assert cache.get("test_key") is None


def test_draft_state_with_multiple_champions():
    """Test DraftState with multiple champions."""
    ahri = Champion("ahri", "Ahri", Role.MIDDLE, [ChampionTag.MAGE])
    yasuo = Champion("yasuo", "Yasuo", Role.MIDDLE, [ChampionTag.ASSASSIN])
    zed = Champion("zed", "Zed", Role.MIDDLE, [ChampionTag.ASSASSIN])
    jinx = Champion("jinx", "Jinx", Role.BOTTOM, [ChampionTag.MARKSMAN])
    
    draft_state = DraftState(
        role=Role.MIDDLE,
        ally_champions=[jinx],
        enemy_champions=[yasuo, zed],
        banned_champions=[ahri],
        patch="14.1"
    )
    
    assert len(draft_state.ally_champions) == 1
    assert len(draft_state.enemy_champions) == 2
    assert len(draft_state.banned_champions) == 1
    assert draft_state.ally_champions[0].name == "Jinx"
    assert draft_state.enemy_champions[0].name == "Yasuo"
    assert draft_state.enemy_champions[1].name == "Zed"


def test_score_weights_calculation():
    """Test that score weights sum to 1.0 for proper weighting."""
    weights = ScoreWeights()
    total = weights.meta + weights.synergy + weights.counter
    
    # Should sum to 1.0 (allowing for floating point precision)
    assert abs(total - 1.0) < 0.001
    
    # Individual weights should be positive
    assert weights.meta > 0
    assert weights.synergy > 0
    assert weights.counter > 0


def test_scorer_final_score_calculation():
    """Test final score calculation with confidence bonus."""
    scorer = StandardScorer()
    weights = ScoreWeights()
    
    meta_score = 70.0
    synergy_score = 60.0
    counter_score = 80.0
    confidence_bonus = 15.0
    
    # Calculate expected score manually
    expected_base = (
        meta_score * weights.meta +
        synergy_score * weights.synergy +
        counter_score * weights.counter
    )
    expected_final = expected_base + confidence_bonus
    
    # Test scorer calculation
    actual_score = scorer.calculate_final_score(
        meta_score, synergy_score, counter_score, weights, confidence_bonus
    )
    
    assert abs(actual_score - expected_final) < 0.001