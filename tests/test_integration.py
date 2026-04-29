"""
Integration tests for the Champion Draft Assist Tool.

Tests that verify the main components work together correctly.
"""

import pytest
import asyncio
from datetime import datetime
from src.models import (
    Champion, Role, ChampionTag, DraftState, ChampionStats,
    UserPreferences, ScoreWeights, MatchFilters
)
from src.scoring.scorer import StandardScorer
from src.data.manager import SimpleCache
from src.data.riot_api_client import RiotAPIClient
from src.engine import StandardSuggestionEngine


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


@pytest.mark.asyncio
async def test_end_to_end_recommendation_workflow():
    """
    Test complete workflow from API data to recommendations.
    
    Requirements: All - Test complete system integration
    """
    # Create mock API client with test API key
    api_client = RiotAPIClient(api_key="test_key")
    scorer = StandardScorer()
    engine = StandardSuggestionEngine(api_client, scorer)
    
    # Create test draft state
    yasuo = Champion("yasuo", "Yasuo", Role.MIDDLE, [ChampionTag.ASSASSIN])
    jinx = Champion("jinx", "Jinx", Role.BOTTOM, [ChampionTag.MARKSMAN])
    ahri = Champion("ahri", "Ahri", Role.MIDDLE, [ChampionTag.MAGE])
    
    draft_state = DraftState(
        role=Role.MIDDLE,
        ally_champions=[jinx],
        enemy_champions=[yasuo],
        banned_champions=[ahri],
        patch="14.1"
    )
    
    # Test user champion pool
    user_pool = ["zed", "orianna", "syndra"]
    
    # Use async context manager for API client
    async with api_client:
        # Generate recommendations
        result = await engine.generate_recommendations(draft_state, user_pool)
        
        # Verify result structure
        assert result is not None
        assert hasattr(result, 'champion_pool_recommendations')
        assert hasattr(result, 'overall_recommendations')
        assert hasattr(result, 'timestamp')
        
        # Verify recommendations are lists
        assert isinstance(result.champion_pool_recommendations, list)
        assert isinstance(result.overall_recommendations, list)
        
        # Verify we get up to 5 recommendations each (as per requirements 7.3, 7.4)
        assert len(result.champion_pool_recommendations) <= 5
        assert len(result.overall_recommendations) <= 5
        
        # Verify banned champions are excluded (requirement 3.3)
        all_recommended_ids = []
        for rec in result.champion_pool_recommendations + result.overall_recommendations:
            all_recommended_ids.append(rec.champion.id)
        
        assert "ahri" not in all_recommended_ids, "Banned champion should not appear in recommendations"
        
        # Verify champion pool recommendations only contain pool champions (requirement 2.2)
        for rec in result.champion_pool_recommendations:
            assert rec.champion.id in user_pool, f"Champion {rec.champion.id} not in user pool"
        
        # Verify each recommendation has required fields
        for rec in result.overall_recommendations:
            assert hasattr(rec, 'champion')
            assert hasattr(rec, 'score')
            assert hasattr(rec, 'explanations')
            assert hasattr(rec, 'score_breakdown')
            
            # Verify score is in valid range
            assert 0 <= rec.score <= 115, f"Score {rec.score} out of valid range"  # Max 100 + 15 bonus
            
            # Verify explanations (requirement 9.1: 2-4 explanations)
            assert 2 <= len(rec.explanations) <= 4
            assert all(isinstance(exp, str) for exp in rec.explanations)
            
            # Verify score breakdown has all components
            assert hasattr(rec.score_breakdown, 'meta_score')
            assert hasattr(rec.score_breakdown, 'synergy_score')
            assert hasattr(rec.score_breakdown, 'counter_score')


@pytest.mark.asyncio
async def test_api_data_integration():
    """
    Test API data fetching and caching functionality.
    
    Requirements: 1.1, 1.5 - API integration and caching
    """
    api_client = RiotAPIClient(api_key="test_key")
    
    async with api_client:
        # Test champion stats fetching
        stats = await api_client.fetch_champion_stats("14.1", Role.MIDDLE)
        
        assert isinstance(stats, list)
        assert len(stats) > 0
        
        # Verify stats structure
        for stat in stats:
            assert hasattr(stat, 'champion_id')
            assert hasattr(stat, 'role')
            assert hasattr(stat, 'win_rate')
            assert hasattr(stat, 'patch')
            assert stat.role == Role.MIDDLE
            assert stat.patch == "14.1"
            assert 0 <= stat.win_rate <= 1
        
        # Test caching - second call should use cache
        cached_stats = await api_client.fetch_champion_stats("14.1", Role.MIDDLE)
        assert len(cached_stats) == len(stats)
        
        # Test match data fetching
        filters = MatchFilters(patch="14.1", role=Role.MIDDLE)
        matches = await api_client.fetch_match_data(filters)
        
        assert isinstance(matches, list)
        assert len(matches) > 0
        
        # Verify match structure
        for match in matches:
            assert hasattr(match, 'match_id')
            assert hasattr(match, 'participants')
            assert hasattr(match, 'patch')
            assert match.patch == "14.1"
            assert len(match.participants) == 10  # 5v5 match


