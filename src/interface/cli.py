"""
Command-line interface for the Champion Draft Assist Tool.

This module provides a CLI interface using Click for user interaction
with the draft assist functionality.
"""

import click
import asyncio
from typing import List
from datetime import datetime

from ..models import (
    Champion, DraftState, Role, ChampionTag, 
    ChampionRecommendation, RecommendationResult
)
from ..engine import StandardSuggestionEngine
from ..data.manager import DataManager, SimpleCache
from ..scoring.scorer import StandardScorer


class MockDataManager(DataManager):
    """Mock data manager for CLI demonstration."""
    
    def __init__(self):
        self.cache = SimpleCache()
    
    async def fetch_champion_stats(self, patch: str, role: Role):
        """Return mock champion stats for mid lane champions."""
        from ..models import ChampionStats
        
        # Mock data for common mid lane champions
        mock_champions = [
            ("yasuo", 0.52), ("zed", 0.49), ("ahri", 0.51), ("katarina", 0.48),
            ("azir", 0.47), ("cassiopeia", 0.50), ("diana", 0.53), ("fizz", 0.51),
            ("leblanc", 0.49), ("lissandra", 0.48), ("malzahar", 0.52), ("orianna", 0.50),
            ("syndra", 0.49), ("talon", 0.51), ("twisted_fate", 0.48), ("veigar", 0.50),
            ("viktor", 0.49), ("xerath", 0.48), ("ziggs", 0.47), ("akali", 0.50),
            ("anivia", 0.49), ("annie", 0.51), ("brand", 0.48), ("corki", 0.47),
            ("ekko", 0.52), ("galio", 0.49), ("irelia", 0.50), ("kassadin", 0.48),
            ("lux", 0.51), ("neeko", 0.49), ("qiyana", 0.47), ("ryze", 0.46),
            ("sylas", 0.51), ("vel_koz", 0.49), ("vladimir", 0.50), ("yone", 0.49)
        ]
        
        return [
            ChampionStats(
                champion_id=champ_id,
                role=role,
                win_rate=win_rate,
                pick_rate=0.05,  # 5% pick rate
                ban_rate=0.02,   # 2% ban rate
                patch=patch,
                rank_tier="GOLD"
            )
            for champ_id, win_rate in mock_champions
        ]
    
    async def fetch_match_data(self, filters):
        return []
    
    async def fetch_synergy_data(self, patch: str, role_a: Role, role_b: Role):
        return []
    
    async def fetch_counter_data(self, patch: str, role: Role):
        return []
    
    def get_cached_data(self, key: str):
        return self.cache.get(key)
    
    def set_cached_data(self, key: str, data, ttl: int):
        self.cache.set(key, data, ttl)
    
    async def save_user_data(self, user_data):
        pass
    
    async def load_user_data(self):
        return None


@click.group()
def cli():
    """Champion Draft Assist Tool - Get intelligent champion recommendations."""
    pass


@cli.command()
@click.option('--allies', '-a', multiple=True, help='Allied champion names (e.g., --allies yasuo --allies zed)')
@click.option('--enemies', '-e', multiple=True, help='Enemy champion names (e.g., --enemies ahri --enemies katarina)') 
@click.option('--banned', '-b', multiple=True, help='Banned champion names (e.g., --banned yasuo --banned zed)')
@click.option('--patch', '-p', default='14.1', help='Game patch version (default: 14.1)')
@click.option('--pool', multiple=True, help='Your champion pool (e.g., --pool yasuo --pool zed --pool ahri)')
def recommend(allies, enemies, banned, patch, pool):
    """
    Get champion recommendations for mid lane.
    
    Requirements: 7.1, 7.6
    - Accept draft state input (allies, enemies, banned champions)
    - Display champion pool and overall recommendations
    - Show explanations and score breakdowns
    
    Examples:
        python main.py recommend --allies yasuo --enemies ahri --banned zed --pool yasuo --pool katarina
        python main.py recommend -a yasuo -a jinx -e ahri -e diana -b zed -b fizz --pool yasuo --pool katarina --pool ahri
    """
    
    # Display input summary
    click.echo("🎯 Champion Draft Assist Tool")
    click.echo("=" * 50)
    click.echo(f"📊 Patch: {patch}")
    click.echo(f"🎭 Role: Mid Lane")
    click.echo()
    
    if allies:
        click.echo(f"🤝 Allied Champions: {', '.join(allies)}")
    if enemies:
        click.echo(f"⚔️  Enemy Champions: {', '.join(enemies)}")
    if banned:
        click.echo(f"🚫 Banned Champions: {', '.join(banned)}")
    if pool:
        click.echo(f"🏊 Your Champion Pool: {', '.join(pool)}")
    
    if allies or enemies or banned or pool:
        click.echo()
    
    # Run the async recommendation generation
    try:
        result = asyncio.run(_generate_recommendations(allies, enemies, banned, patch, pool))
        display_recommendations(result)
    except Exception as e:
        click.echo(f"❌ Error generating recommendations: {str(e)}", err=True)
        return


