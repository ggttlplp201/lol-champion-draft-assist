"""
Suggestion Engine for orchestrating champion recommendations.

This module provides the main SuggestionEngine class that coordinates
data fetching, scoring, and recommendation generation.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from .models import (
    DraftState, ChampionRecommendation, RecommendationResult,
    Champion, ChampionStats, SynergyData, CounterData,
    ScoreBreakdown, UserPreferences, ScoreWeights
)
from .data.manager import DataManager
from .scoring.scorer import ChampionScorer


class SuggestionEngine(ABC):
    """Abstract base class for suggestion engines."""
    
    @abstractmethod
    async def generate_recommendations(
        self,
        draft_state: DraftState,
        user_champion_pool: List[str]
    ) -> RecommendationResult:
        """Generate champion recommendations based on draft state and user pool."""
        pass


class StandardSuggestionEngine(SuggestionEngine):
    """Standard implementation of the suggestion engine."""
    
    def __init__(self, data_manager: DataManager, scorer: ChampionScorer):
        self.data_manager = data_manager
        self.scorer = scorer
        self.default_preferences = UserPreferences(
            score_weights=ScoreWeights(),
            confidence_bonus=15.0
        )
    
    async def generate_recommendations(
        self,
        draft_state: DraftState,
        user_champion_pool: List[str]
    ) -> RecommendationResult:
        """
        Generate champion recommendations based on current draft state.
        
        Returns both champion pool recommendations (filtered to user's pool with bonus)
        and overall recommendations (all champions).
        """
        # Fetch required data
        champion_stats = await self.data_manager.fetch_champion_stats(
            draft_state.patch, 
            draft_state.role
        )
        
        # For MVP, we'll use placeholder data structures
        # These will be implemented in future tasks
        synergy_data: List[SynergyData] = []
        counter_data: List[CounterData] = []
        
        # Get all available champions for the role (placeholder)
        available_champions = self._get_available_champions(
            draft_state, 
            champion_stats
        )
        
        # Calculate scores for all champions
        all_recommendations = []
        for champion in available_champions:
            stats = self._find_champion_stats(champion.id, champion_stats)
            if not stats:
                continue
                
            recommendation = self._create_recommendation(
                champion, 
                stats,
                draft_state,
                synergy_data,
                counter_data,
                is_in_pool=False
            )
            all_recommendations.append(recommendation)
        
        # Sort by score (descending)
        all_recommendations.sort(key=lambda x: x.score, reverse=True)
        
        # Filter for champion pool recommendations
        pool_recommendations = [
            self._create_recommendation(
                rec.champion,
                self._find_champion_stats(rec.champion.id, champion_stats),
                draft_state,
                synergy_data,
                counter_data,
                is_in_pool=True
            )
            for rec in all_recommendations
            if rec.champion.id in user_champion_pool
        ]
        
        # Sort pool recommendations by score (descending)
        pool_recommendations.sort(key=lambda x: x.score, reverse=True)
        
        return RecommendationResult(
            champion_pool_recommendations=pool_recommendations[:5],
            overall_recommendations=all_recommendations[:5],
            timestamp=datetime.now()
        )
    
    def _get_available_champions(
        self, 
        draft_state: DraftState, 
        champion_stats: List[ChampionStats]
    ) -> List[Champion]:
        """Get list of available champions excluding banned ones."""
        # Placeholder implementation - will be expanded in future tasks
        banned_ids = {champ.id for champ in draft_state.banned_champions}
        
        available = []
        for stats in champion_stats:
            if stats.champion_id not in banned_ids:
                # Create basic champion object from stats
                champion = Champion(
                    id=stats.champion_id,
                    name=stats.champion_id.title(),  # Placeholder name
                    role=stats.role,
                    tags=[]  # Will be populated from API data
                )
                available.append(champion)
        
        return available
    
    def _find_champion_stats(
        self, 
        champion_id: str, 
        champion_stats: List[ChampionStats]
    ) -> Optional[ChampionStats]:
        """Find stats for a specific champion."""
        for stats in champion_stats:
            if stats.champion_id == champion_id:
                return stats
        return None
    
    def _create_recommendation(
        self,
        champion: Champion,
        stats: ChampionStats,
        draft_state: DraftState,
        synergy_data: List[SynergyData],
        counter_data: List[CounterData],
        is_in_pool: bool = False
    ) -> ChampionRecommendation:
        """Create a champion recommendation with scores and explanations."""
        # Calculate component scores
        meta_score = self.scorer.calculate_meta_score(champion, stats)
        synergy_score = self.scorer.calculate_synergy_score(
            champion, 
            draft_state.ally_champions, 
            synergy_data
        )
        counter_score = self.scorer.calculate_counter_score(
            champion,
            draft_state.enemy_champions,
            counter_data
        )
        
        # Apply confidence bonus if in user's champion pool
        confidence_bonus = self.default_preferences.confidence_bonus if is_in_pool else 0.0
        
        # Calculate final score
        final_score = self.scorer.calculate_final_score(
            meta_score,
            synergy_score,
            counter_score,
            self.default_preferences.score_weights,
            confidence_bonus
        )
        
        # Create score breakdown
        score_breakdown = ScoreBreakdown(
            meta_score=meta_score,
            synergy_score=synergy_score,
            counter_score=counter_score,
            confidence_bonus=confidence_bonus if is_in_pool else None
        )
        
        # Generate explanations (placeholder implementation)
        explanations = self._generate_explanations(
            champion, 
            score_breakdown, 
            draft_state
        )
        
        return ChampionRecommendation(
            champion=champion,
            score=final_score,
            explanations=explanations,
            score_breakdown=score_breakdown
        )
    
    def _generate_explanations(
        self,
        champion: Champion,
        score_breakdown: ScoreBreakdown,
        draft_state: DraftState
    ) -> List[str]:
        """Generate explanations based on score components."""
        explanations = []
        
        # Determine highest contributing factors
        scores = [
            (score_breakdown.meta_score, "meta"),
            (score_breakdown.synergy_score, "synergy"), 
            (score_breakdown.counter_score, "counter")
        ]
        scores.sort(key=lambda x: x[0], reverse=True)
        
        # Add explanations for top contributing factors
        for score, factor in scores[:2]:  # Top 2 factors
            if factor == "meta" and score > 60:
                explanations.append("Strong pick in the current patch")
            elif factor == "synergy" and score > 60 and draft_state.ally_champions:
                ally_name = draft_state.ally_champions[0].name
                explanations.append(f"Synergizes well with {ally_name}")
            elif factor == "counter" and score > 60 and draft_state.enemy_champions:
                enemy_name = draft_state.enemy_champions[0].name
                explanations.append(f"Performs well against {enemy_name}")
        
        # Add confidence bonus explanation
        if score_breakdown.confidence_bonus:
            explanations.append("Champion in your pool (confidence bonus applied)")
        
        # Ensure we have at least one explanation
        if not explanations:
            explanations.append("Balanced pick for current draft state")
        
        return explanations[:4]  # Limit to 4 explanations as per requirements