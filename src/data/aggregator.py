"""
Data aggregation system for match statistics.

This module provides functionality to filter matches by patch and role,
and calculate individual champion win rates from match data.
"""

from typing import List, Dict, Optional
from collections import defaultdict
import logging

from ..models import (
    MatchData, MatchFilters, Role, ChampionStats, Participant,
    SynergyData, CounterData
)

logger = logging.getLogger(__name__)


class MatchDataAggregator:
    """Aggregates match data to calculate champion statistics."""
    
    # Sample size thresholds
    MIN_SYNERGY_SAMPLE_SIZE = 5
    MIN_COUNTER_SAMPLE_SIZE = 3
    
    def _normalize_patch(self, patch: str) -> str:
        """
        Normalize patch string to major.minor format.
        
        Args:
            patch: Patch string (e.g., "14.1.123" or "14.1")
            
        Returns:
            Normalized patch string (e.g., "14.1")
        """
        parts = patch.split('.')
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}"
        return patch
    
    def filter_matches_by_patch_and_role(
        self, 
        matches: List[MatchData], 
        patch: str, 
        role: Role
    ) -> List[MatchData]:
        """
        Filter matches by patch and ensure they contain the specified role.
        
        Args:
            matches: List of match data
            patch: Game patch version to filter by
            role: Role that must be present in the match
            
        Returns:
            Filtered list of matches
        """
        filtered_matches = []
        normalized_target_patch = self._normalize_patch(patch)
        
        for match in matches:
            # Check if match is from the correct patch (normalized comparison)
            if self._normalize_patch(match.patch) != normalized_target_patch:
                continue
            
            # Check if match contains the specified role
            has_role = any(participant.role == role for participant in match.participants)
            if not has_role:
                continue
            
            filtered_matches.append(match)
        
        logger.debug(f"Filtered {len(matches)} matches to {len(filtered_matches)} for patch {patch} and role {role.value}")
        return filtered_matches
    
    def calculate_individual_champion_win_rates(
        self, 
        matches: List[MatchData], 
        role: Role
    ) -> Dict[str, ChampionStats]:
        """
        Calculate individual champion win rates for a specific role.
        
        Args:
            matches: List of match data
            role: Role to calculate win rates for
            
        Returns:
            Dictionary mapping champion IDs to their statistics
        """
        # Track wins and total games for each champion
        champion_stats = defaultdict(lambda: {"wins": 0, "games": 0, "picks": 0})
        
        # Count total role appearances for accurate pick rate calculation
        total_role_games = 0
        
        for match in matches:
            # Find participants playing the specified role
            role_participants = [p for p in match.participants if p.role == role]
            total_role_games += len(role_participants)
            
            for participant in role_participants:
                champion_id = participant.champion_id
                champion_stats[champion_id]["games"] += 1
                champion_stats[champion_id]["picks"] += 1
                
                if participant.win:
                    champion_stats[champion_id]["wins"] += 1
        
        # Convert to ChampionStats objects
        result = {}
        for champion_id, stats in champion_stats.items():
            if stats["games"] > 0:
                win_rate = stats["wins"] / stats["games"]
                # Use total role appearances as denominator for pick rate
                pick_rate = stats["picks"] / total_role_games if total_role_games > 0 else 0.0
                ban_rate = 0.0  # Simplified for MVP
                
                # Get patch from first match (all should be same patch after filtering)
                patch = matches[0].patch if matches else "unknown"
                
                result[champion_id] = ChampionStats(
                    champion_id=champion_id,
                    role=role,
                    win_rate=win_rate,
                    pick_rate=pick_rate,
                    ban_rate=ban_rate,
                    patch=patch,
                    rank_tier="ALL"  # Simplified for MVP
                )
        
        logger.info(f"Calculated win rates for {len(result)} champions in role {role.value}")
        return result
    
    def calculate_synergy_data(
        self, 
        matches: List[MatchData], 
        role_a: Role, 
        role_b: Role
    ) -> List[SynergyData]:
        """
        Calculate synergy data between champions in two different roles.
        
        Args:
            matches: List of match data
            role_a: First role
            role_b: Second role
            
        Returns:
            List of synergy data for champion pairs
        """
        # Track champion pair statistics
        pair_stats = defaultdict(lambda: {"wins": 0, "games": 0})
        # Track individual stats by (champion, role) to avoid role conflation
        individual_stats = defaultdict(lambda: {"wins": 0, "games": 0})
        
        for match in matches:
            # Find participants for each role
            role_a_participants = [p for p in match.participants if p.role == role_a]
            role_b_participants = [p for p in match.participants if p.role == role_b]
            
            # Track individual champion performance by (champion, role)
            for participant in role_a_participants + role_b_participants:
                key = (participant.champion_id, participant.role)
                individual_stats[key]["games"] += 1
                if participant.win:
                    individual_stats[key]["wins"] += 1
            
            # Track champion pair performance (same team)
            for p_a in role_a_participants:
                for p_b in role_b_participants:
                    # Only count if they're on the same team (both win or both lose)
                    if p_a.win == p_b.win:
                        # Include role information in pair key for clarity
                        pair_key = (role_a, p_a.champion_id, role_b, p_b.champion_id)
                        pair_stats[pair_key]["games"] += 1
                        if p_a.win:  # Both won
                            pair_stats[pair_key]["wins"] += 1
        
        # Calculate synergy deltas
        synergy_data = []
        patch = matches[0].patch if matches else "unknown"
        
        for pair_key, stats in pair_stats.items():
            if stats["games"] < self.MIN_SYNERGY_SAMPLE_SIZE:
                continue
            
            role_a_key, champion_a, role_b_key, champion_b = pair_key
            
            # Get individual win rates by (champion, role)
            individual_key_a = (champion_a, role_a_key)
            individual_key_b = (champion_b, role_b_key)
            
            win_rate_a = (individual_stats[individual_key_a]["wins"] / 
                         individual_stats[individual_key_a]["games"]) if individual_stats[individual_key_a]["games"] > 0 else 0.5
            win_rate_b = (individual_stats[individual_key_b]["wins"] / 
                         individual_stats[individual_key_b]["games"]) if individual_stats[individual_key_b]["games"] > 0 else 0.5
            
            # Calculate expected combined win rate (assuming independence)
            expected_win_rate = win_rate_a * win_rate_b + (1 - win_rate_a) * (1 - win_rate_b)
            
            # Calculate actual combined win rate
            combined_win_rate = stats["wins"] / stats["games"]
            
            # Calculate synergy delta
            synergy_delta = combined_win_rate - expected_win_rate
            
            # For compatibility with existing SynergyData model, keep role-aligned order
            # This prevents role collision (mid+jungle vs mid+support for same champions)
            champion_pair = (champion_a, champion_b)  # Maintain role order
            
            synergy_data.append(SynergyData(
                champion_pair=champion_pair,
                role1=role_a_key,
                role2=role_b_key,
                combined_win_rate=combined_win_rate,
                expected_win_rate=expected_win_rate,
                synergy_delta=synergy_delta,
                sample_size=stats["games"],
                patch=patch
            ))
        
        logger.info(f"Calculated synergy data for {len(synergy_data)} champion pairs between {role_a.value} and {role_b.value}")
        return synergy_data
    
    def calculate_counter_data(
        self, 
        matches: List[MatchData], 
        role: Role
    ) -> List[CounterData]:
        """
        Calculate head-to-head counter data for champions in the same role.
        
        Args:
            matches: List of match data
            role: Role to calculate counter data for
            
        Returns:
            List of counter data for champion matchups
        """
        # Track head-to-head matchup statistics with canonical keys
        matchup_stats = defaultdict(lambda: {"wins_a": 0, "wins_b": 0, "games": 0})
        
        for match in matches:
            # Find participants for the specified role
            role_participants = [p for p in match.participants if p.role == role]
            
            # For each pair of participants in the same role (opposing teams)
            for i, p_a in enumerate(role_participants):
                for j, p_b in enumerate(role_participants):
                    if i >= j:  # Avoid duplicates and self-comparison
                        continue
                    
                    # Only count if they're on opposing teams
                    if p_a.win != p_b.win:
                        champion_a = p_a.champion_id
                        champion_b = p_b.champion_id
                        
                        # Create canonical matchup key (always sorted)
                        canonical_a, canonical_b = sorted([champion_a, champion_b])
                        matchup_key = (canonical_a, canonical_b)
                        
                        matchup_stats[matchup_key]["games"] += 1
                        
                        # Track wins for the canonical first champion
                        if (champion_a == canonical_a and p_a.win) or (champion_b == canonical_a and p_b.win):
                            matchup_stats[matchup_key]["wins_a"] += 1
                        else:
                            matchup_stats[matchup_key]["wins_b"] += 1
        
        # Convert to CounterData objects
        counter_data = []
        patch = matches[0].patch if matches else "unknown"
        
        for (canonical_a, canonical_b), stats in matchup_stats.items():
            if stats["games"] < self.MIN_COUNTER_SAMPLE_SIZE:
                continue
            
            win_rate_a = stats["wins_a"] / stats["games"]
            win_rate_b = stats["wins_b"] / stats["games"]
            
            # Create both directional entries for lookup convenience
            counter_data.extend([
                CounterData(
                    champion_a=canonical_a,
                    champion_b=canonical_b,
                    role_a=role,
                    role_b=role,
                    win_rate_a=win_rate_a,
                    win_rate_b=win_rate_b,
                    sample_size=stats["games"],
                    patch=patch
                ),
                CounterData(
                    champion_a=canonical_b,
                    champion_b=canonical_a,
                    role_a=role,
                    role_b=role,
                    win_rate_a=win_rate_b,
                    win_rate_b=win_rate_a,
                    sample_size=stats["games"],
                    patch=patch
                )
            ])
        
        logger.info(f"Calculated counter data for {len(counter_data)} matchups in role {role.value}")
        return counter_data