async def _generate_recommendations(allies, enemies, banned, patch, pool):
    """Generate recommendations using the suggestion engine."""
    
    # Create champion objects from input strings
    def create_champion(name: str) -> Champion:
        return Champion(
            id=name.lower().replace("'", "_").replace(" ", "_"),
            name=name.title(),
            role=Role.MIDDLE,
            tags=[]  # Will be populated from API data in production
        )
    
    # Build draft state
    draft_state = DraftState(
        role=Role.MIDDLE,  # MVP: Fixed to mid lane
        ally_champions=[create_champion(ally) for ally in allies],
        enemy_champions=[create_champion(enemy) for enemy in enemies],
        banned_champions=[create_champion(banned_champ) for banned_champ in banned],
        patch=patch
    )
    
    # Convert pool to champion IDs
    user_champion_pool = [name.lower().replace("'", "_").replace(" ", "_") for name in pool]
    
    # Initialize components
    data_manager = MockDataManager()
    scorer = StandardScorer()
    engine = StandardSuggestionEngine(data_manager, scorer)
    
    # Generate recommendations
    return await engine.generate_recommendations(draft_state, user_champion_pool)


def format_recommendation(recommendation: ChampionRecommendation) -> str:
    """
    Format a single recommendation for display.
    
    Requirements: 7.6
    - Show explanations and score breakdowns
    - Display champion names with recommendation scores
    """
    lines = []
    
    # Champion name and total score
    lines.append(f"🏆 {recommendation.champion.name} (Score: {recommendation.score:.1f})")
    
    # Score breakdown
    breakdown = recommendation.score_breakdown
    score_line = f"   📊 Meta: {breakdown.meta_score:.1f} | Synergy: {breakdown.synergy_score:.1f} | Counter: {breakdown.counter_score:.1f}"
    
    # Add confidence bonus if present
    if breakdown.confidence_bonus:
        score_line += f" | Bonus: +{breakdown.confidence_bonus:.1f}"
    
    lines.append(score_line)
    
    # Explanations
    for explanation in recommendation.explanations:
        lines.append(f"   💡 {explanation}")
    
    return "\n".join(lines)


def display_recommendations(result: RecommendationResult) -> None:
    """
    Display recommendation results in formatted output.
    
    Requirements: 7.1, 7.6
    - Display "Top 5 Champion Pool Picks" and "Top 5 Overall Picks"
    - Show explanations and score breakdowns
    - Clearly label each section
    """
    click.echo()
    click.echo("🏆 TOP 5 CHAMPION POOL PICKS")
    click.echo("=" * 50)
    
    if result.champion_pool_recommendations:
        for i, rec in enumerate(result.champion_pool_recommendations[:5], 1):
            click.echo(f"{i}. {format_recommendation(rec)}")
            if i < len(result.champion_pool_recommendations[:5]):
                click.echo()
    else:
        click.echo("   ℹ️  No champion pool recommendations available.")
        click.echo("   💡 Try adding champions to your pool with --pool option")
    
    click.echo()
    click.echo("⭐ TOP 5 OVERALL PICKS")
    click.echo("=" * 50)
    
    if result.overall_recommendations:
        for i, rec in enumerate(result.overall_recommendations[:5], 1):
            click.echo(f"{i}. {format_recommendation(rec)}")
            if i < len(result.overall_recommendations[:5]):
                click.echo()
    else:
        click.echo("   ℹ️  No overall recommendations available.")
    
    # Display timestamp
    click.echo()
    click.echo(f"🕒 Generated at: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    cli()