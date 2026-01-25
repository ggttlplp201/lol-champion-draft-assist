"""
Tests for core data models.

Basic tests to ensure the data models are properly defined and functional.
"""

import pytest
from datetime import datetime
from src.models import (
    Champion, Role, ChampionTag, DraftState, ChampionRecommendation,
    ScoreBreakdown, RecommendationResult, ChampionStats, UserData,
    UserPreferences, ScoreWeights
)


def test_champion_creation():
    """Test basic Champion model creation."""
    champion = Champion(
        id="ahri",
        name="Ahri",
        role=Role.MIDDLE,
        tags=[ChampionTag.MAGE, ChampionTag.ASSASSIN]
    )
    
    assert champion.id == "ahri"
    assert champion.name == "Ahri"
    assert champion.role == Role.MIDDLE
    assert ChampionTag.MAGE in champion.tags
    assert ChampionTag.ASSASSIN in champion.tags


def test_draft_state_creation():
    """Test DraftState model creation."""
    ahri = Champion("ahri", "Ahri", Role.MIDDLE, [ChampionTag.MAGE])
    yasuo = Champion("yasuo", "Yasuo", Role.MIDDLE, [ChampionTag.ASSASSIN])
    zed = Champion("zed", "Zed", Role.MIDDLE, [ChampionTag.ASSASSIN])
    
    draft_state = DraftState(
        role=Role.MIDDLE,
        ally_champions=[ahri],
        enemy_champions=[yasuo],
        banned_champions=[zed],
        patch="14.1"
    )
    
    assert draft_state.role == Role.MIDDLE
    assert len(draft_state.ally_champions) == 1
    assert len(draft_state.enemy_champions) == 1
    assert len(draft_state.banned_champions) == 1
    assert draft_state.patch == "14.1"


def test_score_breakdown_creation():
    """Test ScoreBreakdown model creation."""
    breakdown = ScoreBreakdown(
        meta_score=75.0,
        synergy_score=60.0,
        counter_score=80.0,
        confidence_bonus=15.0
    )
    
    assert breakdown.meta_score == 75.0
    assert breakdown.synergy_score == 60.0
    assert breakdown.counter_score == 80.0
    assert breakdown.confidence_bonus == 15.0


def test_champion_recommendation_creation():
    """Test ChampionRecommendation model creation."""
    champion = Champion("ahri", "Ahri", Role.MIDDLE, [ChampionTag.MAGE])
    breakdown = ScoreBreakdown(75.0, 60.0, 80.0, 15.0)
    
    recommendation = ChampionRecommendation(
        champion=champion,
        score=85.0,
        explanations=["Strong in current patch", "Good synergy with team"],
        score_breakdown=breakdown
    )
    
    assert recommendation.champion.name == "Ahri"
    assert recommendation.score == 85.0
    assert len(recommendation.explanations) == 2
    assert recommendation.score_breakdown.meta_score == 75.0


def test_user_preferences_defaults():
    """Test UserPreferences model with default values."""
    preferences = UserPreferences(
        score_weights=ScoreWeights(),
        confidence_bonus=15.0
    )
    
    assert preferences.score_weights.meta == 0.4
    assert preferences.score_weights.synergy == 0.3
    assert preferences.score_weights.counter == 0.3
    assert preferences.confidence_bonus == 15.0


def test_role_enum():
    """Test Role enum values."""
    assert Role.MIDDLE.value == "MIDDLE"
    assert Role.TOP.value == "TOP"
    assert Role.JUNGLE.value == "JUNGLE"
    assert Role.BOTTOM.value == "BOTTOM"
    assert Role.UTILITY.value == "UTILITY"


def test_champion_tag_enum():
    """Test ChampionTag enum values."""
    assert ChampionTag.MAGE.value == "Mage"
    assert ChampionTag.ASSASSIN.value == "Assassin"
    assert ChampionTag.TANK.value == "Tank"
    assert ChampionTag.FIGHTER.value == "Fighter"
    assert ChampionTag.MARKSMAN.value == "Marksman"
    assert ChampionTag.SUPPORT.value == "Support"