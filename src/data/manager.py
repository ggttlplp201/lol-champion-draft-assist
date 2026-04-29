"""
Data Manager for handling API communication and caching.

This module provides the DataManager class that handles communication with
Riot Games API endpoints and manages local caching of data.
"""

import os
import json
import pickle
from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic, Any, Dict
from datetime import datetime, timedelta
from pathlib import Path

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
        self.created_at = datetime.now()
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.now() > self.expires_at
    
    def time_until_expiry(self) -> timedelta:
        """Get time remaining until expiry."""
        return self.expires_at - datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert cache entry to dictionary for serialization."""
        return {
            'data': self.data,
            'expires_at': self.expires_at.isoformat(),
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data_dict: Dict[str, Any]) -> 'CacheEntry[T]':
        """Create cache entry from dictionary."""
        entry = cls.__new__(cls)
        entry.data = data_dict['data']
        entry.expires_at = datetime.fromisoformat(data_dict['expires_at'])
        entry.created_at = datetime.fromisoformat(data_dict['created_at'])
        return entry


class PersistentCache:
    """
    Enhanced cache implementation with persistent storage and TTL-based invalidation.
    
    Requirements: 1.5 - Cache API responses locally and refresh data every 24 hours
    """
    
    def __init__(self, cache_dir: str = "cache"):
        self._memory_cache: Dict[str, CacheEntry] = {}
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Load existing cache from disk on initialization
        self._load_cache_from_disk()
    
    def get(self, key: str) -> Optional[T]:
        """
        Get cached data if not expired.
        
        First checks memory cache, then disk cache if not found in memory.
        """
        # Check memory cache first
        entry = self._memory_cache.get(key)
        if entry and not entry.is_expired():
            return entry.data
        elif entry and entry.is_expired():
            # Remove expired entry from memory and disk
            del self._memory_cache[key]
            self._remove_from_disk(key)
            return None
        
        # Check disk cache if not in memory
        disk_entry = self._load_from_disk(key)
        if disk_entry and not disk_entry.is_expired():
            # Load into memory cache for faster access
            self._memory_cache[key] = disk_entry
            return disk_entry.data
        elif disk_entry and disk_entry.is_expired():
            # Remove expired entry from disk
            self._remove_from_disk(key)
        
        return None
    
    def set(self, key: str, data: T, ttl: int) -> None:
        """
        Store data in cache with TTL.
        
        Stores in both memory and disk for persistence across restarts.
        """
        entry = CacheEntry(data, ttl)
        
        # Store in memory cache
        self._memory_cache[key] = entry
        
        # Store on disk for persistence
        self._save_to_disk(key, entry)
    
    def clear(self) -> None:
        """Clear all cached data from memory and disk."""
        self._memory_cache.clear()
        
        # Clear disk cache
        for cache_file in self.cache_dir.glob("*.cache"):
            cache_file.unlink()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        total_entries = len(self._memory_cache)
        expired_entries = sum(1 for entry in self._memory_cache.values() if entry.is_expired())
        
        return {
            'total_entries': total_entries,
            'active_entries': total_entries - expired_entries,
            'expired_entries': expired_entries,
            'cache_dir': str(self.cache_dir),
            'disk_files': len(list(self.cache_dir.glob("*.cache")))
        }
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries from memory and disk.
        
        Returns the number of entries cleaned up.
        """
        cleaned_count = 0
        
        # Clean memory cache
        expired_keys = [key for key, entry in self._memory_cache.items() if entry.is_expired()]
        for key in expired_keys:
            del self._memory_cache[key]
            self._remove_from_disk(key)  # Also remove from disk
            cleaned_count += 1
        
        # Clean disk cache (check files that might not be in memory)
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                key = cache_file.stem
                if key not in self._memory_cache:  # Only check files not in memory
                    entry = self._load_from_disk(key)
                    if entry and entry.is_expired():
                        cache_file.unlink()
                        cleaned_count += 1
            except Exception:
                # If we can't load the file, it's probably corrupted, so remove it
                cache_file.unlink()
                cleaned_count += 1
        
        return cleaned_count
    
    def _save_to_disk(self, key: str, entry: CacheEntry) -> None:
        """Save cache entry to disk."""
        try:
            cache_file = self.cache_dir / f"{key}.cache"
            with open(cache_file, 'wb') as f:
                pickle.dump(entry.to_dict(), f)
        except Exception as e:
            # Log error but don't fail the operation
            print(f"Warning: Failed to save cache entry to disk: {e}")
    
    def _load_from_disk(self, key: str) -> Optional[CacheEntry]:
        """Load cache entry from disk."""
        try:
            cache_file = self.cache_dir / f"{key}.cache"
            if cache_file.exists():
                with open(cache_file, 'rb') as f:
                    data_dict = pickle.load(f)
                return CacheEntry.from_dict(data_dict)
        except Exception as e:
            # Log error and remove corrupted file
            print(f"Warning: Failed to load cache entry from disk: {e}")
            try:
                cache_file = self.cache_dir / f"{key}.cache"
                if cache_file.exists():
                    cache_file.unlink()
            except Exception:
                pass
        
        return None
    
    def _remove_from_disk(self, key: str) -> None:
        """Remove cache entry from disk."""
        try:
            cache_file = self.cache_dir / f"{key}.cache"
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            print(f"Warning: Failed to remove cache entry from disk: {e}")
    
    def _load_cache_from_disk(self) -> None:
        """Load all valid cache entries from disk into memory on startup."""
        for cache_file in self.cache_dir.glob("*.cache"):
            try:
                key = cache_file.stem
                entry = self._load_from_disk(key)
                if entry and not entry.is_expired():
                    self._memory_cache[key] = entry
                elif entry and entry.is_expired():
                    # Remove expired file
                    cache_file.unlink()
            except Exception:
                # Remove corrupted files
                try:
                    cache_file.unlink()
                except Exception:
                    pass


class SimpleCache:
    """Simple in-memory cache implementation (legacy compatibility)."""
    
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