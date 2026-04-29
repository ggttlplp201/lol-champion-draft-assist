"""
Tests for enhanced caching functionality.

Tests the PersistentCache implementation and cache management features.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from src.data.manager import PersistentCache, CacheEntry


def test_persistent_cache_basic_operations():
    """Test basic cache operations with persistent storage."""
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = PersistentCache(temp_dir)
        
        # Test setting and getting data
        test_data = {"champion": "ahri", "win_rate": 0.52}
        cache.set("test_key", test_data, 3600)  # 1 hour TTL
        
        retrieved_data = cache.get("test_key")
        assert retrieved_data == test_data
        
        # Test that data persists to disk
        cache_files = list(Path(temp_dir).glob("*.cache"))
        assert len(cache_files) == 1
        assert cache_files[0].name == "test_key.cache"


def test_persistent_cache_expiration():
    """Test cache expiration functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = PersistentCache(temp_dir)
        
        # Set data with very short TTL
        test_data = {"champion": "yasuo", "score": 85}
        cache.set("short_ttl", test_data, 1)  # 1 second TTL
        
        # Should be available immediately
        assert cache.get("short_ttl") == test_data
        
        # Wait for expiration (simulate by manually expiring)
        entry = cache._memory_cache["short_ttl"]
        entry.expires_at = datetime.now() - timedelta(seconds=1)
        
        # Should return None after expiration
        assert cache.get("short_ttl") is None
        
        # Should be removed from memory cache
        assert "short_ttl" not in cache._memory_cache


def test_persistent_cache_disk_persistence():
    """Test that cache persists across cache instance restarts."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create first cache instance and store data
        cache1 = PersistentCache(temp_dir)
        test_data = {"champion": "zed", "meta_score": 75}
        cache1.set("persistent_key", test_data, 3600)
        
        # Create second cache instance (simulates restart)
        cache2 = PersistentCache(temp_dir)
        
        # Data should be loaded from disk
        retrieved_data = cache2.get("persistent_key")
        assert retrieved_data == test_data


def test_persistent_cache_cleanup():
    """Test cache cleanup functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = PersistentCache(temp_dir)
        
        # Add multiple entries with different TTLs
        cache.set("active_key", {"data": "active"}, 3600)  # 1 hour
        cache.set("expired_key", {"data": "expired"}, 1)   # 1 second
        
        # Manually expire the second entry
        entry = cache._memory_cache["expired_key"]
        entry.expires_at = datetime.now() - timedelta(seconds=1)
        
        # Run cleanup
        cleaned_count = cache.cleanup_expired()
        
        # Should have cleaned up 1 entry
        assert cleaned_count >= 1
        
        # Active entry should still be available
        assert cache.get("active_key") == {"data": "active"}
        
        # Expired entry should be gone
        assert cache.get("expired_key") is None


def test_cache_stats():
    """Test cache statistics functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = PersistentCache(temp_dir)
        
        # Add some test data
        cache.set("key1", {"data": 1}, 3600)
        cache.set("key2", {"data": 2}, 3600)
        cache.set("key3", {"data": 3}, 1)  # Short TTL
        
        # Get stats
        stats = cache.get_cache_stats()
        
        assert stats["total_entries"] == 3
        assert stats["cache_dir"] == temp_dir
        assert stats["disk_files"] == 3
        
        # Expire one entry and check stats again
        entry = cache._memory_cache["key3"]
        entry.expires_at = datetime.now() - timedelta(seconds=1)
        
        # Access expired entry to trigger cleanup
        cache.get("key3")
        
        updated_stats = cache.get_cache_stats()
        assert updated_stats["total_entries"] == 2


def test_cache_entry_serialization():
    """Test CacheEntry serialization and deserialization."""
    test_data = {"champion": "orianna", "synergy": 0.65}
    entry = CacheEntry(test_data, 3600)
    
    # Test serialization
    entry_dict = entry.to_dict()
    assert entry_dict["data"] == test_data
    assert "expires_at" in entry_dict
    assert "created_at" in entry_dict
    
    # Test deserialization
    restored_entry = CacheEntry.from_dict(entry_dict)
    assert restored_entry.data == test_data
    assert restored_entry.expires_at == entry.expires_at
    assert restored_entry.created_at == entry.created_at


def test_cache_error_handling():
    """Test cache error handling with corrupted files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = PersistentCache(temp_dir)
        
        # Create a corrupted cache file
        corrupted_file = Path(temp_dir) / "corrupted.cache"
        with open(corrupted_file, "w") as f:
            f.write("invalid pickle data")
        
        # Cache should handle corrupted files gracefully
        result = cache.get("corrupted")
        assert result is None
        
        # Corrupted file should be removed
        assert not corrupted_file.exists()


@pytest.mark.asyncio
async def test_riot_api_client_enhanced_caching():
    """Test RiotAPIClient with enhanced caching functionality."""
    from src.data.riot_api_client import RiotAPIClient
    from src.models import Role
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create client with custom cache directory
        client = RiotAPIClient(api_key="test_key")
        client.cache = PersistentCache(temp_dir)
        
        async with client:
            # Test cache stats
            initial_stats = client.get_cache_stats()
            assert "total_entries" in initial_stats
            assert "cache_dir" in initial_stats
            
            # Fetch some data (will be cached)
            stats = await client.fetch_champion_stats("14.1", Role.MIDDLE)
            assert len(stats) > 0
            
            # Check that cache now has entries
            updated_stats = client.get_cache_stats()
            assert updated_stats["total_entries"] > initial_stats["total_entries"]
            
            # Test cache cleanup
            cleaned_count = client.cleanup_expired_cache()
            assert isinstance(cleaned_count, int)
            
            # Test cache clearing
            client.clear_cache()
            final_stats = client.get_cache_stats()
            assert final_stats["total_entries"] == 0