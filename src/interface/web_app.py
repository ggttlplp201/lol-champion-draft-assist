"""Web interface for the Champion Draft Assist Tool."""

import asyncio
import json
import os
import requests as _requests
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from typing import List

from ..models import (
    Champion, DraftState, Role, ChampionTag,
    ChampionRecommendation, ChampionStats, SynergyData, CounterData
)
from ..engine import StandardSuggestionEngine
from ..data.manager import DataManager, SimpleCache
from ..scoring.scorer import StandardScorer


_ITEM_NAMES: dict = {}   # {item_id_int: name_str}
_RUNE_NAMES: dict = {}   # {rune_id_int: name_str}


def _enrich_champion_data_with_keys(champion_data: dict) -> tuple:
    """Fetch DDragon to add 'key'+'tags' to each entry.
    Returns (short_patch, dd_key_map) where dd_key_map is {int_key: id_str} for all champions."""
    global _ITEM_NAMES, _RUNE_NAMES
    dd_key_map: dict = {}
    try:
        versions = _requests.get(
            'https://ddragon.leagueoflegends.com/api/versions.json', timeout=5
        ).json()
        patch = versions[0]

        champ_json = _requests.get(
            f'https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/champion.json',
            timeout=10,
        ).json()
        for entry in champ_json['data'].values():
            if entry.get('key', '').isdigit():
                dd_key_map[int(entry['key'])] = entry['id']
            name = entry['name']
            for cid, info in champion_data.items():
                if info['name'] == name:
                    info['key']  = entry['key']
                    info['tags'] = entry.get('tags', [])
                    break

        # Item ID → name
        try:
            item_json = _requests.get(
                f'https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/item.json',
                timeout=10,
            ).json()
            _ITEM_NAMES = {int(k): v['name'] for k, v in item_json['data'].items()}
        except Exception:
            pass

        # Rune ID → name
        try:
            rune_json = _requests.get(
                f'https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/runesReforged.json',
                timeout=10,
            ).json()
            for path in rune_json:
                _RUNE_NAMES[path['id']] = path['name']
                for slot in path.get('slots', []):
                    for rune in slot.get('runes', []):
                        _RUNE_NAMES[rune['id']] = rune['name']
        except Exception:
            pass

        parts = patch.split('.')
        return f"{parts[0]}.{parts[1]}", dd_key_map
    except Exception as e:
        print(f'DDragon enrichment failed: {e}')
        return '16.9', {}


# Power-curve heuristic from DDragon champion tags
_POWER_CURVES = {
    'Assassin':  [52, 72, 82, 68, 55],
    'Fighter':   [60, 74, 76, 68, 62],
    'Tank':      [44, 55, 66, 78, 84],
    'Mage':      [40, 62, 80, 72, 62],
    'Marksman':  [28, 48, 68, 84, 90],
    'Support':   [46, 56, 62, 66, 68],
    'Slayer':    [52, 72, 82, 68, 55],
    'Catcher':   [46, 58, 66, 68, 66],
    'Enchanter': [42, 55, 62, 66, 70],
    'Warden':    [44, 55, 66, 78, 84],
    'Juggernaut':[58, 68, 74, 78, 80],
    'Diver':     [58, 72, 74, 66, 60],
    'Specialist':[50, 62, 70, 68, 65],
}
_DEFAULT_CURVE = [50, 62, 72, 70, 65]


def _power_curve(champion_id: str) -> list:
    tags = CHAMPION_DATA.get(champion_id, {}).get('tags', [])
    for tag in tags:
        if tag in _POWER_CURVES:
            return _POWER_CURVES[tag]
    return _DEFAULT_CURVE


def _team_curve(champion_ids: list) -> list:
    curves = [_power_curve(c) for c in champion_ids if c in CHAMPION_DATA]
    if not curves:
        return _DEFAULT_CURVE
    return [round(sum(c[i] for c in curves) / len(curves)) for i in range(5)]


ROLE_MAP = {
    'top':     Role.TOP,
    'jungle':  Role.JUNGLE,
    'mid':     Role.MIDDLE,
    'middle':  Role.MIDDLE,
    'bottom':  Role.BOTTOM,
    'adc':     Role.BOTTOM,
    'support': Role.UTILITY,
    'utility': Role.UTILITY,
}

