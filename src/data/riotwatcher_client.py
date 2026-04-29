"""
RiotWatcher-based implementation of the DataManager interface.

This module provides a concrete implementation using the RiotWatcher library
that integrates seamlessly with the existing caching and data architecture.
"""

import os
import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from riotwatcher import LolWatcher, ApiError
from .manager import DataManager, PersistentCache
from .aggregator import MatchDataAggregator
from ..models import (
    ChampionStats, MatchData, MatchFilters, UserData, Role, 
    Participant, ChampionData, ChampionTag, SynergyData, CounterData
)

logger = logging.getLogger(__name__)


class RiotWatcherError(Exception):
    """Exception raised for RiotWatcher related errors."""
    pass


class RiotWatcherClient(DataManager):
    """RiotWatcher-based implementation of DataManager."""
    
    # Cache TTL values (in seconds)
    CHAMPION_DATA_TTL = 86400  # 24 hours
    MATCH_DATA_TTL = 3600      # 1 hour
    STATS_DATA_TTL = 1800      # 30 minutes
    
    def __init__(self, api_key: Optional[str] = None, region: str = "na1"):
        """
        Initialize the RiotWatcher client.
        
        Args:
            api_key: Riot Games API key. If None, will try to get from environment.
            region: Region for API calls (default: na1)
        """
        self.api_key = api_key or os.getenv("RIOT_API_KEY")
        if not self.api_key:
            raise ValueError("Riot API key must be provided or set in RIOT_API_KEY environment variable")
        
        self.region = region
        self.cache = PersistentCache()
        self.aggregator = MatchDataAggregator()
        
        # Initialize RiotWatcher
        self.watcher = LolWatcher(self.api_key)
        
        # Region mapping for different API endpoints
        self.regional_routing = {
            "na1": "americas",
            "euw1": "europe", 
            "eun1": "europe",
            "kr": "asia",
            "jp1": "asia"
        }
        self.routing_region = self.regional_routing.get(region, "americas")
    
    async def _run_sync_in_executor(self, func, *args, **kwargs):
        """Run synchronous RiotWatcher calls in executor to avoid blocking."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    
    async def get_champion_data(self, patch: Optional[str] = None) -> Dict[str, ChampionData]:
        """
        Get champion data from Data Dragon via direct HTTP request.
        
        Args:
            patch: Game patch version. If None, uses current patch.
            
        Returns:
            Dictionary mapping champion IDs to ChampionData objects
        """
        if not patch:
            patch = await self._get_current_patch()
        
        cache_key = f"champion_data_{patch}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        try:
            # Use direct HTTP request instead of RiotWatcher for Data Dragon
            import aiohttp
            url = f"https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/champion.json"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        champions = {}
                        
                        for champ_key, champ_data in data["data"].items():
                            # Convert tags to ChampionTag enums
                            tags = []
                            for tag in champ_data.get("tags", []):
                                try:
                                    tags.append(ChampionTag(tag))
                                except ValueError:
                                    logger.warning(f"Unknown champion tag: {tag}")
                            
                            champion = ChampionData(
                                id=champ_data["id"],
                                name=champ_data["name"],
                                title=champ_data["title"],
                                tags=tags,
                                role_stats={}  # Will be populated by match data
                            )
                            champions[champ_data["id"]] = champion
                        
                        self.cache.set(cache_key, champions, self.CHAMPION_DATA_TTL)
                        return champions
                    else:
                        raise RiotWatcherError(f"Failed to get champion data: {response.status}")
            
        except Exception as e:
            raise RiotWatcherError(f"Failed to get champion data: {e}")
    
    async def _get_current_patch(self) -> str:
        """Get the current game patch version."""
        cache_key = "current_patch"
        cached_patch = self.cache.get(cache_key)
        if cached_patch:
            return cached_patch
        
        try:
            # Use direct HTTP request instead of RiotWatcher for Data Dragon
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("https://ddragon.leagueoflegends.com/api/versions.json") as response:
                    if response.status == 200:
                        versions = await response.json()
                        current_patch = versions[0]  # First version is the latest
                        self.cache.set(cache_key, current_patch, self.CHAMPION_DATA_TTL)
                        return current_patch
                    else:
                        raise RiotWatcherError(f"Failed to get patch version: {response.status}")
            
        except Exception as e:
            raise RiotWatcherError(f"Failed to get patch version: {e}")
    
    async def fetch_champion_stats(self, patch: str, role: Role) -> List[ChampionStats]:
        """
        Fetch champion statistics for a specific patch and role.
        Uses match data aggregation to calculate accurate win rates.
        """
        cache_key = f"champion_stats_{patch}_{role.value}"
        cached_stats = self.cache.get(cache_key)
        if cached_stats:
            return cached_stats
        
        # Fetch match data for the patch and role
        filters = MatchFilters(patch=patch, role=role)
        matches = await self.fetch_match_data(filters)
        
        # Filter matches and calculate win rates using aggregator
        filtered_matches = self.aggregator.filter_matches_by_patch_and_role(matches, patch, role)
        champion_stats_dict = self.aggregator.calculate_individual_champion_win_rates(filtered_matches, role)
        
        # Convert to list
        stats = list(champion_stats_dict.values())
        
        self.cache.set(cache_key, stats, self.STATS_DATA_TTL)
        return stats
    
    async def fetch_match_data(self, filters: MatchFilters) -> List[MatchData]:
        """
        Fetch match data based on provided filters using RiotWatcher.
        
        For MVP, this will fetch a limited set of matches from a high-ranked player.
        In production, you'd want to fetch from multiple players or use a different approach.
        """
        cache_key = f"match_data_{filters.patch}_{filters.role.value}_{filters.rank_tier}"
        cached_matches = self.cache.get(cache_key)
        if cached_matches:
            return cached_matches
        
        try:
            # For MVP: Get matches from a known high-ranked summoner
            # In production, you'd want to fetch from multiple sources
            summoner_name = "Faker"  # Example high-ranked player
            
            # Get summoner info
            summoner = await self._run_sync_in_executor(
                self.watcher.summoner.by_name, self.region, summoner_name
            )
            
            # Get match list (last 20 matches)
            match_list = await self._run_sync_in_executor(
                self.watcher.match.matchlist_by_puuid,
                self.routing_region,
                summoner["puuid"],
                count=20
            )
            
            matches = []
            for match_id in match_list[:10]:  # Limit to 10 matches for MVP
                try:
                    # Get match details
                    match_detail = await self._run_sync_in_executor(
                        self.watcher.match.by_id, self.routing_region, match_id
                    )
                    
                    # Convert to our MatchData format
                    match_data = self._convert_riot_match_to_match_data(match_detail)
                    if match_data:
                        matches.append(match_data)
                        
                except ApiError as e:
                    logger.warning(f"Failed to fetch match {match_id}: {e}")
                    continue
            
            self.cache.set(cache_key, matches, self.MATCH_DATA_TTL)
            return matches
            
        except ApiError as e:
            logger.warning(f"Failed to fetch real match data, using mock data: {e}")
            # Fall back to mock data if API fails
            return await self._get_mock_match_data(filters)
        except Exception as e:
            logger.warning(f"Unexpected error fetching match data, using mock data: {e}")
            return await self._get_mock_match_data(filters)
    
    def _convert_riot_match_to_match_data(self, riot_match: Dict[str, Any]) -> Optional[MatchData]:
        """Convert Riot API match data to our MatchData format."""
        try:
            info = riot_match["info"]
            participants = []
            
            for participant in info["participants"]:
                # Map position to our Role enum
                role_mapping = {
                    "TOP": Role.TOP,
                    "JUNGLE": Role.JUNGLE,
                    "MIDDLE": Role.MIDDLE,
                    "BOTTOM": Role.BOTTOM,
                    "UTILITY": Role.UTILITY
                }
                
                role = role_mapping.get(participant.get("teamPosition"), Role.MIDDLE)
                
                participant_data = Participant(
                    champion_id=participant["championName"],  # Use champion name as ID
                    role=role,
                    win=participant["win"]
                )
                participants.append(participant_data)
            
            return MatchData(
                match_id=riot_match["metadata"]["matchId"],
                participants=participants,
                patch=info["gameVersion"].split(".")[0] + "." + info["gameVersion"].split(".")[1],
                game_duration=info["gameDuration"]
            )
            
        except Exception as e:
            logger.error(f"Failed to convert match data: {e}")
            return None
    
    async def _get_mock_match_data(self, filters: MatchFilters) -> List[MatchData]:
        """Fallback mock match data when API is unavailable."""
        logger.info("Using mock match data for development")
        
        matches = []
        champion_pool = ["Yasuo", "Zed", "Ahri", "Orianna", "Syndra", "Jinx", "Thresh", "Graves", "Garen", "Darius"]
        
        for i in range(50):
            team_a_win = i % 2 == 0
            
            participants = []
            # Team A
            participants.extend([
                Participant(champion_id=champion_pool[i % 5], role=Role.MIDDLE, win=team_a_win),
                Participant(champion_id=champion_pool[(i + 1) % 10], role=Role.BOTTOM, win=team_a_win),
                Participant(champion_id=champion_pool[(i + 2) % 10], role=Role.UTILITY, win=team_a_win),
                Participant(champion_id=champion_pool[(i + 3) % 10], role=Role.JUNGLE, win=team_a_win),
                Participant(champion_id=champion_pool[(i + 4) % 10], role=Role.TOP, win=team_a_win),
            ])
            
            # Team B
            participants.extend([
                Participant(champion_id=champion_pool[(i + 5) % 5], role=Role.MIDDLE, win=not team_a_win),
                Participant(champion_id=champion_pool[(i + 6) % 10], role=Role.BOTTOM, win=not team_a_win),
                Participant(champion_id=champion_pool[(i + 7) % 10], role=Role.UTILITY, win=not team_a_win),
                Participant(champion_id=champion_pool[(i + 8) % 10], role=Role.JUNGLE, win=not team_a_win),
                Participant(champion_id=champion_pool[(i + 9) % 10], role=Role.TOP, win=not team_a_win),
            ])
            
            matches.append(MatchData(
                match_id=f"MOCK_{1000000 + i}",
                participants=participants,
                patch=filters.patch,
                game_duration=1800 + i * 60
            ))
        
        return matches
    
    async def fetch_synergy_data(self, patch: str, role_a: Role, role_b: Role) -> List[SynergyData]:
        """Fetch synergy data between two roles for a specific patch."""
        cache_key = f"synergy_data_{patch}_{role_a.value}_{role_b.value}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # Fetch match data for the patch
        filters = MatchFilters(patch=patch, role=role_a)
        matches = await self.fetch_match_data(filters)
        
        # Calculate synergy data using aggregator
        synergy_data = self.aggregator.calculate_synergy_data(matches, role_a, role_b)
        
        self.cache.set(cache_key, synergy_data, self.STATS_DATA_TTL)
        return synergy_data
    
    async def fetch_counter_data(self, patch: str, role: Role) -> List[CounterData]:
        """Fetch counter data for a specific role and patch."""
        cache_key = f"counter_data_{patch}_{role.value}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # Fetch match data for the patch and role
        filters = MatchFilters(patch=patch, role=role)
        matches = await self.fetch_match_data(filters)
        
        # Calculate counter data using aggregator
        counter_data = self.aggregator.calculate_counter_data(matches, role)
        
        self.cache.set(cache_key, counter_data, self.STATS_DATA_TTL)
        return counter_data
    
    def get_cached_data(self, key: str) -> Optional[Any]:
        """Retrieve cached data by key."""
        return self.cache.get(key)
    
    def set_cached_data(self, key: str, data: Any, ttl: int) -> None:
        """Store data in cache with time-to-live."""
        self.cache.set(key, data, ttl)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring and debugging."""
        return self.cache.get_cache_stats()
    
    def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries."""
        return self.cache.cleanup_expired()
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.cache.clear()
    
    async def save_user_data(self, user_data: UserData) -> None:
        """Save user data to persistent storage (JSON file for MVP)."""
        try:
            import json
            
            data_dict = {
                "champion_pool": user_data.champion_pool,
                "preferences": {
                    "score_weights": {
                        "meta": user_data.preferences.score_weights.meta,
                        "synergy": user_data.preferences.score_weights.synergy,
                        "counter": user_data.preferences.score_weights.counter,
                    },
                    "confidence_bonus": user_data.preferences.confidence_bonus
                },
                "last_updated": user_data.last_updated.isoformat()
            }
            
            os.makedirs("data", exist_ok=True)
            with open("data/user_data.json", "w") as f:
                json.dump(data_dict, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save user data: {e}")
            raise RiotWatcherError(f"Failed to save user data: {e}")
    
    async def load_user_data(self) -> Optional[UserData]:
        """Load user data from persistent storage."""
        try:
            import json
            
            if not os.path.exists("data/user_data.json"):
                return None
            
            with open("data/user_data.json", "r") as f:
                data_dict = json.load(f)
            
            from ..models import ScoreWeights, UserPreferences
            
            score_weights = ScoreWeights(
                meta=data_dict["preferences"]["score_weights"]["meta"],
                synergy=data_dict["preferences"]["score_weights"]["synergy"],
                counter=data_dict["preferences"]["score_weights"]["counter"]
            )
            
            preferences = UserPreferences(
                score_weights=score_weights,
                confidence_bonus=data_dict["preferences"]["confidence_bonus"]
            )
            
            return UserData(
                champion_pool=data_dict["champion_pool"],
                preferences=preferences,
                last_updated=datetime.fromisoformat(data_dict["last_updated"])
            )
            
        except Exception as e:
            logger.error(f"Failed to load user data: {e}")
            return None