"""Real champion data from Lolalytics via the lolalytics-api scraper."""

import json
import asyncio
from typing import List, Optional, Dict

from .manager import DataManager, SimpleCache
from ..models import ChampionStats, MatchData, MatchFilters, UserData, Role, SynergyData, CounterData

try:
    import lolalytics_api as la
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


_ROLE_LANE = {
    Role.TOP:     'top',
    Role.JUNGLE:  'jungle',
    Role.MIDDLE:  'mid',
    Role.BOTTOM:  'adc',
    Role.UTILITY: 'support',
}

_ROLE_KEY = {
    Role.TOP:     'top',
    Role.JUNGLE:  'jungle',
    Role.MIDDLE:  'mid',
    Role.BOTTOM:  'bottom',
    Role.UTILITY: 'support',
}

# lolalytics URL slug = champion_id with underscores removed, except these
_SLUG_EXCEPTIONS = {
    'renata_glasc': 'renata',
}

_TTL = 86400  # 24 h cache


def _to_slug(champion_id: str) -> str:
    return _SLUG_EXCEPTIONS.get(champion_id, champion_id.replace('_', ''))


class LolatyticsClient(DataManager):
    """
    Fetches real win/pick/ban rates and counter matchup data from Lolalytics.
    Uses get_champion_data() and get_counters() — the two reliable endpoints.
    Synergy data is not available; the scorer's hash fallback handles it.
    """

    def __init__(self, champion_data: dict, champions_by_role: dict):
        if not _AVAILABLE:
            raise ImportError("lolalytics_api not installed — run: pip install lolalytics-api")
        self._champions_by_role = champions_by_role
        self.cache = SimpleCache()
        self._name_to_id: Dict[str, str] = {
            info['name']: cid for cid, info in champion_data.items()
        }
        self._id_to_name: Dict[str, str] = {
            cid: info['name'] for cid, info in champion_data.items()
        }

    def _cid(self, name: str) -> Optional[str]:
        return self._name_to_id.get(name)

    @staticmethod
    def _parse_pct(s) -> float:
        try:
            return float(str(s).replace('%', '').strip()) / 100
        except (ValueError, AttributeError):
            return 0.0

    # ── sync wrappers (safe for run_in_executor) ───────────────

    def _fetch_champ_detail(self, champion_id: str, lane: str) -> Optional[dict]:
        try:
            slug = _to_slug(champion_id)
            data = json.loads(la.get_champion_data(slug, lane=lane))
            return {
                'win_rate':  self._parse_pct(data.get('winrate', '50%')),
                'pick_rate': self._parse_pct(data.get('pickrate', '5%')),
                'ban_rate':  self._parse_pct(data.get('banrate', '3%')),
            }
        except Exception:
            return None

    def _fetch_counters_for(self, champion_id: str) -> list:
        try:
            slug = _to_slug(champion_id)
            return list(json.loads(la.get_counters(n=60, champion=slug)).values())
        except Exception:
            return []

    # ── DataManager interface ──────────────────────────────────

    async def fetch_champion_stats(self, patch: str, role: Role) -> List[ChampionStats]:
        key = f"la_stats_{role.value}"
        cached = self.cache.get(key)
        if cached:
            return cached

        lane = _ROLE_LANE[role]
        role_key = _ROLE_KEY[role]
        champ_ids = [cid for cid, *_ in self._champions_by_role.get(role_key, [])
                     if cid in self._id_to_name]

        if not champ_ids:
            return []

        loop = asyncio.get_event_loop()
        details = await asyncio.gather(
            *[loop.run_in_executor(None, self._fetch_champ_detail, cid, lane)
              for cid in champ_ids],
            return_exceptions=True,
        )

        stats = []
        for cid, detail in zip(champ_ids, details):
            if not detail or isinstance(detail, Exception):
                continue
            stats.append(ChampionStats(
                champion_id=cid,
                role=role,
                win_rate=detail['win_rate'],
                pick_rate=detail['pick_rate'],
                ban_rate=detail['ban_rate'],
                patch=patch,
                rank_tier='EMERALD',
            ))

        if stats:
            self.cache.set(key, stats, _TTL)
        return stats

    async def fetch_counter_data(self, patch: str, role: Role) -> List[CounterData]:
        key = f"la_counters_{role.value}"
        cached = self.cache.get(key)
        if cached:
            return cached

        role_key = _ROLE_KEY[role]
        champ_ids = [cid for cid, *_ in self._champions_by_role.get(role_key, [])
                     if cid in self._id_to_name]

        if not champ_ids:
            return []

        loop = asyncio.get_event_loop()
        all_entries = await asyncio.gather(
            *[loop.run_in_executor(None, self._fetch_counters_for, cid)
              for cid in champ_ids],
            return_exceptions=True,
        )

        counter_data: List[CounterData] = []
        for cid, entries in zip(champ_ids, all_entries):
            if isinstance(entries, Exception):
                continue
            for entry in entries:
                enemy_id = self._cid(entry.get('champion', ''))
                if not enemy_id:
                    continue
                try:
                    win_rate_a = float(entry['winrate']) / 100
                except (KeyError, ValueError):
                    continue
                counter_data.append(CounterData(
                    champion_a=cid,
                    champion_b=enemy_id,
                    role_a=role, role_b=role,
                    win_rate_a=win_rate_a,
                    win_rate_b=1.0 - win_rate_a,
                    sample_size=500,
                    patch=patch,
                ))

        if counter_data:
            self.cache.set(key, counter_data, _TTL)
        return counter_data

    async def fetch_synergy_data(self, patch: str, role_a: Role, role_b: Role) -> List[SynergyData]:
        return []  # not available — scorer uses hash fallback

    async def fetch_match_data(self, filters: MatchFilters) -> List[MatchData]:
        return []

    def get_cached_data(self, key: str):
        return self.cache.get(key)

    def set_cached_data(self, key: str, data, ttl: int):
        self.cache.set(key, data, ttl)

    async def save_user_data(self, user_data) -> None:
        pass

    async def load_user_data(self):
        return None
