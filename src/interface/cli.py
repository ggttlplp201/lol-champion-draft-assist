"""
Command-line interface for the Champion Draft Assist Tool.

This module provides a CLI interface using Click for user interaction
with the draft assist functionality.
"""

import click
from typing import List
from datetime import datetime

from ..models import (
    Champion, DraftState, Role, ChampionTag, 
    ChampionRecommendation, RecommendationResult
)


@click.group()
def cli():
    """Champion Draft Assist Tool - Get intelligent champion recommendations."""
    pass


@cli.command()
@click.option('--allies', '-a', multiple=True, help='Allied champion names')
@click.option('--enemies', '-e', multiple=True, help='Enemy champion names') 
@click.option('--banned', '-b', multiple=True, help='Banned champion names')
@click.option('--patch', '-p', default='14.1', help='Game patch version')
@click.option('--pool', multiple=True, help='Your champion pool')
def recommend(allies, enemies, banned, patch, pool):
    """Get champion recommendations for mid lane."""
    
    # For MVP, we'll create a simple placeholder implementation
    click.echo("Champion Draft Assist Tool")
    click.echo("=" * 40)
    click.echo(f"Patch: {patch}")
    click.echo(f"Role: Mid Lane")
    
    if allies:
        click.echo(f"Allied Champions: {', '.join(allies)}")
    if enemies:
        click.echo(f"Enemy Champions: {', '.join(enemies)}")
    if banned:
        click.echo(f"Banned Champions: {', '.join(banned)}")
    if pool:
        click.echo(f"Your Champion Pool: {', '.join(pool)}")
    
    click.echo("\n[Recommendations will be implemented in future tasks]")


def format_recommendation(recommendation: ChampionRecommendation) -> str:
    """Format a single recommendation for display."""
    lines = [
        f"{recommendation.champion.name} (Score: {recommendation.score:.1f})",
        f"  Meta: {recommendation.score_breakdown.meta_score:.1f} | "
        f"Synergy: {recommendation.score_breakdown.synergy_score:.1f} | "
        f"Counter: {recommendation.score_breakdown.counter_score:.1f}"
    ]
    
    for explanation in recommendation.explanations:
        lines.append(f"  • {explanation}")
    
    return "\n".join(lines)


def display_recommendations(result: RecommendationResult) -> None:
    """Display recommendation results in formatted output."""
    click.echo("\n🏆 TOP 5 CHAMPION POOL PICKS")
    click.echo("=" * 40)
    
    if result.champion_pool_recommendations:
        for i, rec in enumerate(result.champion_pool_recommendations[:5], 1):
            click.echo(f"{i}. {format_recommendation(rec)}")
            if i < len(result.champion_pool_recommendations[:5]):
                click.echo()
    else:
        click.echo("No champion pool recommendations available.")
    
    click.echo("\n⭐ TOP 5 OVERALL PICKS")
    click.echo("=" * 40)
    
    if result.overall_recommendations:
        for i, rec in enumerate(result.overall_recommendations[:5], 1):
            click.echo(f"{i}. {format_recommendation(rec)}")
            if i < len(result.overall_recommendations[:5]):
                click.echo()
    else:
        click.echo("No overall recommendations available.")


if __name__ == '__main__':
    cli()