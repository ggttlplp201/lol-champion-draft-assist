"""
Champion data service for fetching and managing champion information.

This module provides services for fetching champion data specifically
for mid lane champions from Data Dragon and processing their metadata.
"""

import logging
from typing import List, Dict, Optional
from ..models import Champion, Role, ChampionTag, ChampionData
from .riot_api_client import RiotAPIClient

logger = logging.getLogger(__name__)


class ChampionService:
    """Service for managing champion data operations."""
    
    def __init__(self, api_client: RiotAPIClient):
        """
        Initialize the champion service.
        
        Args:
            api_client: Riot API client instance
        """
        self.api_client = api_client
    
    async def get_mid_lane_champions(self, patch: Optional[str] = None) -> List[Champion]:
        """
        Fetch list of champions suitable for mid lane.
        
        Args:
            patch: Game patch version. If None, uses current patch.
            
        Returns:
            List of Champion objects suitable for mid lane
        """
        try:
            champion_data = await self.api_client.get_champion_data(patch)
            mid_lane_champions = []
            
            # Filter champions that are commonly played mid lane
            # This is based on champion tags and known mid lane champions
            mid_lane_tags = {ChampionTag.MAGE, ChampionTag.ASSASSIN}
            
            # Known mid lane champions (including some fighters/marksmen that go mid)
            known_mid_champions = {
                "Yasuo", "Yone", "Zed", "Talon", "Katarina", "Akali", "Fizz",
                "Ahri", "Orianna", "Syndra", "Azir", "Cassiopeia", "Ryze",
                "Twisted Fate", "Veigar", "Annie", "Brand", "Malzahar",
                "Xerath", "Ziggs", "Lux", "Vel'Koz", "Anivia", "Karthus",
                "Corki", "Tristana", "Lucian", "Irelia", "Sylas", "Galio",
                "Diana", "Ekko", "Kassadin", "LeBlanc", "Qiyana", "Viktor",
                "Vladimir", "Swain", "Neeko", "Seraphine", "Vex", "Akshan"
            }
            
            for champ_id, champ_data in champion_data.items():
                # Include if champion has mid lane tags or is in known mid champions
                has_mid_tags = any(tag in mid_lane_tags for tag in champ_data.tags)
                is_known_mid = champ_data.name in known_mid_champions
                
                if has_mid_tags or is_known_mid:
                    champion = Champion(
                        id=champ_data.id,
                        name=champ_data.name,
                        role=Role.MIDDLE,
                        tags=champ_data.tags
                    )
                    mid_lane_champions.append(champion)
            
            logger.info(f"Found {len(mid_lane_champions)} mid lane champions")
            return mid_lane_champions
            
        except Exception as e:
            logger.error(f"Failed to fetch mid lane champions: {e}")
            raise
    
    async def get_champion_by_name(self, name: str, patch: Optional[str] = None) -> Optional[Champion]:
        """
        Get a specific champion by name.
        
        Args:
            name: Champion name
            patch: Game patch version. If None, uses current patch.
            
        Returns:
            Champion object if found, None otherwise
        """
        try:
            champion_data = await self.api_client.get_champion_data(patch)
            
            # Search by name (case insensitive)
            for champ_id, champ_data in champion_data.items():
                if champ_data.name.lower() == name.lower():
                    return Champion(
                        id=champ_data.id,
                        name=champ_data.name,
                        role=Role.MIDDLE,  # MVP: Always mid lane
                        tags=champ_data.tags
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get champion {name}: {e}")
            raise
    
    async def get_champions_by_ids(self, champion_ids: List[str], patch: Optional[str] = None) -> List[Champion]:
        """
        Get multiple champions by their IDs.
        
        Args:
            champion_ids: List of champion IDs
            patch: Game patch version. If None, uses current patch.
            
        Returns:
            List of Champion objects
        """
        try:
            champion_data = await self.api_client.get_champion_data(patch)
            champions = []
            
            for champ_id in champion_ids:
                if champ_id in champion_data:
                    champ_data_obj = champion_data[champ_id]
                    champion = Champion(
                        id=champ_data_obj.id,
                        name=champ_data_obj.name,
                        role=Role.MIDDLE,  # MVP: Always mid lane
                        tags=champ_data_obj.tags
                    )
                    champions.append(champion)
                else:
                    logger.warning(f"Champion ID {champ_id} not found")
            
            return champions
            
        except Exception as e:
            logger.error(f"Failed to get champions by IDs: {e}")
            raise
    
    def parse_champion_metadata(self, champion_data: ChampionData) -> Dict[str, any]:
        """
        Parse champion metadata for additional information.
        
        Args:
            champion_data: Raw champion data from API
            
        Returns:
            Dictionary with parsed metadata
        """
        metadata = {
            "primary_role": self._determine_primary_role(champion_data.tags),
            "damage_type": self._determine_damage_type(champion_data.tags),
            "difficulty": self._estimate_difficulty(champion_data.tags),
            "archetype": self._determine_archetype(champion_data.tags)
        }
        
        return metadata
    
    def _determine_primary_role(self, tags: List[ChampionTag]) -> str:
        """Determine primary role based on champion tags."""
        if ChampionTag.ASSASSIN in tags:
            return "assassin"
        elif ChampionTag.MAGE in tags:
            return "mage"
        elif ChampionTag.FIGHTER in tags:
            return "fighter"
        elif ChampionTag.MARKSMAN in tags:
            return "marksman"
        else:
            return "unknown"
    
    def _determine_damage_type(self, tags: List[ChampionTag]) -> str:
        """Determine primary damage type based on champion tags."""
        if ChampionTag.MAGE in tags:
            return "magic"
        elif ChampionTag.MARKSMAN in tags or ChampionTag.ASSASSIN in tags:
            return "physical"
        elif ChampionTag.FIGHTER in tags:
            return "mixed"
        else:
            return "unknown"
    
    def _estimate_difficulty(self, tags: List[ChampionTag]) -> str:
        """Estimate champion difficulty based on tags."""
        if ChampionTag.ASSASSIN in tags:
            return "high"
        elif ChampionTag.MAGE in tags:
            return "medium"
        elif ChampionTag.FIGHTER in tags:
            return "medium"
        else:
            return "low"
    
    def _determine_archetype(self, tags: List[ChampionTag]) -> str:
        """Determine champion archetype for team composition analysis."""
        if ChampionTag.ASSASSIN in tags:
            return "burst"
        elif ChampionTag.MAGE in tags:
            return "control"
        elif ChampionTag.FIGHTER in tags:
            return "bruiser"
        elif ChampionTag.MARKSMAN in tags:
            return "dps"
        else:
            return "utility"