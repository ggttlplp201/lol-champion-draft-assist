"""
Web interface for the Champion Draft Assist Tool.

This module provides a Flask web application with a modern UI
that matches the League of Legends aesthetic.
"""

import asyncio
from flask import Flask, render_template, request, jsonify
from typing import List, Dict, Any

from ..models import (
    Champion, DraftState, Role, ChampionTag, 
    ChampionRecommendation, RecommendationResult,
    SynergyData, CounterData
)
from ..engine import StandardSuggestionEngine
from ..data.manager import DataManager, SimpleCache
from ..scoring.scorer import StandardScorer


class MockDataManager(DataManager):
    """Mock data manager for web interface demonstration."""
    
    def __init__(self):
        self.cache = SimpleCache()
    
    async def fetch_champion_stats(self, patch: str, role: Role):
        """Return mock champion stats for mid lane champions."""
        from ..models import ChampionStats
        
        # Mock data for common mid lane champions with more realistic scores
        mock_champions = [
            ("sylas", 0.54), ("orianna", 0.52), ("ahri", 0.51), ("katarina", 0.49),
            ("azir", 0.48), ("cassiopeia", 0.50), ("diana", 0.53), ("fizz", 0.51),
            ("leblanc", 0.49), ("lissandra", 0.48), ("malzahar", 0.52), ("yasuo", 0.50),
            ("syndra", 0.49), ("talon", 0.51), ("twisted_fate", 0.48), ("veigar", 0.50),
            ("viktor", 0.49), ("xerath", 0.48), ("ziggs", 0.47), ("akali", 0.50),
            ("anivia", 0.49), ("annie", 0.51), ("brand", 0.48), ("corki", 0.47),
            ("ekko", 0.52), ("galio", 0.49), ("irelia", 0.50), ("kassadin", 0.48),
            ("lux", 0.51), ("neeko", 0.49), ("qiyana", 0.47), ("ryze", 0.46),
            ("zed", 0.51), ("vel_koz", 0.49), ("vladimir", 0.50), ("yone", 0.49)
        ]
        
        return [
            ChampionStats(
                champion_id=champ_id,
                role=role,
                win_rate=win_rate,
                pick_rate=0.05,
                ban_rate=0.02,
                patch=patch,
                rank_tier="GOLD"
            )
            for champ_id, win_rate in mock_champions
        ]
    
    async def fetch_match_data(self, filters):
        return []
    
    async def fetch_synergy_data(self, patch: str, role_a: Role, role_b: Role):
        """Return mock synergy data that varies based on champion combinations."""
        from ..models import SynergyData
        import random
        
        # Mock synergy data - some champions work better together
        synergy_pairs = {
            # AP + AD combinations work well
            ('sylas', 'jinx'): 0.08,
            ('orianna', 'jinx'): 0.06,
            ('ahri', 'jinx'): 0.05,
            ('malzahar', 'jinx'): 0.04,
            
            # Engage + follow-up combinations
            ('diana', 'yasuo'): 0.10,
            ('malzahar', 'yasuo'): 0.08,
            ('orianna', 'yasuo'): 0.07,
            
            # Control mages + ADCs
            ('orianna', 'ashe'): 0.06,
            ('syndra', 'jinx'): 0.05,
            ('xerath', 'caitlyn'): 0.04,
        }
        
        mock_data = []
        for (champ_a, champ_b), delta in synergy_pairs.items():
            mock_data.append(SynergyData(
                champion_pair=(champ_a, champ_b),
                role1=Role.MIDDLE,
                role2=role_b,
                combined_win_rate=0.52 + delta,
                expected_win_rate=0.52,
                synergy_delta=delta,
                sample_size=1000,
                patch=patch
            ))
        
        return mock_data
    
    async def fetch_counter_data(self, patch: str, role: Role):
        """Return mock counter data that creates realistic matchups."""
        from ..models import CounterData
        
        # Mock counter relationships - some champions counter others
        counter_matchups = {
            # Assassins vs Control Mages
            ('zed', 'xerath'): 0.58,
            ('zed', 'vel_koz'): 0.57,
            ('katarina', 'malzahar'): 0.45,  # Malz counters Kat
            ('yasuo', 'malzahar'): 0.42,    # Malz counters Yasuo
            
            # Control Mages vs Assassins  
            ('malzahar', 'zed'): 0.58,
            ('malzahar', 'katarina'): 0.60,
            ('lissandra', 'zed'): 0.55,
            ('annie', 'katarina'): 0.56,
            
            # Poke vs All-in
            ('xerath', 'diana'): 0.54,
            ('vel_koz', 'fizz'): 0.53,
            ('ziggs', 'akali'): 0.55,
            
            # All-in vs Poke
            ('diana', 'xerath'): 0.58,
            ('fizz', 'vel_koz'): 0.59,
            ('akali', 'ziggs'): 0.57,
            
            # Skill matchups
            ('yasuo', 'zed'): 0.52,
            ('ahri', 'leblanc'): 0.51,
            ('orianna', 'syndra'): 0.50,
        }
        
        mock_data = []
        for (champ_a, champ_b), win_rate in counter_matchups.items():
            mock_data.append(CounterData(
                champion_a=champ_a,
                champion_b=champ_b,
                role_a=role,
                role_b=role,
                win_rate_a=win_rate,
                win_rate_b=1.0 - win_rate,
                sample_size=500,
                patch=patch
            ))
        
        return mock_data
    
    def get_cached_data(self, key: str):
        return self.cache.get(key)
    
    def set_cached_data(self, key: str, data, ttl: int):
        self.cache.set(key, data, ttl)
    
    async def save_user_data(self, user_data):
        pass
    
    async def load_user_data(self):
        return None