CHAMPION_DATA = {
    # Top
    'aatrox': {'name': 'Aatrox'},
    'camille': {'name': 'Camille'},
    'cho_gath': {'name': "Cho'Gath"},
    'darius': {'name': 'Darius'},
    'fiora': {'name': 'Fiora'},
    'garen': {'name': 'Garen'},
    'gnar': {'name': 'Gnar'},
    'illaoi': {'name': 'Illaoi'},
    'jax': {'name': 'Jax'},
    'kennen': {'name': 'Kennen'},
    'k_sante': {'name': "K'Sante"},
    'malphite': {'name': 'Malphite'},
    'maokai': {'name': 'Maokai'},
    'mordekaiser': {'name': 'Mordekaiser'},
    'nasus': {'name': 'Nasus'},
    'ornn': {'name': 'Ornn'},
    'pantheon': {'name': 'Pantheon'},
    'renekton': {'name': 'Renekton'},
    'riven': {'name': 'Riven'},
    'sett': {'name': 'Sett'},
    'shen': {'name': 'Shen'},
    'singed': {'name': 'Singed'},
    'teemo': {'name': 'Teemo'},
    'tryndamere': {'name': 'Tryndamere'},
    'urgot': {'name': 'Urgot'},
    'volibear': {'name': 'Volibear'},
    'wukong': {'name': 'Wukong'},
    # Jungle
    'amumu': {'name': 'Amumu'},
    'diana': {'name': 'Diana'},
    'ekko': {'name': 'Ekko'},
    'evelynn': {'name': 'Evelynn'},
    'fiddlesticks': {'name': 'Fiddlesticks'},
    'graves': {'name': 'Graves'},
    'hecarim': {'name': 'Hecarim'},
    'jarvan_iv': {'name': 'Jarvan IV'},
    'kayn': {'name': 'Kayn'},
    'kha_zix': {'name': "Kha'Zix"},
    'kindred': {'name': 'Kindred'},
    'lee_sin': {'name': 'Lee Sin'},
    'lillia': {'name': 'Lillia'},
    'master_yi': {'name': 'Master Yi'},
    'nidalee': {'name': 'Nidalee'},
    'nocturne': {'name': 'Nocturne'},
    'rammus': {'name': 'Rammus'},
    'sejuani': {'name': 'Sejuani'},
    'shaco': {'name': 'Shaco'},
    'taliyah': {'name': 'Taliyah'},
    'udyr': {'name': 'Udyr'},
    'vi': {'name': 'Vi'},
    'viego': {'name': 'Viego'},
    'warwick': {'name': 'Warwick'},
    'zac': {'name': 'Zac'},
    # Mid
    'ahri': {'name': 'Ahri'},
    'akali': {'name': 'Akali'},
    'anivia': {'name': 'Anivia'},
    'annie': {'name': 'Annie'},
    'azir': {'name': 'Azir'},
    'brand': {'name': 'Brand'},
    'cassiopeia': {'name': 'Cassiopeia'},
    'corki': {'name': 'Corki'},
    'fizz': {'name': 'Fizz'},
    'galio': {'name': 'Galio'},
    'irelia': {'name': 'Irelia'},
    'kassadin': {'name': 'Kassadin'},
    'katarina': {'name': 'Katarina'},
    'leblanc': {'name': 'LeBlanc'},
    'lissandra': {'name': 'Lissandra'},
    'lux': {'name': 'Lux'},
    'malzahar': {'name': 'Malzahar'},
    'neeko': {'name': 'Neeko'},
    'orianna': {'name': 'Orianna'},
    'qiyana': {'name': 'Qiyana'},
    'ryze': {'name': 'Ryze'},
    'sylas': {'name': 'Sylas'},
    'syndra': {'name': 'Syndra'},
    'talon': {'name': 'Talon'},
    'twisted_fate': {'name': 'Twisted Fate'},
    'veigar': {'name': 'Veigar'},
    'vel_koz': {'name': "Vel'Koz"},
    'viktor': {'name': 'Viktor'},
    'vladimir': {'name': 'Vladimir'},
    'xerath': {'name': 'Xerath'},
    'yasuo': {'name': 'Yasuo'},
    'yone': {'name': 'Yone'},
    'zed': {'name': 'Zed'},
    'ziggs': {'name': 'Ziggs'},
    # ADC
    'aphelios': {'name': 'Aphelios'},
    'ashe': {'name': 'Ashe'},
    'caitlyn': {'name': 'Caitlyn'},
    'draven': {'name': 'Draven'},
    'ezreal': {'name': 'Ezreal'},
    'jhin': {'name': 'Jhin'},
    'jinx': {'name': 'Jinx'},
    'kai_sa': {'name': "Kai'Sa"},
    'kog_maw': {'name': "Kog'Maw"},
    'lucian': {'name': 'Lucian'},
    'miss_fortune': {'name': 'Miss Fortune'},
    'nilah': {'name': 'Nilah'},
    'samira': {'name': 'Samira'},
    'sivir': {'name': 'Sivir'},
    'tristana': {'name': 'Tristana'},
    'twitch': {'name': 'Twitch'},
    'varus': {'name': 'Varus'},
    'vayne': {'name': 'Vayne'},
    'xayah': {'name': 'Xayah'},
    'zeri': {'name': 'Zeri'},
    # Support
    'bard': {'name': 'Bard'},
    'blitzcrank': {'name': 'Blitzcrank'},
    'janna': {'name': 'Janna'},
    'karma': {'name': 'Karma'},
    'leona': {'name': 'Leona'},
    'lulu': {'name': 'Lulu'},
    'milio': {'name': 'Milio'},
    'morgana': {'name': 'Morgana'},
    'nami': {'name': 'Nami'},
    'nautilus': {'name': 'Nautilus'},
    'renata_glasc': {'name': 'Renata Glasc'},
    'seraphine': {'name': 'Seraphine'},
    'senna': {'name': 'Senna'},
    'sona': {'name': 'Sona'},
    'soraka': {'name': 'Soraka'},
    'taric': {'name': 'Taric'},
    'thresh': {'name': 'Thresh'},
    'yuumi': {'name': 'Yuumi'},
    'zilean': {'name': 'Zilean'},
    'zyra': {'name': 'Zyra'},
}

