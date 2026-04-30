# What is Drafted?

A real-time champion select overlay for League of Legends. Connects to your local League client, reads the live ban/pick state automatically, and surfaces data-driven recommendations — counters, synergies, builds, runes, and win-rate curves — without leaving champion select.

## Features

- **Live LCU integration** — hooks into the League client and auto-fills picks, bans, and your assigned role the moment champion select starts. No manual input required.
- **Champion recommendations** scored on three factors:
  - **Meta strength (40%)** — current patch win rate and tier from Lolalytics (Emerald+, global)
  - **Counter score (30%)** — head-to-head win rate against each enemy pick
  - **Synergy score (30%)** — how well the champion pairs with your ally picks
- **Counter picks panel** — shows the strongest counters to the selected champion
- **Build & runes** — most-played item core and rune page with win rates, pulled from Lolalytics
- **Win rate by game length** — chart showing whether the champion wins early, scales to late, or peaks mid game, using real match data (not heuristics)
- **Patch delta indicators** — flags champions with significant win-rate changes this patch
- **Electron overlay** — runs as a floating window above the League client; stays on top in windowed / borderless windowed mode

## Running the app

### Prerequisites

- Python 3.9+ with a virtual environment (`venv/`)
- Node.js 18+ (for the Electron overlay)
- Dependencies installed: `pip install -r requirements.txt`

### Start the overlay

```bash
cd electron
npm install      # first time only
npm start
```

This spawns the Flask backend automatically and opens a floating overlay window.

### Browser-only (no Electron)

Double-click **`Launch Draft Advisor.command`** in Finder, or run manually:

```bash
python web_server.py
# then open http://127.0.0.1:5001
```

## How it works

```
League client (LCU API)
        │  local HTTPS, port discovered via process args
        ▼
  Flask backend  ──────────────────────────────────────────┐
  • polls /lol-champ-select/v1/session every 500 ms        │
  • streams state changes to browser via SSE               │
  • fetches champion stats + counters from Lolalytics      │
  • fetches build + rune + game-length WR from Lolalytics  │
        │                                                   │
        ▼                                                   │
  Browser UI  ◄──────────────────────────────────────────── SSE
  • renders recommendations, counters, build, runes
  • power spike chart (real win-rate-by-game-length data)
        │
        ▼
  Electron wrapper
  • always-on-top BrowserWindow (floats over the game)
  • menu-bar tray icon to toggle always-on-top or quit
```

**Data source**: [Lolalytics](https://lolalytics.com) internal API — Emerald+ ranked, global, current patch. No Riot API key required.

## Scoring model

| Factor | Weight | Source |
|---|---|---|
| Win rate (patch-adjusted) | 40% | Lolalytics `ep=tier` |
| Counter win rate vs enemy picks | 30% | Lolalytics `ep=counter` |
| Synergy with ally picks | 30% | Hash-based estimate (Lolalytics doesn't expose synergy data directly) |

Recommendations are filtered to champions whose primary role matches the selected lane, with a minimum of 500 games for statistical reliability.

## Project structure

```
web_server.py          entry point — starts Flask
src/
  interface/
    web_app.py         Flask routes, SSE relay, champion detail API
  lcu/
    connector.py       LCUConnector (REST) + LCUService (polling thread)
  data/
    lolalytics_client.py   fetches stats, counters, builds, runes
    manager.py             DataManager base + SimpleCache
  engine.py            recommendation engine
  scoring/scorer.py    weighted scorer
  models.py            dataclasses (Role, Champion, DraftState, …)
static/
  js/app.js            UI logic, SSE client, chart rendering
  css/style.css        styles
templates/index.html   single-page app shell
electron/
  main.js              spawns Flask, creates BrowserWindow
  package.json         Electron + electron-builder config
```

---

*For personal use only. Not affiliated with Riot Games. League of Legends is a trademark of Riot Games, Inc.*
