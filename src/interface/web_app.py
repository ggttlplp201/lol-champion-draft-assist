"""Web interface for the Champion Draft Assist Tool."""

import asyncio
import os
from flask import Flask, render_template, request, jsonify
from typing import List

from ..models import (
    Champion, DraftState, Role, ChampionTag,
    ChampionRecommendation, ChampionStats, SynergyData, CounterData
)
from ..engine import StandardSuggestionEngine
from ..data.manager import DataManager, SimpleCache
from ..scoring.scorer import StandardScorer


ROLE_MAP = {
    'top': Role.TOP,
    'jungle': Role.JUNGLE,
    'mid': Role.MIDDLE,
    'bottom': Role.BOTTOM,
    'adc': Role.BOTTOM,
    'support': Role.UTILITY,
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


class LolatyticsWithFallback(DataManager):
    """Uses LolatyticsClient for real data; falls back to MockDataManager on failure."""

    def __init__(self, primary: DataManager, fallback: MockDataManager):
        self._p = primary
        self._f = fallback

    async def fetch_champion_stats(self, patch: str, role: Role) -> List[ChampionStats]:
        try:
            stats = await self._p.fetch_champion_stats(patch, role)
            if len(stats) >= 5:
                return stats
        except Exception:
            pass
        return await self._f.fetch_champion_stats(patch, role)

    async def fetch_counter_data(self, patch: str, role: Role) -> List[CounterData]:
        try:
            data = await self._p.fetch_counter_data(patch, role)
            if data:
                return data
        except Exception:
            pass
        return await self._f.fetch_counter_data(patch, role)

    async def fetch_synergy_data(self, patch, role_a, role_b):
        return await self._f.fetch_synergy_data(patch, role_a, role_b)

    async def fetch_match_data(self, filters):
        return []

    def get_cached_data(self, key):
        return self._f.get_cached_data(key)

    def set_cached_data(self, key, data, ttl):
        self._f.set_cached_data(key, data, ttl)

    async def save_user_data(self, user_data):
        pass

    async def load_user_data(self):
        return None


template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'templates'))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'static'))
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = 'draft_advisor_secret_key'

_mock = MockDataManager()
try:
    from ..data.lolalytics_client import LolatyticsClient
    _lolalytics = LolatyticsClient(CHAMPION_DATA, CHAMPIONS_BY_ROLE)
    data_manager = LolatyticsWithFallback(_lolalytics, _mock)
    print('Using Lolalytics real data (win/pick/ban rates + counter matchups)')
except Exception as e:
    print(f'Lolalytics unavailable ({e}) — using mock data')
    data_manager = _mock

scorer = StandardScorer()
engine = StandardSuggestionEngine(data_manager, scorer)


@app.route('/')
def index():
    return render_template('index.html', champions=CHAMPION_DATA)


@app.route('/api/recommendations', methods=['POST'])
def get_recommendations():
    try:
        data = request.get_json()
        role = ROLE_MAP.get(data.get('role', 'mid'), Role.MIDDLE)
        result = asyncio.run(_generate_recommendations_async(
            data.get('allies', []),
            data.get('enemies', []),
            data.get('banned', []),
            data.get('patch', '14.3'),
            data.get('championPool', []),
            role,
        ))
        return jsonify({
            'championPoolRecommendations': [_fmt(r) for r in result.champion_pool_recommendations],
            'overallRecommendations': [_fmt(r) for r in result.overall_recommendations],
            'timestamp': result.timestamp.isoformat(),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/champions')
def get_champions():
    return jsonify(CHAMPION_DATA)


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


def run_web_app(host='127.0.0.1', port=8080, debug=True):
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_web_app()