# (champion_id, win_rate, pick_rate, ban_rate)
CHAMPIONS_BY_ROLE = {
    'top': [
        ('darius',      0.513, 0.090, 0.050),
        ('garen',       0.528, 0.060, 0.020),
        ('malphite',    0.543, 0.080, 0.040),
        ('camille',     0.503, 0.070, 0.060),
        ('fiora',       0.512, 0.100, 0.070),
        ('jax',         0.508, 0.080, 0.040),
        ('nasus',       0.492, 0.070, 0.020),
        ('teemo',       0.514, 0.050, 0.030),
        ('urgot',       0.523, 0.060, 0.030),
        ('volibear',    0.503, 0.070, 0.030),
        ('sett',        0.519, 0.080, 0.040),
        ('mordekaiser', 0.532, 0.100, 0.060),
        ('tryndamere',  0.502, 0.060, 0.030),
        ('renekton',    0.511, 0.070, 0.040),
        ('cho_gath',    0.504, 0.060, 0.020),
        ('illaoi',      0.521, 0.070, 0.030),
        ('irelia',      0.491, 0.090, 0.080),
        ('kennen',      0.503, 0.040, 0.020),
        ('maokai',      0.534, 0.060, 0.030),
        ('pantheon',    0.503, 0.050, 0.030),
        ('shen',        0.522, 0.070, 0.030),
        ('singed',      0.512, 0.040, 0.020),
        ('wukong',      0.513, 0.060, 0.030),
        ('aatrox',      0.496, 0.100, 0.060),
        ('k_sante',     0.487, 0.080, 0.070),
        ('riven',       0.494, 0.080, 0.040),
        ('ornn',        0.518, 0.060, 0.020),
        ('gnar',        0.492, 0.050, 0.020),
    ],
    'jungle': [
        ('warwick',      0.541, 0.070, 0.040),
        ('rammus',       0.549, 0.050, 0.030),
        ('amumu',        0.532, 0.090, 0.070),
        ('zac',          0.528, 0.070, 0.050),
        ('fiddlesticks', 0.518, 0.060, 0.050),
        ('udyr',         0.531, 0.050, 0.030),
        ('master_yi',    0.521, 0.080, 0.060),
        ('nocturne',     0.519, 0.070, 0.070),
        ('hecarim',      0.512, 0.070, 0.040),
        ('vi',           0.521, 0.060, 0.030),
        ('sejuani',      0.511, 0.060, 0.030),
        ('jarvan_iv',    0.502, 0.050, 0.020),
        ('kayn',         0.509, 0.110, 0.050),
        ('kha_zix',      0.508, 0.100, 0.080),
        ('ekko',         0.521, 0.080, 0.040),
        ('graves',       0.511, 0.080, 0.050),
        ('lee_sin',      0.491, 0.140, 0.060),
        ('shaco',        0.502, 0.070, 0.080),
        ('diana',        0.508, 0.070, 0.040),
        ('viego',        0.501, 0.090, 0.050),
        ('lillia',       0.509, 0.060, 0.030),
        ('nidalee',      0.491, 0.060, 0.030),
        ('kindred',      0.498, 0.050, 0.040),
        ('evelynn',      0.508, 0.060, 0.070),
        ('taliyah',      0.511, 0.040, 0.030),
    ],
    'mid': [
        ('sylas',        0.540, 0.090, 0.070),
        ('orianna',      0.520, 0.070, 0.040),
        ('ahri',         0.510, 0.120, 0.050),
        ('katarina',     0.490, 0.080, 0.060),
        ('azir',         0.480, 0.060, 0.040),
        ('cassiopeia',   0.500, 0.050, 0.020),
        ('diana',        0.530, 0.060, 0.040),
        ('fizz',         0.510, 0.070, 0.060),
        ('leblanc',      0.490, 0.100, 0.090),
        ('lissandra',    0.480, 0.050, 0.030),
        ('malzahar',     0.520, 0.060, 0.040),
        ('yasuo',        0.500, 0.150, 0.120),
        ('syndra',       0.490, 0.070, 0.050),
        ('talon',        0.510, 0.070, 0.040),
        ('twisted_fate', 0.480, 0.060, 0.040),
        ('veigar',       0.500, 0.070, 0.030),
        ('viktor',       0.490, 0.070, 0.040),
        ('xerath',       0.480, 0.050, 0.030),
        ('ziggs',        0.470, 0.040, 0.020),
        ('akali',        0.500, 0.090, 0.110),
        ('anivia',       0.490, 0.040, 0.020),
        ('annie',        0.510, 0.040, 0.020),
        ('brand',        0.480, 0.040, 0.030),
        ('corki',        0.470, 0.040, 0.020),
        ('ekko',         0.520, 0.080, 0.040),
        ('galio',        0.490, 0.050, 0.040),
        ('irelia',       0.500, 0.070, 0.070),
        ('kassadin',     0.480, 0.060, 0.050),
        ('lux',          0.510, 0.080, 0.030),
        ('neeko',        0.490, 0.040, 0.020),
        ('qiyana',       0.470, 0.050, 0.040),
        ('ryze',         0.460, 0.050, 0.030),
        ('zed',          0.510, 0.120, 0.100),
        ('vel_koz',      0.490, 0.050, 0.030),
        ('vladimir',     0.500, 0.070, 0.040),
        ('yone',         0.490, 0.110, 0.090),
    ],
    'bottom': [
        ('jinx',         0.521, 0.120, 0.090),
        ('caitlyn',      0.513, 0.130, 0.070),
        ('jhin',         0.524, 0.110, 0.060),
        ('ashe',         0.513, 0.100, 0.040),
        ('ezreal',       0.502, 0.150, 0.040),
        ('vayne',        0.509, 0.100, 0.080),
        ('kai_sa',       0.513, 0.120, 0.090),
        ('sivir',        0.519, 0.080, 0.030),
        ('draven',       0.501, 0.070, 0.050),
        ('miss_fortune', 0.522, 0.090, 0.040),
        ('tristana',     0.508, 0.070, 0.040),
        ('lucian',       0.502, 0.090, 0.060),
        ('aphelios',     0.501, 0.080, 0.060),
        ('twitch',       0.509, 0.050, 0.040),
        ('kog_maw',      0.518, 0.050, 0.030),
        ('samira',       0.511, 0.090, 0.100),
        ('zeri',         0.502, 0.070, 0.050),
        ('nilah',        0.509, 0.050, 0.020),
        ('xayah',        0.511, 0.080, 0.050),
        ('varus',        0.501, 0.060, 0.030),
    ],
    'support': [
        ('soraka',       0.541, 0.080, 0.070),
        ('janna',        0.532, 0.070, 0.040),
        ('lulu',         0.528, 0.090, 0.060),
        ('nami',         0.533, 0.080, 0.040),
        ('seraphine',    0.518, 0.070, 0.050),
        ('nautilus',     0.519, 0.110, 0.080),
        ('thresh',       0.512, 0.160, 0.070),
        ('blitzcrank',   0.518, 0.100, 0.090),
        ('leona',        0.512, 0.110, 0.060),
        ('morgana',      0.533, 0.100, 0.070),
        ('sona',         0.529, 0.060, 0.040),
        ('karma',        0.521, 0.070, 0.030),
        ('milio',        0.518, 0.060, 0.040),
        ('zilean',       0.521, 0.040, 0.020),
        ('bard',         0.509, 0.070, 0.040),
        ('yuumi',        0.501, 0.070, 0.150),
        ('senna',        0.512, 0.080, 0.050),
        ('taric',        0.512, 0.030, 0.010),
        ('zyra',         0.519, 0.050, 0.040),
        ('renata_glasc', 0.509, 0.040, 0.030),
    ],
}


