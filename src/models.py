"""
Core data models for the Champion Draft Assist Tool.

This module defines the fundamental data structures used throughout the application,
including Champion, DraftState, ChampionRecommendation, and related types.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class Role(Enum):
    """Champion roles in League of Legends."""
    TOP = "TOP"
    JUNGLE = "JUNGLE"
    MIDDLE = "MIDDLE"
    BOTTOM = "BOTTOM"
    UTILITY = "UTILITY"


class ChampionTag(Enum):
    """Champion archetype tags."""
    TANK = "Tank"
    FIGHTER = "Fighter"
    ASSASSIN = "Assassin"
    MAGE = "Mage"
    MARKSMAN = "Marksman"
    SUPPORT = "Support"


@dataclass
class Champion:
    """Represents a League of Legends champion."""
    id: str
    name: str
    role: Role
    tags: List[ChampionTag]


@dataclass
class ScoreBreakdown:
    """Breakdown of recommendation score components."""
    meta_score: float
    synergy_score: float
    counter_score: float
    confidence_bonus: Optional[float] = None


@dataclass
class ChampionRecommendation:
    """A champion recommendation with score and explanations."""
    champion: Champion
    score: float
    explanations: List[str]
    score_breakdown: ScoreBreakdown


@dataclass
class DraftState:
    """Current state of the champion draft."""
    role: Role  # MVP: Fixed to MIDDLE
    ally_champions: List[Champion]
    enemy_champions: List[Champion]
    banned_champions: List[Champion]
    patch: str


@dataclass
class RecommendationResult:
    """Result containing both champion pool and overall recommendations."""
    champion_pool_recommendations: List[ChampionRecommendation]
    overall_recommendations: List[ChampionRecommendation]
    timestamp: datetime


@dataclass
class ChampionStats:
    """Statistics for a champion in a specific role and patch."""
    champion_id: str
    role: Role
    win_rate: float
    pick_rate: float
    ban_rate: float
    patch: str
    rank_tier: str


@dataclass
class MatchFilters:
    """Filters for match data queries."""
    patch: str
    role: Role
    rank_tier: Optional[str] = None
    region: Optional[str] = None


@dataclass
class Participant:
    """Match participant data."""
    champion_id: str
    role: Role
    win: bool


@dataclass
class MatchData:
    """Match data from Riot Games API."""
    match_id: str
    participants: List[Participant]
    patch: str
    game_duration: int


@dataclass
class SynergyData:
    """Synergy data between two champions."""
    champion_pair: tuple[str, str]
    role1: Role
    role2: Role
    combined_win_rate: float
    expected_win_rate: float
    synergy_delta: float
    sample_size: int
    patch: str


@dataclass
class CounterData:
    """Counter relationship between two champions."""
    champion_a: str
    champion_b: str
    role_a: Role
    role_b: Role
    win_rate_a: float  # championA win rate vs championB
    win_rate_b: float  # championB win rate vs championA
    sample_size: int
    patch: str


@dataclass
class ScoreWeights:
    """Weights for different score components."""
    meta: float = 0.4
    synergy: float = 0.3
    counter: float = 0.3


@dataclass
class UserPreferences:
    """User preferences and settings."""
    score_weights: ScoreWeights
    confidence_bonus: float = 15.0  # default confidence bonus


@dataclass
class UserData:
    """User data including champion pool and preferences."""
    champion_pool: List[str]
    preferences: UserPreferences
    last_updated: datetime


@dataclass
class RoleStatistics:
    """Statistics for a champion in a specific role."""
    win_rate: float
    pick_rate: float
    ban_rate: float
    average_game_length: float
    common_build_paths: List[Dict[str, Any]]  # Simplified for MVP


@dataclass
class ChampionData:
    """Complete champion data including static and dynamic information."""
    # Static Data (from Data Dragon)
    id: str
    name: str
    title: str
    tags: List[ChampionTag]
    
    # Dynamic Statistics (computed from match data)
    role_stats: Dict[Role, RoleStatistics]