@pytest.mark.asyncio
async def test_recommendation_accuracy_known_scenarios():
    """
    Test recommendation accuracy with known scenarios.
    
    Requirements: All - Verify recommendation logic with predictable inputs
    """
    api_client = RiotAPIClient(api_key="test_key")
    scorer = StandardScorer()
    engine = StandardSuggestionEngine(api_client, scorer)
    
    async with api_client:
        # Scenario 1: Empty draft state should return meta-based recommendations
        empty_draft = DraftState(
            role=Role.MIDDLE,
            ally_champions=[],
            enemy_champions=[],
            banned_champions=[],
            patch="14.1"
        )
        
        result = await engine.generate_recommendations(empty_draft, ["yasuo", "zed"])
        
        assert len(result.overall_recommendations) > 0
        # In empty draft, recommendations should be primarily meta-based
        for rec in result.overall_recommendations:
            assert rec.score_breakdown.meta_score > 0
        
        # Scenario 2: Champion pool recommendations should have confidence bonus
        pool_recs = result.champion_pool_recommendations
        overall_recs = result.overall_recommendations
        
        # Find same champion in both lists (if exists)
        for pool_rec in pool_recs:
            for overall_rec in overall_recs:
                if pool_rec.champion.id == overall_rec.champion.id:
                    # Pool recommendation should have higher score due to confidence bonus
                    assert pool_rec.score > overall_rec.score
                    assert pool_rec.score_breakdown.confidence_bonus is not None
                    assert overall_rec.score_breakdown.confidence_bonus is None
        
        # Scenario 3: Banned champions should never appear
        banned_champion = Champion("syndra", "Syndra", Role.MIDDLE, [ChampionTag.MAGE])
        draft_with_bans = DraftState(
            role=Role.MIDDLE,
            ally_champions=[],
            enemy_champions=[],
            banned_champions=[banned_champion],
            patch="14.1"
        )
        
        result_with_bans = await engine.generate_recommendations(draft_with_bans, ["yasuo", "syndra"])
        
        # Verify banned champion doesn't appear in any recommendations
        all_recommended = result_with_bans.champion_pool_recommendations + result_with_bans.overall_recommendations
        for rec in all_recommended:
            assert rec.champion.id != "syndra", "Banned champion appeared in recommendations"


@pytest.mark.asyncio
async def test_user_data_persistence():
    """
    Test user data saving and loading functionality.
    
    Requirements: 2.4, 10.1, 10.2, 10.3 - User data persistence
    """
    api_client = RiotAPIClient(api_key="test_key")
    
    # Create test user data
    from src.models import UserData, UserPreferences, ScoreWeights
    
    test_user_data = UserData(
        champion_pool=["yasuo", "zed", "ahri"],
        preferences=UserPreferences(
            score_weights=ScoreWeights(meta=0.5, synergy=0.3, counter=0.2),
            confidence_bonus=20.0
        ),
        last_updated=datetime.now()
    )
    
    async with api_client:
        # Test saving user data
        await api_client.save_user_data(test_user_data)
        
        # Test loading user data
        loaded_data = await api_client.load_user_data()
        
        assert loaded_data is not None
        assert loaded_data.champion_pool == test_user_data.champion_pool
        assert loaded_data.preferences.confidence_bonus == test_user_data.preferences.confidence_bonus
        assert loaded_data.preferences.score_weights.meta == test_user_data.preferences.score_weights.meta
        assert loaded_data.preferences.score_weights.synergy == test_user_data.preferences.score_weights.synergy
        assert loaded_data.preferences.score_weights.counter == test_user_data.preferences.score_weights.counter


@pytest.mark.asyncio
async def test_error_handling_integration():
    """
    Test error handling across integrated components.
    
    Requirements: Error handling for API failures and invalid inputs
    """
    # Test with invalid API key
    invalid_client = RiotAPIClient(api_key="invalid_key")
    scorer = StandardScorer()
    engine = StandardSuggestionEngine(invalid_client, scorer)
    
    draft_state = DraftState(
        role=Role.MIDDLE,
        ally_champions=[],
        enemy_champions=[],
        banned_champions=[],
        patch="14.1"
    )
    
    # This should handle API errors gracefully (using mock data for MVP)
    async with invalid_client:
        result = await engine.generate_recommendations(draft_state, [])
        # Should still return results using mock data
        assert result is not None
        assert isinstance(result.overall_recommendations, list)