class MockDataManager(DataManager):

    def __init__(self):
        self.cache = SimpleCache()

    async def fetch_champion_stats(self, patch: str, role: Role) -> List[ChampionStats]:
        role_key = next((k for k, v in ROLE_MAP.items() if v == role), 'mid')
        champs = CHAMPIONS_BY_ROLE.get(role_key, CHAMPIONS_BY_ROLE['mid'])
        return [
            ChampionStats(
                champion_id=cid, role=role,
                win_rate=wr, pick_rate=pr, ban_rate=br,
                patch=patch, rank_tier='GOLD',
            )
            for cid, wr, pr, br in champs
        ]

    async def fetch_match_data(self, filters):
        return []

    async def fetch_synergy_data(self, patch: str, role_a: Role, role_b: Role):
        pairs = {
            ('sylas', 'jinx'): 0.08, ('orianna', 'jinx'): 0.06,
            ('ahri', 'jinx'): 0.05, ('malzahar', 'jinx'): 0.04,
            ('diana', 'yasuo'): 0.10, ('malzahar', 'yasuo'): 0.08,
            ('orianna', 'yasuo'): 0.07, ('orianna', 'ashe'): 0.06,
            ('syndra', 'jinx'): 0.05, ('xerath', 'caitlyn'): 0.04,
            ('amumu', 'miss_fortune'): 0.09, ('leona', 'jinx'): 0.07,
            ('thresh', 'lucian'): 0.08, ('lulu', 'kai_sa'): 0.07,
        }
        return [
            SynergyData(
                champion_pair=(a, b), role1=role_a, role2=role_b,
                combined_win_rate=0.52 + d, expected_win_rate=0.52,
                synergy_delta=d, sample_size=1000, patch=patch,
            )
            for (a, b), d in pairs.items()
        ]

    async def fetch_counter_data(self, patch: str, role: Role):
        matchups = {
            ('zed', 'xerath'): 0.58, ('zed', 'vel_koz'): 0.57,
            ('katarina', 'malzahar'): 0.45, ('yasuo', 'malzahar'): 0.42,
            ('malzahar', 'zed'): 0.58, ('malzahar', 'katarina'): 0.60,
            ('lissandra', 'zed'): 0.55, ('annie', 'katarina'): 0.56,
            ('xerath', 'diana'): 0.54, ('vel_koz', 'fizz'): 0.53,
            ('diana', 'xerath'): 0.58, ('fizz', 'vel_koz'): 0.59,
            ('darius', 'fiora'): 0.54, ('malphite', 'fiora'): 0.57,
            ('vayne', 'malphite'): 0.56, ('caitlyn', 'blitzcrank'): 0.54,
            ('jinx', 'leona'): 0.52, ('soraka', 'blitzcrank'): 0.55,
        }
        return [
            CounterData(
                champion_a=a, champion_b=b, role_a=role, role_b=role,
                win_rate_a=wr, win_rate_b=1.0 - wr, sample_size=500, patch=patch,
            )
            for (a, b), wr in matchups.items()
        ]

    def get_cached_data(self, key):
        return self.cache.get(key)

    def set_cached_data(self, key, data, ttl):
        self.cache.set(key, data, ttl)

    async def save_user_data(self, user_data):
        pass

    async def load_user_data(self):
        return None


