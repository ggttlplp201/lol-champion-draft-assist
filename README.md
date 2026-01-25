# League of Legends Champion Draft Assist Tool

A data-driven champion recommendation system that helps League of Legends players make better picks during champion select by analyzing patch strength, team synergy, and enemy matchups.

## The Problem

Champion select in League of Legends is complex and high-pressure:

- **Information overload**: 160+ champions, constantly changing balance patches, complex team interactions
- **Time pressure**: 30 seconds to pick while considering allies, enemies, and bans
- **Hidden knowledge**: Pro-level synergies and counters aren't obvious to most players
- **Recency bias**: Players often remember recent games more than statistical trends

Most players rely on gut feeling, outdated guides, or simple "counter pick" websites that don't consider the full draft context.

## The Solution

This tool provides **intelligent, context-aware champion recommendations** by combining three key factors:

### 🎯 **Meta Score (40%)** - Patch Strength
How strong is this champion in the current patch?
- Uses real match data from Riot Games API
- Filters by rank and role for relevance
- Updates automatically with each patch

### 🤝 **Synergy Score (30%)** - Team Chemistry  
How well does this champion work with your team?
- **Duo-Delta Method**: Compares actual vs expected win rates when champions are played together
- Example: If Yasuo normally wins 50% and Malphite wins 50%, we'd expect them together to win ~50%. If they actually win 65% together, that's a +15% synergy bonus.
- Accounts for all ally champions, not just one

### ⚔️ **Counter Score (30%)** - Matchup Advantage
How well does this champion perform against enemies?
- Head-to-head win rates from historical match data
- Considers all enemy champions, weighted by importance
- Updates with patch changes and meta shifts

## Why Duo-Delta for Synergy?

Traditional synergy analysis has problems:
- **Subjective**: "These champions have good teamfight synergy" (says who?)
- **Incomplete**: Only considers obvious combos like Yasuo + Malphite
- **Static**: Doesn't adapt to patch changes or meta shifts

**Duo-Delta is objective and comprehensive:**

1. **Statistical Foundation**: Uses actual match outcomes, not opinions
2. **Discovers Hidden Synergies**: Finds unexpected champion combinations that win more than they should
3. **Adapts Automatically**: Updates as the meta changes and new strategies emerge
4. **Quantifiable**: Gives precise numbers you can trust

**Example**: If Orianna (52% win rate) and Jinx (51% win rate) win 58% of games when played together, that's a +5% synergy delta - significantly better than random chance.

## MVP Scope

This initial version focuses on **core functionality with mid lane**:

### ✅ **What's Included**
- **Mid lane recommendations only** (most complex role for testing)
- **Real-time patch data** from Riot Games API with caching
- **Mathematical scoring system** with configurable weights
- **Champion pool support** with confidence bonuses
- **Statistical correctness** with comprehensive test coverage
- **Command-line interface** for immediate usability

### 🔄 **What's Coming Next**
- **All roles support** (top, jungle, ADC, support)
- **Web interface** with visual champion portraits and explanations
- **Advanced team composition analysis** (damage types, team fight roles)
- **Real-time integration** with champion select (if possible within Riot's ToS)
- **Machine learning enhancements** for meta prediction

### 🚫 **What's Explicitly Out of Scope**
- **Game client integration** (violates Riot's Terms of Service)
- **Automated picking** (this is a recommendation tool, not a bot)
- **Rank climbing guarantees** (it's still a game of skill!)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Riot API key
export RIOT_API_KEY="your_key_here"

# Run tests to verify everything works
python -m pytest tests/

# Get champion recommendations (coming soon)
python main.py --role mid --allies yasuo --enemies zed
```

## Technical Highlights

- **Statistically rigorous**: Proper sample sizes, confidence intervals, and bias correction
- **Performance optimized**: Intelligent caching and rate limiting for Riot API
- **Test-driven**: Property-based testing ensures mathematical correctness
- **Extensible architecture**: Clean separation between data, scoring, and interface layers

---

*This tool is for educational and personal use only. It is not affiliated with Riot Games. League of Legends is a trademark of Riot Games, Inc.*