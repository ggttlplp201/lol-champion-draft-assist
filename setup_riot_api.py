#!/usr/bin/env python3
"""
Setup script for Riot API integration.

This script helps you set up the Riot API key and test the integration.
"""

import os
import sys
import asyncio
from pathlib import Path

def check_requirements():
    """Check if required packages are installed."""
    try:
        import riotwatcher
        print("✅ RiotWatcher is installed")
        return True
    except ImportError:
        print("❌ RiotWatcher is not installed")
        print("   Run: pip install -r requirements.txt")
        return False

def check_api_key():
    """Check if Riot API key is set."""
    api_key = os.getenv("RIOT_API_KEY")
    if api_key:
        print(f"✅ Riot API key is set: {api_key[:8]}...")
        return True
    else:
        print("❌ Riot API key is not set")
        print("   Get your API key from: https://developer.riotgames.com/")
        print("   Then set it with: export RIOT_API_KEY='your_key_here'")
        return False

async def test_api_connection():
    """Test the API connection."""
    try:
        from src.data.riotwatcher_client import RiotWatcherClient
        
        print("🔄 Testing API connection...")
        client = RiotWatcherClient()
        
        # Test getting current patch
        patch = await client._get_current_patch()
        print(f"✅ Successfully connected! Current patch: {patch}")
        
        # Test getting champion data
        champion_data = await client.get_champion_data()
        print(f"✅ Champion data loaded: {len(champion_data)} champions")
        
        return True
        
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False

def main():
    """Main setup function."""
    print("🚀 Riot API Setup")
    print("=" * 50)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Check API key
    if not check_api_key():
        print("\n📝 To get started:")
        print("1. Go to https://developer.riotgames.com/")
        print("2. Create an account and get a development API key")
        print("3. Set the environment variable:")
        print("   export RIOT_API_KEY='your_key_here'")
        print("4. Run this script again")
        sys.exit(1)
    
    # Test API connection
    print("\n🔄 Testing API connection...")
    success = asyncio.run(test_api_connection())
    
    if success:
        print("\n🎉 Setup complete!")
        print("You can now run the web app with real Riot data:")
        print("   python -m src.interface.web_app")
    else:
        print("\n❌ Setup failed")
        print("Check your API key and internet connection")
        sys.exit(1)

if __name__ == "__main__":
    main()