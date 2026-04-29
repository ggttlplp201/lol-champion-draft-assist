"""Real champion data from Lolalytics via the internal mega API."""

import asyncio
from typing import List, Dict, Optional

import aiohttp

from .manager import DataManager, SimpleCache
from ..models import ChampionStats, MatchData, MatchFilters, UserData, Role, SynergyData, CounterData


_LANE = {
    Role.TOP:     'top',
    Role.JUNGLE:  'jungle',
    Role.MIDDLE:  'middle',
    Role.BOTTOM:  'bottom',
    Role.UTILITY: 'support',
}

_BASE = 'https://a1.lolalytics.com/mega/'
_TIER = 'emerald_plus'
_QUEUE = 'ranked'
_TTL = 86400  # 24 h


class LolatyticsClient(DataManager):
    """
    Fetches champion data from Lolalytics' internal JSON API.

    - fetch_champion_stats: one request for all champions in a lane (ep=tier)
    - fetch_counter_data:   one request per champion in the lane (ep=counter),
                            run in parallel
    - Synergy data: not available; scorer uses hash fallback
    - Region: global Emerald+ (NA regional data returns 404 from Lolalytics)
    """

    def __init__(self, champion_data: dict, patch: str):
        """
        champion_data: {champion_id: {'name': ..., 'key': '<numeric_riot_id>'}}
        patch:         current patch string, e.g. '16.9'
        """
        self._patch = patch
        self.cache = SimpleCache()
        # numeric Riot key → internal champion_id
        self._cid_map: Dict[int, str] = {
            int(info['key']): champ_id
            for champ_id, info in champion_data.items()
            if info.get('key', '').isdigit()
        }

    # ── helpers ────────────────────────────────────────────────

    async def _get(self, session: aiohttp.ClientSession, params: dict) -> Optional[dict]:
        try:
            async with session.get(_BASE, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return None
                data = await r.json(content_type=None)
                if isinstance(data, dict) and data.get('status') == 404:
                    return None
                return data
        except Exception:
            return None

    # ── DataManager interface ───────────────────────────────────

    async def fetch_champion_stats(self, patch: str, role: Role) -> List[ChampionStats]:
        key = f"la2_stats_{role.value}"
        cached = self.cache.get(key)
        if cached:
            return cached

        lane = _LANE[role]
        params = dict(ep='tier', v=1, patch=patch, lane=lane,
                      tier=_TIER, queue=_QUEUE, region='all')

        async with aiohttp.ClientSession() as session:
            data, patch_deltas = await asyncio.gather(
                self._get(session, params),
                self.fetch_patch_deltas(patch),
                return_exceptions=True,
            )

        if not isinstance(data, dict) or 'tier' not in data:
            return []
        if not isinstance(patch_deltas, dict):
            patch_deltas = {}

        # Flatten all tier groups into one champion dict
        champs: dict = {}
        for group in data['tier'].values():
            if isinstance(group, dict):
                cid_data = group.get('lane', {}).get(lane, {}).get('cid', {})
                champs.update(cid_data)

        stats = []
        for cid_str, info in champs.items():
            cid_int = int(cid_str)
            champ_id = self._cid_map.get(cid_int)
            if not champ_id:
                continue
            # Skip off-meta picks: only include champions whose primary lane matches
            if info.get('defaultLane') != lane:
                continue
            # Skip champions with too few games — win rate is statistically unreliable
            if info.get('games', 0) < 500:
                continue
            try:
                stats.append(ChampionStats(
                    champion_id=champ_id,
                    role=role,
                    win_rate=float(info['wr']) / 100,
                    pick_rate=float(info['pr']) / 100,
                    ban_rate=float(info.get('br', 0)) / 100,
                    patch=patch,
                    rank_tier='EMERALD+',
                    patch_delta_wr=patch_deltas.get(cid_int),
                ))
            except (KeyError, ValueError, TypeError):
                continue

        if stats:
            self.cache.set(key, stats, _TTL)
        return stats

    async def fetch_counter_data(self, patch: str, role: Role) -> List[CounterData]:
        key = f"la2_counters_{role.value}"
        cached = self.cache.get(key)
        if cached:
            return cached

        lane = _LANE[role]

        # Get champion list for this role from champion stats cache (or fetch it)
        champ_stats = await self.fetch_champion_stats(patch, role)
        champ_ids = [s.champion_id for s in champ_stats]
        if not champ_ids:
            return []

        # Build reverse map: champion_id → numeric cid
        id_to_cid = {v: k for k, v in self._cid_map.items()}

        async def fetch_one(session: aiohttp.ClientSession, champ_id: str) -> List[CounterData]:
            cid = id_to_cid.get(champ_id)
            if cid is None:
                return []
            # Lolalytics uses slug format (no underscores) for the c= param
            slug = champ_id.replace('_', '')
            if champ_id == 'renata_glasc':
                slug = 'renata'
            params = dict(ep='counter', v=1, patch=patch, c=slug, lane=lane,
                          tier=_TIER, queue=_QUEUE, region='all')
            data = await self._get(session, params)
            if not data or 'counters' not in data:
                return []

            results = []
            for entry in data['counters']:
                enemy_cid = entry.get('cid')
                enemy_id = self._cid_map.get(enemy_cid)
                if not enemy_id:
                    continue
                vs_wr = entry.get('vsWr')
                if vs_wr is None:
                    continue
                win_rate_a = float(vs_wr) / 100
                # d1 = vsWr - enemy's allWr: positive means we out-perform expectation
                d1 = entry.get('d1')
                results.append(CounterData(
                    champion_a=champ_id,
                    champion_b=enemy_id,
                    role_a=role, role_b=role,
                    win_rate_a=win_rate_a,
                    win_rate_b=1.0 - win_rate_a,
                    sample_size=int(entry.get('n', 0)),
                    patch=patch,
                    relative_advantage=float(d1) if d1 is not None else None,
                ))
            return results

        async with aiohttp.ClientSession() as session:
            all_results = await asyncio.gather(
                *[fetch_one(session, cid) for cid in champ_ids],
                return_exceptions=True,
            )

        counter_data: List[CounterData] = []
        for result in all_results:
            if isinstance(result, list):
                counter_data.extend(result)

        if counter_data:
            self.cache.set(key, counter_data, _TTL)
        return counter_data

    async def fetch_patch_deltas(self, patch: str) -> Dict[int, float]:
        """
        Return {cid: deltaWr} for champions with significant patch changes.
        Uses ep=front which lists recently buffed/nerfed champions.
        Cached for 24h; returns empty dict on failure.
        """
        key = f"la2_front_{patch}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        params = dict(ep='front', v=1, patch=patch,
                      tier=_TIER, queue=_QUEUE, region='all')
        async with aiohttp.ClientSession() as session:
            data = await self._get(session, params)

        if not data or 'changes' not in data:
            return {}

        deltas: Dict[int, float] = {}
        changes = data['changes']
        for category in ('buffs', 'nerfs', 'adjusted'):
            for entry in changes.get(category, []):
                cid = entry.get('cid')
                dwr = entry.get('deltaWr')
                if cid is not None and dwr is not None:
                    deltas[int(cid)] = float(dwr)

        self.cache.set(key, deltas, _TTL)
        return deltas

    async def fetch_champion_detail(self, patch: str, champion_id: str, role: Role) -> dict:
        """Fetch item and rune data from Lolalytics."""
        cache_key = f"la2_detail_{champion_id}_{role.value}_{patch}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        lane = _LANE[role]
        slug = champion_id.replace('_', '')
        if champion_id == 'renata_glasc':
            slug = 'renata'

        rune_params = dict(ep='rune', v=1, patch=patch, c=slug, lane=lane,
                           tier=_TIER, queue=_QUEUE, region='all')
        build_url = (f'https://lolalytics.com/lol/{slug}/build/q-data.json'
                     f'?lane={lane}&tier={_TIER}&patch={patch}')

        _hdrs = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        async with aiohttp.ClientSession(headers=_hdrs) as session:
            rune_task  = self._get(session, rune_params)
            build_task = self._get_url(session, build_url)
            rune_data, build_data = await asyncio.gather(rune_task, build_task,
                                                         return_exceptions=True)

        result: dict = {}
        if isinstance(rune_data, dict):
            result['runes'] = self._parse_runes(rune_data)
        if isinstance(build_data, dict):
            result['items'] = self._parse_items_qwik(build_data)
            result['game_length_wr'] = self._parse_game_length_wr(build_data)

        self.cache.set(cache_key, result, _TTL)
        return result

    async def _get_url(self, session: aiohttp.ClientSession, url: str) -> Optional[dict]:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return None
                return await r.json(content_type=None)
        except Exception:
            return None

    @staticmethod
    def _b36(s: str) -> int:
        """Decode a Qwik reference string (base-36) to an int index."""
        n = 0
        for c in s:
            n = n * 36 + (int(c) if c.isdigit() else ord(c) - ord('a') + 10)
        return n

    def _qwik_resolve(self, objs: list, val, depth: int = 0):
        """Recursively resolve Qwik object references."""
        if depth > 10:
            return val
        if isinstance(val, str):
            try:
                idx = self._b36(val)
                if 0 <= idx < len(objs):
                    return self._qwik_resolve(objs, objs[idx], depth + 1)
            except Exception:
                pass
            return val
        if isinstance(val, dict):
            return {k: self._qwik_resolve(objs, v, depth + 1) for k, v in val.items()}
        if isinstance(val, list):
            return [self._qwik_resolve(objs, x, depth + 1) for x in val]
        return val

    def _parse_items_qwik(self, data: dict) -> list:
        """Extract the recommended item build from the Lolalytics q-data.json Qwik payload."""
        objs = data.get('_objs', [])
        if not objs:
            return []

        # Build reverse map: Qwik code → numeric item ID
        # The global item dict (maps item_id_str → short_code) is a large dict in objs
        code_to_item: dict[str, int] = {}
        for obj in objs:
            if isinstance(obj, dict) and '1001' in obj and '3814' in obj and len(obj) > 100:
                for item_id_str, code in obj.items():
                    if item_id_str.isdigit() and int(item_id_str) < 10000:
                        code_to_item[code] = int(item_id_str)
                break

        # Find the champion build data: dict with {start, core, item4, item5, item6}
        build_obj_ref = None
        for obj in objs:
            if isinstance(obj, dict) and 'core' in obj and 'start' in obj and 'item4' in obj:
                build_obj_ref = obj
                break

        if build_obj_ref is None or not code_to_item:
            return []

        # Extract core items (most-played build path)
        core_ref = build_obj_ref.get('core')
        if not core_ref:
            return []

        try:
            core_idx = self._b36(core_ref)
            core_obj = objs[core_idx]  # {'set': ref, 'wr': ref, 'n': ref}
            if not isinstance(core_obj, dict):
                return []

            set_idx = self._b36(core_obj['set'])
            set_list = objs[set_idx]  # list of item code refs
            wr_idx = self._b36(core_obj['wr'])
            n_idx = self._b36(core_obj['n'])

            item_ids = []
            for code_ref in set_list:
                item_code_idx = self._b36(code_ref)
                item_code = objs[item_code_idx] if 0 <= item_code_idx < len(objs) else None
                if isinstance(item_code, str) and item_code in code_to_item:
                    item_ids.append(code_to_item[item_code])
                elif isinstance(item_code, int) and 1000 <= item_code <= 9999:
                    item_ids.append(item_code)

            wr = objs[wr_idx] if 0 <= wr_idx < len(objs) else 0
            n = objs[n_idx] if 0 <= n_idx < len(objs) else 0

            if not item_ids:
                return []

            return [{'id': iid, 'wr': round(float(wr), 1), 'n': int(n)}
                    for iid in item_ids if 1000 <= iid <= 9999]

        except Exception:
            return []

    def _parse_game_length_wr(self, data: dict) -> list:
        """
        Extract win rate by game-length bucket from q-data.json.
        Returns list of (bucket, win_rate%) for 7 Lolalytics time buckets:
          1=<20m, 2=20-25m, 3=25-30m, 4=30-35m, 5=35-40m, 6=40-45m, 7=45+m
        """
        objs = data.get('_objs', [])
        if not objs:
            return []
        try:
            # Find the {time: ref, timeWin: ref} object
            time_obj = None
            for obj in objs:
                if isinstance(obj, dict) and 'time' in obj and 'timeWin' in obj and len(obj) == 2:
                    time_obj = obj
                    break
            if not time_obj:
                return []

            counts_ref = self._b36(time_obj['time'])
            wins_ref   = self._b36(time_obj['timeWin'])
            counts_dict = objs[counts_ref]  # {1: ref, 2: ref, ...}
            wins_dict   = objs[wins_ref]

            result = []
            for bucket_str in sorted(counts_dict.keys(), key=int):
                n = objs[self._b36(counts_dict[bucket_str])]
                w = objs[self._b36(wins_dict[bucket_str])]
                if isinstance(n, int) and isinstance(w, int) and n > 0:
                    wr = round(w / n * 100, 1)
                    result.append({'bucket': int(bucket_str), 'wr': wr, 'n': n})
            return result
        except Exception:
            return []

    def _parse_runes(self, data: dict) -> dict:
        """Extract the most-picked rune page from ep=rune response."""
        try:
            pick_set = data['summary']['runes']['pick']['set']
            return {
                'pri': pick_set.get('pri', []),
                'sec': pick_set.get('sec', []),
                'mod': pick_set.get('mod', []),
                'wr':  round(float(data['summary']['runes']['pick'].get('wr', 0)), 1),
                'n':   int(data['summary']['runes']['pick'].get('n', 0)),
            }
        except (KeyError, TypeError, ValueError):
            return {}

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
