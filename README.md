# Champion Draft Assist Tool

A League of Legends draft assistance tool that provides intelligent champion recommendations for mid lane during champion select.

## Project Structure

```
├── src/                    # Main source code
│   ├── models.py          # Core data models
│   ├── engine.py          # Main suggestion engine
│   ├── data/              # Data management module
│   │   ├── __init__.py
│   │   └── manager.py     # API client and caching
│   ├── scoring/           # Scoring algorithms
│   │   ├── __init__.py
│   │   └── scorer.py      # Champion scoring logic
│   └── interface/         # User interfaces
│       ├── __init__.py
│       └── cli.py         # Command-line interface
├── tests/                 # Test files
│   ├── __init__.py
│   └── test_models.py     # Model tests
├── venv/                  # Virtual environment
├── main.py               # Main entry point
├── setup.py              # Package configuration
├── requirements.txt      # Dependencies
└── README.md            # This file
```

## Setup

1. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run tests:
```bash
pytest
```

4. Run CLI (placeholder):
```bash
python main.py recommend --help
```

## MVP Scope

This initial implementation focuses on:
- Core data models for champions, draft state, and recommendations
- Basic project structure with modular design
- Placeholder implementations for future API integration
- Mid lane champion recommendations only

## Next Steps

Future tasks will implement:
- Riot Games API integration
- Data aggregation and statistics calculation
- Champion scoring algorithms
- CLI interface functionality
- Property-based testing