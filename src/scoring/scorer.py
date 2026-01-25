"""
Champion scoring algorithms.

This module implements the mathematical scoring system for champion recommendations,
including meta, synergy, and counter score calculations.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from ..models import (
    Champion, DraftState, ChampionRecommendation, ScoreBreakdown,
    ChampionStats, SynergyData, CounterData, ScoreWeights, Role
)


class ChampionScorer(ABC):
    """Abstract base class for champion scoring algorithms."""
    
    @abstractmethod
    def calculate_meta_score(self, champion: Champion, stats: ChampionStats) -> float:
        """Calculate meta score based on patch statistics."""
        pass
    
    @abstractmethod
    def calculate_synergy_score(
        self, 
        champion: Champion, 
        ally_champions: List[Champion],
        synergy_data: List[SynergyData]
    ) -> float:
        """Calculate synergy score with allied champions."""
        pass
    
    @abstractmethod
    def calculate_counter_score(
        self,
        champion: Champion,
        enemy_champions: List[Champion], 
        counter_data: List[CounterData]
    ) -> float:
        """Calculate counter score against enemy champions."""
        pass
    
    @abstractmethod
    def calculate_final_score(
        self,
        meta_score: float,
        synergy_score: float,
        counter_score: float,
        weights: ScoreWeights,
        confidence_bonus: float = 0.0
    ) -> float:
        """Calculate final weighted score with optional confidence bonus."""
        pass


class StandardScorer(ChampionScorer):
    """Standard implementation of champion scoring algorithms."""
    
    def calculate_meta_score(self, champion: Champion, stats: ChampionStats) -> float:
        """
        Calculate meta score based on win rate.
        Normalizes win rate to 0-100 scale.
        """
        # Normalize win rate from typical range (0.3-0.7) to 0-100 scale
        return self._normalize_to_scale(stats.win_rate, 0.3, 0.7, 0, 100)
    
    def calculate_synergy_score(
        self, 
        champion: Champion, 
        ally_champions: List[Champion],
        synergy_data: List[SynergyData]
    ) -> float:
        """
        Calculate average synergy score with all allied champions.
        Uses synergy delta normalized to 0-100 scale.
        """
        if not ally_champions:
            return 50.0  # Neutral score when no allies
        
        synergy_scores = []
        for ally in ally_champions:
            synergy = self._find_synergy_data(champion.id, ally.id, synergy_data)
            if synergy:
                # Normalize synergy delta from typical range (-0.2, 0.2) to 0-100
                score = self._normalize_to_scale(synergy.synergy_delta, -0.2, 0.2, 0, 100)
                synergy_scores.append(score)
            else:
                synergy_scores.append(50.0)  # Neutral score for missing data
        
        return sum(synergy_scores) / len(synergy_scores)
    
    def calculate_counter_score(
        self,
        champion: Champion,
        enemy_champions: List[Champion], 
        counter_data: List[CounterData]
    ) -> float:
        """
        Calculate average counter score against all enemy champions.
        Uses head-to-head win rates normalized to 0-100 scale.
        """
        if not enemy_champions:
            return 50.0  # Neutral score when no enemies
        
        counter_scores = []
        for enemy in enemy_champions:
            counter = self._find_counter_data(champion.id, enemy.id, counter_data)
            if counter:
                # Normalize win rate from typical range (0.3-0.7) to 0-100
                score = self._normalize_to_scale(counter.win_rate_a, 0.3, 0.7, 0, 100)
                counter_scores.append(score)
            else:
                counter_scores.append(50.0)  # Neutral score for missing data
        
        return sum(counter_scores) / len(counter_scores)
    
    def calculate_final_score(
        self,
        meta_score: float,
        synergy_score: float,
        counter_score: float,
        weights: ScoreWeights,
        confidence_bonus: float = 0.0
    ) -> float:
        """
        Calculate final weighted score: (Meta × 0.4) + (Synergy × 0.3) + (Counter × 0.3)
        Plus optional confidence bonus for champion pool champions.
        """
        weighted_score = (
            meta_score * weights.meta +
            synergy_score * weights.synergy +
            counter_score * weights.counter
        )
        
        return weighted_score + confidence_bonus
    
    def _normalize_to_scale(
        self, 
        value: float, 
        min_input: float, 
        max_input: float, 
        min_output: float, 
        max_output: float
    ) -> float:
        """Normalize a value from input range to output range."""
        # Clamp value to input range
        clamped = max(min_input, min(max_input, value))
        
        # Normalize to 0-1 range
        normalized = (clamped - min_input) / (max_input - min_input)
        
        # Scale to output range
        return min_output + normalized * (max_output - min_output)
    
    def _find_synergy_data(
        self, 
        champion_a: str, 
        champion_b: str, 
        synergy_data: List[SynergyData],
        role_a: Optional[Role] = None,
        role_b: Optional[Role] = None
    ) -> Optional[SynergyData]:
        """
        Find synergy data for a champion pair, optionally filtered by roles.
        
        Args:
            champion_a: First champion ID
            champion_b: Second champion ID  
            synergy_data: List of synergy data
            role_a: Optional role for champion_a (for role-specific lookup)
            role_b: Optional role for champion_b (for role-specific lookup)
        """
        for synergy in synergy_data:
            pair = synergy.champion_pair
            
            # If roles are specified, match them exactly
            if role_a is not None and role_b is not None:
                if ((pair[0] == champion_a and pair[1] == champion_b and 
                     synergy.role1 == role_a and synergy.role2 == role_b) or
                    (pair[0] == champion_b and pair[1] == champion_a and 
                     synergy.role1 == role_b and synergy.role2 == role_a)):
                    return synergy
            else:
                # Fallback to champion-only matching (for backward compatibility)
                if (pair[0] == champion_a and pair[1] == champion_b) or \
                   (pair[0] == champion_b and pair[1] == champion_a):
                    return synergy
        return None
    
    def _find_counter_data(
        self, 
        champion_a: str, 
        champion_b: str, 
        counter_data: List[CounterData]
    ) -> Optional[CounterData]:
        """Find counter data for a champion matchup."""
        for counter in counter_data:
            if counter.champion_a == champion_a and counter.champion_b == champion_b:
                return counter
        return None