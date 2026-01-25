"""
Riot Games API client implementation.

This module provides a concrete implementation of the DataManager interface
that communicates with Riot Games API endpoints including Match-V5 API and Data Dragon.
"""

import os
import json
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
import aiohttp
import logging

from .manager import DataManager, SimpleCache
from .aggregator import MatchDataAggregator
from ..models import (
    ChampionStats, MatchData, MatchFilters, UserData, Role, 
    Participant, ChampionData, ChampionTag, SynergyData, CounterData
)

logger = logging.getLogger(__name__)


class RiotAPIError(Exception):
    """Exception raised for Riot API related errors."""
    pass


class RateLimitError(RiotAPIError):
    """Exception raised when API rate limit is exceeded."""
    pass


class RiotAPIClient(DataManager):
    """Concrete implementation of DataManager for Riot Games API."""
    
    # API Endpoints
    DATA_DRAGON_BASE = "https://ddragon.leagueoflegends.com"
    RIOT_API_BASE = "https://americas.api.riotgames.com"
    
    # Cache TTL values (in seconds)
    CHAMPION_DATA_TTL = 86400  # 24 hours
    MATCH_DATA_TTL = 3600      # 1 hour
    STATS_DATA_TTL = 1800      # 30 minutes
    
    def __init__(self, api_key: Optional[str] = None, region: str = "na1"):
        """
        Initialize the Riot API client.
        
        Args:
            api_key: Riot Games API key. If None, will try to get from environment.
            region: Region for API calls (default: na1)
        """
        self.api_key = api_key or os.getenv("RIOT_API_KEY")
        if not self.api_key:
            raise ValueError("Riot API key must be provided or set in RIOT_API_KEY environment variable")
        
        self.region = region
        self.cache = SimpleCache()
        self.session: Optional[aiohttp.ClientSession] = None
        self.aggregator = MatchDataAggregator()
        
        # Rate limiting
        self._request_times: List[float] = []
        self._rate_limit_per_second = 20
        self._rate_limit_per_2_minutes = 100
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "X-Riot-Token": self.api_key,
            "Accept": "application/json"
        }
    
    async def _rate_limit_check(self):
        """Check and enforce rate limits."""
        now = asyncio.get_event_loop().time()
        
        # Remove requests older than 2 minutes
        self._request_times = [t for t in self._request_times if now - t < 120]
        
        # Check 2-minute rate limit
        if len(self._request_times) >= self._rate_limit_per_2_minutes:
            sleep_time = 120 - (now - self._request_times[0])
            if sleep_time > 0:
                logger.warning(f"Rate limit reached, sleeping for {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)
        
        # Check per-second rate limit
        recent_requests = [t for t in self._request_times if now - t < 1]
        if len(recent_requests) >= self._rate_limit_per_second:
            await asyncio.sleep(1)
        
        self._request_times.append(now)
    
    async def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make an HTTP request with error handling and rate limiting.
        
        Args:
            url: The URL to request
            params: Query parameters
            
        Returns:
            JSON response data
            
        Raises:
            RiotAPIError: For API-related errors
            RateLimitError: When rate limited
        """
        if not self.session:
            raise RiotAPIError("Session not initialized. Use async context manager.")
        
        await self._rate_limit_check()
        
        try:
            async with self.session.get(url, headers=self._get_headers(), params=params) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited, retry after {retry_after} seconds")
                    raise RateLimitError(f"Rate limited, retry after {retry_after} seconds")
                elif response.status == 403:
                    raise RiotAPIError("Forbidden - check API key")
                elif response.status == 404:
                    raise RiotAPIError("Resource not found")
                else:
                    error_text = await response.text()
                    raise RiotAPIError(f"API request failed with status {response.status}: {error_text}")
        
        except aiohttp.ClientError as e:
            raise RiotAPIError(f"Network error: {str(e)}")
    
    async def _get_current_patch(self) -> str:
        """Get the current game patch version."""
        cache_key = "current_patch"
        cached_patch = self.cache.get(cache_key)
        if cached_patch:
            return cached_patch
        
        url = f"{self.DATA_DRAGON_BASE}/api/versions.json"
        try:
            # Data Dragon doesn't require API key
            if not self.session:
                raise RiotAPIError("Session not initialized")
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    versions = await response.json()
                    current_patch = versions[0]  # First version is the latest
                    self.cache.set(cache_key, current_patch, self.CHAMPION_DATA_TTL)
                    return current_patch
                else:
                    raise RiotAPIError(f"Failed to get patch version: {response.status}")
        except aiohttp.ClientError as e:
            raise RiotAPIError(f"Network error getting patch version: {str(e)}")
    
    async def get_champion_data(self, patch: Optional[str] = None) -> Dict[str, ChampionData]:
        """
        Get champion data from Data Dragon.
        
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
        
        url = f"{self.DATA_DRAGON_BASE}/cdn/{patch}/data/en_US/champion.json"
        
        try:
            if not self.session:
                raise RiotAPIError("Session not initialized")
            
            async with self.session.get(url) as response:
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
                    raise RiotAPIError(f"Failed to get champion data: {response.status}")
        
        except aiohttp.ClientError as e:
            raise RiotAPIError(f"Network error getting champion data: {str(e)}")
    
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
        Fetch match data based on provided filters.
        
        Note: This is a simplified implementation for MVP.
        Real implementation would query Match-V5 API.
        """
        cache_key = f"match_data_{filters.patch}_{filters.role.value}_{filters.rank_tier}"
        cached_matches = self.cache.get(cache_key)
        if cached_matches:
            return cached_matches
        
        # For MVP, return mock match data
        logger.warning("Using mock match data for MVP")
        
        matches = []
        # Mock some match data for testing - create more diverse data
        champion_pool = ["Yasuo", "Zed", "Ahri", "Orianna", "Syndra", "Jinx", "Thresh", "Graves", "Garen", "Darius"]
        
        for i in range(50):  # More matches for better statistics
            # Create two teams with different champions
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
                match_id=f"NA1_{1000000 + i}",
                participants=participants,
                patch=filters.patch,
                game_duration=1800 + i * 60
            ))
        
        self.cache.set(cache_key, matches, self.MATCH_DATA_TTL)
        return matches
    
    async def fetch_synergy_data(self, patch: str, role_a: Role, role_b: Role) -> List[SynergyData]:
        """
        Fetch synergy data between two roles for a specific patch.
        """
        cache_key = f"synergy_data_{patch}_{role_a.value}_{role_b.value}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # Fetch match data for the patch
        filters = MatchFilters(patch=patch, role=role_a)  # Use role_a as primary filter
        matches = await self.fetch_match_data(filters)
        
        # Calculate synergy data using aggregator
        synergy_data = self.aggregator.calculate_synergy_data(matches, role_a, role_b)
        
        self.cache.set(cache_key, synergy_data, self.STATS_DATA_TTL)
        return synergy_data
    
    async def fetch_counter_data(self, patch: str, role: Role) -> List[CounterData]:
        """
        Fetch counter data for a specific role and patch.
        """
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
    
    async def save_user_data(self, user_data: UserData) -> None:
        """Save user data to persistent storage (JSON file for MVP)."""
        try:
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
            raise RiotAPIError(f"Failed to save user data: {e}")
    
    async def load_user_data(self) -> Optional[UserData]:
        """Load user data from persistent storage."""
        try:
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