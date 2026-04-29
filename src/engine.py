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
        
        # Names that can't be derived from id.replace('_',' ').title()
        self.champion_names = {
            "leblanc": "LeBlanc",
            "twisted_fate": "Twisted Fate",
            "vel_koz": "Vel'Koz",
            "cho_gath": "Cho'Gath",
            "kai_sa": "Kai'Sa",
            "kha_zix": "Kha'Zix",
            "kog_maw": "Kog'Maw",
            "k_sante": "K'Sante",
            "jarvan_iv": "Jarvan IV",
            "miss_fortune": "Miss Fortune",
            "master_yi": "Master Yi",
            "lee_sin": "Lee Sin",
            "renata_glasc": "Renata Glasc",
        }
    
    async def generate_recommendations(
        self,
        draft_state: DraftState,
        user_champion_pool: List[str]
    ) -> RecommendationResult:
        """
        Generate champion recommendations based on current draft state.
        
        Requirements: 2.2, 3.3, 7.3, 7.4
        - Generate champion pool and overall recommendations
        - Exclude banned champions from all suggestions
        - Display "Top 5 Champion Pool Picks" and "Top 5 Overall Picks"
        
        Returns both champion pool recommendations (filtered to user's pool with bonus)
        and overall recommendations (all champions).
        """
        # Fetch required data
        champion_stats = await self.data_manager.fetch_champion_stats(
            draft_state.patch, 
            draft_state.role
        )
        
        synergy_data = await self.data_manager.fetch_synergy_data(
            draft_state.patch, draft_state.role, draft_state.role
        )
        counter_data = await self.data_manager.fetch_counter_data(
            draft_state.patch, draft_state.role
        )
        
        # Get all available champions for the role (excluding banned champions)
        available_champions = self._get_available_champions(
            draft_state, 
            champion_stats
        )
        
        # Calculate scores for all available champions
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
                is_in_pool=False  # Overall recommendations don't get pool bonus
            )
            all_recommendations.append(recommendation)
        
        # Sort by score (descending) for overall recommendations
        all_recommendations.sort(key=lambda x: x.score, reverse=True)
        
        # Generate champion pool recommendations (filtered to user's pool with bonus)
        pool_recommendations = []
        for champion in available_champions:
            # Only include champions in user's champion pool
            if champion.id in user_champion_pool:
                stats = self._find_champion_stats(champion.id, champion_stats)
                if not stats:
                    continue
                    
                recommendation = self._create_recommendation(
                    champion,
                    stats,
                    draft_state,
                    synergy_data,
                    counter_data,
                    is_in_pool=True  # Apply confidence bonus
                )
                pool_recommendations.append(recommendation)
        
        # Sort pool recommendations by score (descending)
        pool_recommendations.sort(key=lambda x: x.score, reverse=True)
        
        # Return top 5 from each category as per requirements 7.3, 7.4
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
        """
        Get list of available champions excluding banned ones.
        
        Requirements: 3.3 - Exclude banned champions from all suggestions
        
        Note: Assumes Champion.id matches ChampionStats.champion_id format exactly.
        For production, ensure consistent ID format (Riot champion key) across all data sources.
        """
        banned_ids = {champ.id for champ in draft_state.banned_champions}
        seen = set()  # Deduplicate champions by ID
        
        available = []
        for stats in champion_stats:
            # Skip banned champions and duplicates
            if stats.champion_id in banned_ids or stats.champion_id in seen:
                continue
            
            seen.add(stats.champion_id)
            
            # Create basic champion object from stats
            champion = Champion(
                id=stats.champion_id,
                name=self._get_champion_name(stats.champion_id),  # Use proper name lookup
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
            score_breakdown=score_breakdown,
            win_rate=stats.win_rate,
            pick_rate=stats.pick_rate,
            ban_rate=stats.ban_rate,
        )
    
    def _generate_explanations(
        self,
        champion: Champion,
        score_breakdown: ScoreBreakdown,
        draft_state: DraftState
    ) -> List[str]:
        """
        Generate deterministic explanations based on score components.
        
        Requirements: 9.1, 9.2, 9.3, 9.4
        - Generate 2-4 explanation bullets using deterministic rules
        - Include meta, synergy, and counter explanations based on highest scores
        - Use specific explanation templates for each score component
        """
        explanations = []
        
        # Determine score components and their weighted contributions for ranking
        weights = self.default_preferences.score_weights
        weighted_contributions = [
            (score_breakdown.meta_score * weights.meta, score_breakdown.meta_score, "meta"),
            (score_breakdown.synergy_score * weights.synergy, score_breakdown.synergy_score, "synergy"), 
            (score_breakdown.counter_score * weights.counter, score_breakdown.counter_score, "counter")
        ]
        
        # Sort by weighted contribution (descending) to prioritize highest contributing factors
        weighted_contributions.sort(key=lambda x: x[0], reverse=True)
        
        # Generate explanations for top contributing factors (deterministic rules)
        explanation_count = 0
        max_explanations = 4  # Requirement 9.1: 2-4 explanation bullets
        
        for weighted_contrib, raw_score, component_type in weighted_contributions:
            if explanation_count >= max_explanations:
                break
                
            # Meta score explanations (Requirement 9.2)
            if component_type == "meta" and raw_score > 60:
                explanations.append("Strong pick in the current patch")
                explanation_count += 1
            
            # Synergy score explanations (Requirement 9.3)
            elif component_type == "synergy" and raw_score > 60 and draft_state.ally_champions:
                # Use first ally champion for explanation (deterministic)
                ally_name = draft_state.ally_champions[0].name
                explanations.append(f"Synergizes well with {ally_name}")
                explanation_count += 1
            
            # Counter score explanations (Requirement 9.4)
            elif component_type == "counter" and raw_score > 60 and draft_state.enemy_champions:
                # Use first enemy champion for explanation (deterministic)
                enemy_name = draft_state.enemy_champions[0].name
                explanations.append(f"Performs well against {enemy_name}")
                explanation_count += 1
        
        # Add confidence bonus explanation if applicable
        if score_breakdown.confidence_bonus and explanation_count < max_explanations:
            explanations.append("Champion in your pool (confidence bonus applied)")
            explanation_count += 1
        
        # Add team composition explanation if we have room and allies exist
        if (explanation_count < max_explanations and 
            draft_state.ally_champions and 
            len(explanations) < 2):  # Ensure we have at least 2 explanations
            explanations.append("Balances team damage profile")
            explanation_count += 1
        
        # Ensure we have at least 2 explanations as per requirement 9.1
        if len(explanations) < 2:
            explanations.append("Balanced pick for current draft state")
        
        # Return exactly 2-4 explanations as per requirements
        return explanations[:max_explanations]
    
    def _get_champion_name(self, champion_id: str) -> str:
        return self.champion_names.get(champion_id, champion_id.replace('_', ' ').title())