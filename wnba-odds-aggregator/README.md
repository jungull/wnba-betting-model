# WNBA Odds Aggregator

A robust, automated system for collecting, processing, and monitoring WNBA betting odds from both live APIs and historical sources.

## Features
- Historical and live odds data collection
- Unified data processing and validation
- SQLite storage with indexing
- Monitoring and alerting
- Modular, production-ready architecture

## Setup

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd wnba-odds-aggregator
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # or
   source venv/bin/activate  # On Mac/Linux
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in your configuration.

## Project Structure

```
wnba-odds-aggregator/
├── src/
│   ├── scrapers/
│   ├── api/
│   ├── processors/
│   ├── monitors/
│   └── utils/
├── scripts/
├── tests/
├── config/
├── docs/
├── requirements.txt
├── .gitignore
├── README.md
```

## License
MIT 