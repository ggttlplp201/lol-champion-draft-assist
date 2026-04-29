# Riot API Integration Setup

This guide will help you set up real Riot API integration for your Draft Advisor application.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Get Riot API Key
1. Go to [Riot Developer Portal](https://developer.riotgames.com/)
2. Create an account (or log in)
3. Generate a development API key
4. Copy your API key

### 3. Set Environment Variable
```bash
# On macOS/Linux:
export RIOT_API_KEY="your_api_key_here"

# On Windows:
set RIOT_API_KEY=your_api_key_here
```

### 4. Test the Setup
```bash
python setup_riot_api.py
```

### 5. Run the Application
```bash
python -m src.interface.web_app
```

## What Works Now

✅ **Champion Data**: Real champion information from Data Dragon
✅ **Current Patch**: Automatically gets the latest patch version
✅ **Rate Limiting**: Built-in rate limiting to respect API limits
✅ **Caching**: Intelligent caching to minimize API calls
✅ **Fallback**: Gracefully falls back to mock data if API fails

## What's Still Mock Data

⚠️ **Match Data**: Currently uses limited real matches + mock data fallback
⚠️ **Win Rates**: Calculated from limited match sample
⚠️ **Synergy/Counter Data**: Uses mock data with realistic patterns

## API Key Types

### Development Key (Free)
- **Rate Limit**: 20 requests/second, 100 requests/2 minutes
- **Duration**: 24 hours (renewable)
- **Perfect for**: Testing and development

### Personal API Key (Free)
- **Rate Limit**: 100 requests/second, 600 requests/10 minutes  
- **Duration**: Doesn't expire
- **Perfect for**: Personal projects and small applications

### Production API Key (Application Required)
- **Rate Limit**: Higher limits based on application
- **Duration**: Long-term
- **Perfect for**: Production applications with many users

## Troubleshooting

### "No API key found"
Make sure you've set the environment variable correctly:
```bash
echo $RIOT_API_KEY  # Should show your key
```

### "Rate limit exceeded"
The application has built-in rate limiting, but if you hit limits:
- Wait a few minutes
- The app will automatically retry
- Consider getting a Personal API key for higher limits

### "403 Forbidden"
- Check that your API key is valid
- Make sure it hasn't expired (development keys expire after 24 hours)
- Regenerate your key if needed

### "Champion data not loading"
- Check your internet connection
- The Data Dragon API (for champion data) doesn't require an API key
- Try clearing the cache: delete the `cache/` directory

## File Structure

```
src/data/
├── riotwatcher_client.py    # New RiotWatcher integration
├── riot_api_client.py       # Original custom implementation  
├── manager.py               # Data manager interface
└── ...

setup_riot_api.py           # Setup and testing script
```

## Configuration Options

You can customize the RiotWatcher client:

```python
# Different region
client = RiotWatcherClient(region="euw1")

# Custom API key
client = RiotWatcherClient(api_key="your_key")
```

Supported regions:
- `na1` (North America)
- `euw1` (Europe West)
- `eun1` (Europe Nordic & East)
- `kr` (Korea)
- `jp1` (Japan)

## Next Steps

To get fully real data (not mock), you would need to:

1. **Implement Match Collection**: Collect matches from multiple high-ranked players
2. **Database Storage**: Store match data in a database for analysis
3. **Batch Processing**: Process matches in batches to calculate accurate statistics
4. **Champion.gg Integration**: Use additional data sources for more accurate meta information

The current implementation gives you a solid foundation with real champion data and the infrastructure to expand to full match data collection.