import sys as _sys
if getattr(_sys, 'frozen', False):
    # Running as PyInstaller bundle — all data lands in sys._MEIPASS
    _base = _sys._MEIPASS
else:
    _base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
template_dir = os.path.join(_base, 'templates')
static_dir   = os.path.join(_base, 'static')
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = 'draft_advisor_secret_key'

_mock = MockDataManager()
_current_patch, _dd_key_map = _enrich_champion_data_with_keys(CHAMPION_DATA)
try:
    from ..data.lolalytics_client import LolatyticsClient
    data_manager = LolatyticsClient(CHAMPION_DATA, _current_patch)
    print(f'Using Lolalytics real data (patch {_current_patch}, global Emerald+)')
except Exception as e:
    print(f'Lolalytics unavailable ({e}) — using mock data')
    data_manager = _mock

scorer = StandardScorer()
engine = StandardSuggestionEngine(data_manager, scorer)

# ── LCU champion key map ───────────────────────────────────────────────────
# Start with DDragon's full map (PascalCase IDs for new/unknown champions),
# then override with our internal IDs for known champions so role inference
# and portrait URLs use the right keys.
_champ_key_map: dict = dict(_dd_key_map)
for _cid, _info in CHAMPION_DATA.items():
    if _info.get('key', '').isdigit():
        _champ_key_map[int(_info['key'])] = _cid

try:
    from ..lcu.connector import LCUService
    _lcu = LCUService(_champ_key_map)
    _lcu.start()
except Exception as _lcu_err:
    print(f'LCU service unavailable: {_lcu_err}')
    _lcu = None


_IS_DEV = not getattr(_sys, 'frozen', False)

@app.route('/')
def index():
    return render_template('index.html', champions=CHAMPION_DATA, is_dev=_IS_DEV)


