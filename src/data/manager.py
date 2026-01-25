"""
Data Manager for handling API communication and caching.

This module provides the DataManager class that handles communication with
Riot Games API endpoints and manages local caching of data.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic
from datetime import datetime, timedelta

from ..models import (
    ChampionStats, MatchData, MatchFilters, UserData, Role,
    SynergyData, CounterData
)

T = TypeVar('T')


class DataManager(ABC):
    """Abstract base class for data management operations."""
    
    @abstractmethod
    async def fetch_champion_stats(self, patch: str, role: Role) -> List[ChampionStats]:
        """Fetch champion statistics for a specific patch and role."""
        pass
    
    @abstractmethod
    async def fetch_match_data(self, filters: MatchFilters) -> List[MatchData]:
        """Fetch match data based on provided filters."""
        pass
    
    @abstractmethod
    async def fetch_synergy_data(self, patch: str, role_a: Role, role_b: Role) -> List[SynergyData]:
        """Fetch synergy data between two roles for a specific patch."""
        pass
    
    @abstractmethod
    async def fetch_counter_data(self, patch: str, role: Role) -> List[CounterData]:
        """Fetch counter data for a specific role and patch."""
        pass
    
    @abstractmethod
    def get_cached_data(self, key: str) -> Optional[T]:
        """Retrieve cached data by key."""
        pass
    
    @abstractmethod
    def set_cached_data(self, key: str, data: T, ttl: int) -> None:
        """Store data in cache with time-to-live."""
        pass
    
    @abstractmethod
    async def save_user_data(self, user_data: UserData) -> None:
        """Save user data to persistent storage."""
        pass
    
    @abstractmethod
    async def load_user_data(self) -> Optional[UserData]:
        """Load user data from persistent storage."""
        pass


class CacheEntry(Generic[T]):
    """Cache entry with expiration tracking."""
    
    def __init__(self, data: T, ttl: int):
        self.data = data
        self.expires_at = datetime.now() + timedelta(seconds=ttl)
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.now() > self.expires_at


class SimpleCache:
    """Simple in-memory cache implementation."""
    
    def __init__(self):
        self._cache: dict[str, CacheEntry] = {}
    
    def get(self, key: str) -> Optional[T]:
        """Get cached data if not expired."""
        entry = self._cache.get(key)
        if entry and not entry.is_expired():
            return entry.data
        elif entry:
            # Remove expired entry
            del self._cache[key]
        return None
    
    def set(self, key: str, data: T, ttl: int) -> None:
        """Store data in cache with TTL."""
        self._cache[key] = CacheEntry(data, ttl)
    
    def clear(self) -> None:
        """Clear all cached data."""
        self._cache.clear()