# Initialize Flask app with correct template and static paths
import os
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'templates'))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'static'))

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = 'draft_advisor_secret_key'

# Initialize components
# Try to use RiotWatcher if API key is available, otherwise use mock data
try:
    from ..data.riotwatcher_client import RiotWatcherClient
    import os
    
    if os.getenv("RIOT_API_KEY"):
        print("🔑 Riot API key found - using real data from Riot API")
        data_manager = RiotWatcherClient()
    else:
        print("⚠️  No Riot API key found - using mock data for development")
        print("   Set RIOT_API_KEY environment variable to use real data")
        data_manager = MockDataManager()
except ImportError:
    print("⚠️  RiotWatcher not installed - using mock data")
    print("   Run: pip install -r requirements.txt")
    data_manager = MockDataManager()
except Exception as e:
    print(f"⚠️  Failed to initialize RiotWatcher: {e}")
    print("   Falling back to mock data")
    data_manager = MockDataManager()

scorer = StandardScorer()
engine = StandardSuggestionEngine(data_manager, scorer)

# Champion data for the UI
CHAMPION_DATA = {
    'sylas': {'name': 'Sylas'},
    'orianna': {'name': 'Orianna'},
    'ahri': {'name': 'Ahri'},
    'katarina': {'name': 'Katarina'},
    'azir': {'name': 'Azir'},
    'cassiopeia': {'name': 'Cassiopeia'},
    'diana': {'name': 'Diana'},
    'fizz': {'name': 'Fizz'},
    'leblanc': {'name': 'LeBlanc'},
    'lissandra': {'name': 'Lissandra'},
    'malzahar': {'name': 'Malzahar'},
    'yasuo': {'name': 'Yasuo'},
    'syndra': {'name': 'Syndra'},
    'talon': {'name': 'Talon'},
    'twisted_fate': {'name': 'Twisted Fate'},
    'veigar': {'name': 'Veigar'},
    'viktor': {'name': 'Viktor'},
    'xerath': {'name': 'Xerath'},
    'ziggs': {'name': 'Ziggs'},
    'akali': {'name': 'Akali'},
    'anivia': {'name': 'Anivia'},
    'annie': {'name': 'Annie'},
    'brand': {'name': 'Brand'},
    'corki': {'name': 'Corki'},
    'ekko': {'name': 'Ekko'},
    'galio': {'name': 'Galio'},
    'irelia': {'name': 'Irelia'},
    'kassadin': {'name': 'Kassadin'},
    'lux': {'name': 'Lux'},
    'neeko': {'name': 'Neeko'},
    'qiyana': {'name': 'Qiyana'},
    'ryze': {'name': 'Ryze'},
    'zed': {'name': 'Zed'},
    'vel_koz': {'name': "Vel'Koz"},
    'vladimir': {'name': 'Vladimir'},
    'yone': {'name': 'Yone'},
}


@app.route('/')
def index():
    """Main page with the draft advisor interface."""
    return render_template('index.html', champions=CHAMPION_DATA)


@app.route('/api/recommendations', methods=['POST'])
def get_recommendations():
    """API endpoint to get champion recommendations."""
    try:
        data = request.get_json()
        
        # Extract data from request
        allies = data.get('allies', [])
        enemies = data.get('enemies', [])
        banned = data.get('banned', [])
        champion_pool = data.get('championPool', [])
        patch = data.get('patch', '14.3')
        
        # Generate recommendations
        result = asyncio.run(_generate_recommendations_async(
            allies, enemies, banned, patch, champion_pool
        ))
        
        # Format response
        response = {
            'championPoolRecommendations': [
                _format_recommendation_for_api(rec) 
                for rec in result.champion_pool_recommendations[:5]
            ],
            'overallRecommendations': [
                _format_recommendation_for_api(rec) 
                for rec in result.overall_recommendations[:5]
            ],
            'timestamp': result.timestamp.isoformat()
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/champions')
def get_champions():
    """API endpoint to get available champions."""
    return jsonify(CHAMPION_DATA)


async def _generate_recommendations_async(allies, enemies, banned, patch, champion_pool):
    """Generate recommendations using the suggestion engine."""
    
    def create_champion(champion_id: str) -> Champion:
        champion_data = CHAMPION_DATA.get(champion_id, {'name': champion_id.title()})
        return Champion(
            id=champion_id,
            name=champion_data['name'],
            role=Role.MIDDLE,
            tags=[]
        )
    
    # Build draft state
    draft_state = DraftState(
        role=Role.MIDDLE,
        ally_champions=[create_champion(ally) for ally in allies],
        enemy_champions=[create_champion(enemy) for enemy in enemies],
        banned_champions=[create_champion(banned_champ) for banned_champ in banned],
        patch=patch
    )
    
    # Generate recommendations - this will now use the improved mock data
    return await engine.generate_recommendations(draft_state, champion_pool)


def _format_recommendation_for_api(recommendation: ChampionRecommendation) -> Dict[str, Any]:
    """Format a recommendation for API response."""
    return {
        'championId': recommendation.champion.id,
        'championName': recommendation.champion.name,
        'score': round(recommendation.score, 1),
        'scoreBreakdown': {
            'metaScore': round(recommendation.score_breakdown.meta_score, 1),
            'synergyScore': round(recommendation.score_breakdown.synergy_score, 1),
            'counterScore': round(recommendation.score_breakdown.counter_score, 1),
            'confidenceBonus': round(recommendation.score_breakdown.confidence_bonus or 0, 1)
        },
        'explanations': recommendation.explanations
    }


def run_web_app(host='127.0.0.1', port=8080, debug=True):
    """Run the Flask web application."""
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_web_app()