@app.route('/api/recommendations', methods=['POST'])
def get_recommendations():
    try:
        data = request.get_json()
        role = ROLE_MAP.get(data.get('role', 'mid'), Role.MIDDLE)
        declared = data.get('declared')  # champion the player has declared / hovered

        # Exclude the declared champion from allies so the engine can score it
        allies = [a for a in data.get('allies', []) if a != declared]

        result = asyncio.run(_generate_recommendations_async(
            allies,
            data.get('enemies', []),
            data.get('banned', []),
            _current_patch,
            data.get('championPool', []),
            role,
        ))

        overall = [_fmt(r) for r in result.overall_recommendations]
        pool    = [_fmt(r) for r in result.champion_pool_recommendations]

        # Separate declared champion from the alternatives list.
        # If the declared champion isn't in the scored list (e.g. off-meta / no Lolalytics data
        # for this role), build a minimal fallback entry so the UI still switches to their pick.
        declared_entry = None
        if declared:
            for i, r in enumerate(overall):
                if r['championId'] == declared:
                    declared_entry = r
                    overall = overall[:i] + overall[i+1:]
                    break
            for i, r in enumerate(pool):
                if r['championId'] == declared:
                    pool = pool[:i] + pool[i+1:]
                    break
            if declared_entry is None:
                info = CHAMPION_DATA.get(declared, {})
                declared_entry = {
                    'championId': declared,
                    'championName': info.get('name', declared),
                    'score': 0, 'winRate': 0, 'pickRate': 0, 'banRate': 0,
                    'scoreBreakdown': {'metaScore': 0, 'synergyScore': 0, 'counterScore': 0, 'confidenceBonus': 0},
                    'explanations': [],
                }

        return jsonify({
            'championPoolRecommendations': pool,
            'overallRecommendations':      overall,
            'declaredChampion':            declared_entry,
            'timestamp':                   result.timestamp.isoformat(),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/champions')
def get_champions():
    return jsonify(CHAMPION_DATA)


@app.route('/api/role_pools')
def get_role_pools():
    """Return champion IDs grouped by their primary role per Lolalytics defaultLane data."""
    all_roles = [Role.TOP, Role.JUNGLE, Role.MIDDLE, Role.BOTTOM, Role.UTILITY]
    role_keys  = ['top', 'jungle', 'mid', 'bottom', 'support']
    pools = {k: [] for k in role_keys}
    async def _fetch():
        stats_per_role = await asyncio.gather(
            *[data_manager.fetch_champion_stats(_current_patch, r) for r in all_roles]
        )
        for key, stats in zip(role_keys, stats_per_role):
            pools[key] = [s.champion_id for s in stats]
    asyncio.run(_fetch())
    return jsonify(pools)


@app.route('/api/infer_roles', methods=['POST'])
def infer_roles():
    """Given a list of champion IDs (no positions known), return best-guess role assignments."""
    champ_ids = request.get_json(force=True).get('champions', [])
    if not champ_ids:
        return jsonify({})
    result = asyncio.run(_infer_roles_async(champ_ids))
    return jsonify(result)


async def _infer_roles_async(champ_ids: list) -> dict:
    all_roles = [Role.TOP, Role.JUNGLE, Role.MIDDLE, Role.BOTTOM, Role.UTILITY]
    role_key_map = {Role.TOP: 'top', Role.JUNGLE: 'jungle', Role.MIDDLE: 'mid',
                    Role.BOTTOM: 'bottom', Role.UTILITY: 'support'}

    # Fetch stats for all roles in parallel (most will be cache hits)
    stats_per_role = await asyncio.gather(
        *[data_manager.fetch_champion_stats(_current_patch, r) for r in all_roles],
        return_exceptions=True,
    )

    # Build {champ_id: {role_key: pick_rate}} affinity table
    affinity: dict = {}
    for role, stats in zip(all_roles, stats_per_role):
        if not isinstance(stats, list):
            continue
        rk = role_key_map[role]
        for s in stats:
            if s.champion_id in champ_ids:
                affinity.setdefault(s.champion_id, {})[rk] = s.pick_rate

    # Greedy assignment: highest pick_rate wins, no role double-booked
    ROLE_KEYS = ['top', 'jungle', 'mid', 'bottom', 'support']
    candidates = sorted(
        [(pr, cid, rk) for cid, roles in affinity.items() for rk, pr in roles.items()],
        reverse=True,
    )
    assigned_champs, taken_roles, assignment = set(), set(), {}
    for pr, cid, rk in candidates:
        if cid in assigned_champs or rk in taken_roles:
            continue
        assignment[cid] = rk
        assigned_champs.add(cid)
        taken_roles.add(rk)

    # Any champion with no Lolalytics data gets a leftover role by order
    remaining = [r for r in ROLE_KEYS if r not in taken_roles]
    for cid in champ_ids:
        if cid not in assignment and remaining:
            assignment[cid] = remaining.pop(0)

    return assignment


@app.route('/api/champion_detail', methods=['POST'])
def get_champion_detail():
    try:
        data      = request.get_json()
        champ_id  = data.get('champion_id', '')
        role      = ROLE_MAP.get(data.get('role', 'mid'), Role.MIDDLE)
        allies    = data.get('allies', [])
        enemies   = data.get('enemies', [])

        result = asyncio.run(_champion_detail_async(champ_id, role, allies, enemies))
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


async def _champion_detail_async(champ_id: str, role: Role, allies: list, enemies: list) -> dict:
    # Build / rune data from Lolalytics (best-effort; may be empty)
    lol_detail: dict = {}
    if hasattr(data_manager, 'fetch_champion_detail'):
        try:
            lol_detail = await data_manager.fetch_champion_detail(_current_patch, champ_id, role)
        except Exception:
            pass

    # Resolve item names — items come as [{id, wr, n}, ...]
    raw_items = lol_detail.get('items', [])
    build = []
    for entry in raw_items:
        iid  = entry['id']
        name = _ITEM_NAMES.get(iid, '')
        if name:
            build.append({'id': iid, 'name': name, 'wr': entry.get('wr', 0)})

    # Runes come as {pri:[ids], sec:[ids], mod:[ids], wr, n}
    raw_runes = lol_detail.get('runes', {})
    runes: dict = {}
    if raw_runes.get('pri'):
        runes = {
            'pri': [{'id': rid, 'name': _RUNE_NAMES.get(rid, '')} for rid in raw_runes['pri']],
            'sec': [{'id': rid, 'name': _RUNE_NAMES.get(rid, '')} for rid in raw_runes.get('sec', [])],
            'mod': [{'id': rid, 'name': _RUNE_NAMES.get(rid, '')} for rid in raw_runes.get('mod', [])],
            'wr':  raw_runes.get('wr', 0),
            'n':   raw_runes.get('n', 0),
        }

    # Counter picks — filter to actual enemies in the draft where possible
    counter_data = await data_manager.fetch_counter_data(_current_patch, role)
    enemy_set = set(enemies)
    counters = []
    strong_against = []
    for cd in counter_data:
        if cd.champion_a != champ_id:
            continue
        # Only show matchups against actual draft enemies (if any are known)
        if enemy_set and cd.champion_b not in enemy_set:
            continue
        name = CHAMPION_DATA.get(cd.champion_b, {}).get('name', cd.champion_b)
        if cd.win_rate_b > 0.51:   # enemy beats us
            counters.append({
                'champion_id':   cd.champion_b,
                'champion_name': name,
                'win_rate':      round(cd.win_rate_b * 100, 1),
                'risk':          'high' if cd.win_rate_b > 0.55 else 'mid',
            })
        elif cd.win_rate_a > 0.52:   # we beat them
            strong_against.append({
                'champion_id':   cd.champion_b,
                'champion_name': name,
                'win_rate':      round(cd.win_rate_a * 100, 1),
                'advantage':     'high' if cd.win_rate_a > 0.55 else 'mid',
            })
    # Fallback: only show general matchups when no enemies are known yet (empty draft)
    if not enemy_set and not counters and not strong_against:
        for cd in counter_data:
            if cd.champion_a != champ_id:
                continue
            name = CHAMPION_DATA.get(cd.champion_b, {}).get('name', cd.champion_b)
            if cd.win_rate_b > 0.51:
                counters.append({
                    'champion_id': cd.champion_b, 'champion_name': name,
                    'win_rate': round(cd.win_rate_b * 100, 1),
                    'risk': 'high' if cd.win_rate_b > 0.55 else 'mid',
                })
            elif cd.win_rate_a > 0.52:
                strong_against.append({
                    'champion_id': cd.champion_b, 'champion_name': name,
                    'win_rate': round(cd.win_rate_a * 100, 1),
                    'advantage': 'high' if cd.win_rate_a > 0.55 else 'mid',
                })
    counters.sort(key=lambda x: -x['win_rate'])
    strong_against.sort(key=lambda x: -x['win_rate'])
    counters = counters[:5]
    strong_against = strong_against[:5]

    # Power spike curve — use real Lolalytics win-rate-by-game-length if available,
    # fall back to tag-based heuristic for the recommended champion.
    # Lolalytics has 7 game-length buckets: <20m, 20-25, 25-30, 30-35, 35-40, 40-45, 45+m
    # Map to our 5 display stages: Lane(1-3), Lvl6, Mid(11), Late(16), Full(18)
    raw_gl = lol_detail.get('game_length_wr', [])
    if raw_gl and len(raw_gl) >= 5:
        by_bucket = {entry['bucket']: entry['wr'] for entry in raw_gl}
        # Stage mapping: Lane≈bucket2, Lvl6≈bucket2-3, Mid≈bucket3-4, Late≈bucket5, Full≈bucket6-7
        def avg(*keys):
            vals = [by_bucket[k] for k in keys if k in by_bucket]
            return round(sum(vals) / len(vals), 1) if vals else 50.0
        ally_curve = [
            avg(1, 2),       # Lane
            avg(2, 3),       # Lvl 6
            avg(3, 4),       # Mid
            avg(5),          # Late
            avg(6, 7),       # Full
        ]
        # Reference line: champion's own weighted-average win rate (flat — shows whether each
        # stage is above or below the champion's overall norm). Keeps the same scale as ally_curve.
        baseline = round(sum(e['wr'] * e['n'] for e in raw_gl) / max(sum(e['n'] for e in raw_gl), 1), 1)
        enemy_curve = [baseline] * 5
    else:
        ally_curve  = _team_curve([champ_id] + allies)
        enemy_curve = [50] * 5

    return {
        'build':          build,
        'runes':          runes,
        'counters':       counters,
        'strong_against': strong_against,
        'power_curve':    {'ally': ally_curve, 'enemy': enemy_curve},
        'game_length_wr': raw_gl,
    }


async def _generate_recommendations_async(allies, enemies, banned, patch, champion_pool, role):
    def make(cid):
        info = CHAMPION_DATA.get(cid, {'name': cid.replace('_', ' ').title()})
        return Champion(id=cid, name=info['name'], role=role, tags=[])

    draft_state = DraftState(
        role=role,
        ally_champions=[make(a) for a in allies],
        enemy_champions=[make(e) for e in enemies],
        banned_champions=[make(b) for b in banned],
        patch=patch,
    )
    return await engine.generate_recommendations(draft_state, champion_pool)


def _fmt(rec):
    return {
        'championId': rec.champion.id,
        'championName': rec.champion.name,
        'score': round(rec.score, 1),
        'winRate': round(rec.win_rate * 100, 1),
        'pickRate': round(rec.pick_rate * 100, 1),
        'banRate': round(rec.ban_rate * 100, 1),
        'scoreBreakdown': {
            'metaScore': round(rec.score_breakdown.meta_score, 1),
            'synergyScore': round(rec.score_breakdown.synergy_score, 1),
            'counterScore': round(rec.score_breakdown.counter_score, 1),
            'confidenceBonus': round(rec.score_breakdown.confidence_bonus or 0, 1),
        },
        'explanations': rec.explanations,
    }


@app.route('/api/lcu/raw')
def lcu_raw():
    """Return the raw LCU session JSON — for debugging only."""
    if _lcu is None:
        return jsonify({'error': 'LCU service not running'})
    raw = getattr(_lcu._connector, '_last_raw', None)
    if raw is None:
        return jsonify({'error': 'no raw data (not in champ select or not connected)'})
    # Return just the useful parts to avoid huge response
    return jsonify({
        'localPlayerCellId': raw.get('localPlayerCellId'),
        'myTeam': [
            {k: p.get(k) for k in ('cellId', 'assignedPosition', 'championId', 'championPickIntent', 'spell1Id', 'spell2Id')}
            for p in raw.get('myTeam', [])
        ],
        'theirTeam': [
            {k: p.get(k) for k in ('cellId', 'assignedPosition', 'championId', 'championPickIntent')}
            for p in raw.get('theirTeam', [])
        ],
        'bans': raw.get('bans', {}),
        'actions': raw.get('actions', []),
        'timer': raw.get('timer', {}),
    })


@app.route('/api/lcu/status')
def lcu_status():
    """Is the League client connected and in champion select?"""
    if _lcu is None:
        return jsonify({'connected': False, 'active': False})
    state = _lcu.current()
    return jsonify({
        'connected': _lcu._connector.port is not None,
        'active':    state is not None,
        'state':     state,
    })


@app.route('/api/lcu/stream')
def lcu_stream():
    """SSE stream — pushes champion select state on every change."""
    if _lcu is None:
        return Response('data: {}\n\n', mimetype='text/event-stream')

    def generate():
        q = _lcu.subscribe()
        try:
            # Send current state immediately on connect
            current = _lcu.current()
            yield f'data: {json.dumps(current)}\n\n'
            while True:
                try:
                    state = q.get(timeout=25)
                    yield f'data: {json.dumps(state)}\n\n'
                except Exception:
                    # keepalive comment so the connection stays open
                    yield ': ka\n\n'
        finally:
            _lcu.unsubscribe(q)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Access-Control-Allow-Origin': '*',
        },
    )


def run_web_app(host='127.0.0.1', port=8080, debug=True):
    # Disable the reloader when frozen (PyInstaller binary) — it tries to re-exec
    # the binary as a Python script which fails.
    use_reloader = debug and not getattr(_sys, 'frozen', False)
    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=use_reloader)


if __name__ == '__main__':
    run_web_app()
