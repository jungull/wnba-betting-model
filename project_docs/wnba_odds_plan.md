# Improved Project Plan: WNBA Odds Data Aggregator

## 1. Project Goal
Build a robust, automated system that creates and maintains a unified dataset of WNBA game odds with live API integration, historical data backfill, comprehensive error handling, and monitoring capabilities.

## 2. Enhanced System Architecture

### Core Components
- **Historical Data Pipeline**: One-time backfill with resume capability
- **Live Data Pipeline**: Scheduled API polling with rate limiting
- **Data Processing Layer**: Unified cleaning and validation
- **Storage Layer**: SQLite with proper indexing and constraints
- **Monitoring Layer**: Logging, alerting, and health checks
- **Configuration Management**: Environment-based settings

### Data Flow
```
Historical Sources → Scraper → Data Processor → Database
Live API → Fetcher → Data Processor → Database
Database → Monitoring → Alerts/Logs
```

## 3. Enhanced Bill of Materials & Setup

| Component | Item | Setup Action | Notes |
|-----------|------|--------------|-------|
| Language/Runtime | Python 3.9+ | Install Python | Consider using pyenv for version management |
| Core Libraries | requests, beautifulsoup4, pandas, sqlalchemy, python-dotenv | `pip install -r requirements.txt` | Pin versions for reproducibility |
| Additional Libraries | retries, schedule, logging, hashlib, json | Included in requirements.txt | For robustness and monitoring |
| Live Data API | The Odds API | Sign up at the-odds-api.com | Free tier: 500 requests/month |
| Historical Data | OddsShark + Backup sources | Primary: oddsshark.com/wnba/odds | Consider additional sources for redundancy |
| Data Store | SQLite with WAL mode | Auto-created by SQLAlchemy | WAL mode for better concurrency |
| Automation | cron/systemd (Linux) or Task Scheduler (Windows) | Platform-specific setup | Include health monitoring |
| Monitoring | Python logging + optional external service | Built-in logging framework | Consider Sentry for production |

## 4. Enhanced Security & Configuration

### Environment Configuration (.env)
```env
# API Configuration
ODDS_API_KEY="your_api_key_here"
ODDS_API_BASE_URL="https://api.the-odds-api.com/v4"
API_RATE_LIMIT_REQUESTS=500
API_RATE_LIMIT_PERIOD=2592000  # 30 days in seconds

# Database Configuration
DATABASE_URL="sqlite:///wnba_odds.db"
DATABASE_BACKUP_ENABLED=true
DATABASE_BACKUP_INTERVAL=86400  # 24 hours

# Scraping Configuration
SCRAPER_DELAY=2
SCRAPER_USER_AGENT="WNBAOddsAggregator/1.0"
SCRAPER_TIMEOUT=30
SCRAPER_MAX_RETRIES=3

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE="wnba_odds.log"
LOG_MAX_SIZE=10485760  # 10MB
LOG_BACKUP_COUNT=5

# Monitoring Configuration
ENABLE_HEALTH_CHECKS=true
HEALTH_CHECK_INTERVAL=3600  # 1 hour
ALERT_EMAIL=""  # Optional: for critical alerts
```

### Security Improvements
- Use environment variables for all sensitive configuration
- Implement input validation and sanitization
- Add database connection pooling and timeout handling
- Include API key validation on startup

## 5. Improved Data Schema

### Main Table: `odds`
```sql
CREATE TABLE odds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    sport TEXT NOT NULL DEFAULT 'basketball_wnba',
    commence_time DATETIME NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    bookmaker TEXT NOT NULL,
    market_key TEXT NOT NULL,
    price_home REAL,
    point_home REAL,
    price_away REAL,
    point_away REAL,
    last_update DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL CHECK (source IN ('api', 'scrape')),
    data_quality_score REAL DEFAULT 1.0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(game_id, bookmaker, market_key)
);

CREATE INDEX idx_odds_game_id ON odds(game_id);
CREATE INDEX idx_odds_commence_time ON odds(commence_time);
CREATE INDEX idx_odds_home_team ON odds(home_team);
CREATE INDEX idx_odds_bookmaker ON odds(bookmaker);
CREATE INDEX idx_odds_source ON odds(source);
```

### Supporting Tables
```sql
-- Team name standardization
CREATE TABLE team_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_name TEXT NOT NULL UNIQUE,
    standard_name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- API usage tracking
CREATE TABLE api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT NOT NULL,
    requests_made INTEGER NOT NULL,
    requests_remaining INTEGER,
    reset_time DATETIME,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Data quality logs
CREATE TABLE data_quality_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    issue_description TEXT,
    affected_records INTEGER DEFAULT 1,
    severity TEXT CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 6. Enhanced Implementation Plan

### Phase 1: Foundation & Core Infrastructure

#### Step 1.1: Project Setup
```bash
mkdir wnba-odds-aggregator
cd wnba-odds-aggregator
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

#### Step 1.2: Core Utilities (`utils/`)
- `config.py`: Centralized configuration management
- `database.py`: Database connection and schema management
- `logging_config.py`: Structured logging setup
- `validators.py`: Data validation functions
- `team_mapper.py`: Team name standardization

#### Step 1.3: Database Initialization (`init_db.py`)
- Create database schema with proper constraints
- Populate team_mappings table with known variations
- Set up WAL mode for better concurrent access
- Create initial indexes

### Phase 2: Historical Data Pipeline

#### Step 2.1: Enhanced Web Scraper (`scrapers/oddsshark_scraper.py`)
```python
class OddsSharkScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.SCRAPER_USER_AGENT})
        self.rate_limiter = RateLimiter(calls=1, period=config.SCRAPER_DELAY)
        
    def scrape_with_retry(self, url, max_retries=3):
        # Implement exponential backoff
        # Handle HTTP errors gracefully
        # Parse robots.txt compliance
        
    def extract_odds_data(self, html):
        # Robust HTML parsing with fallback selectors
        # Data validation and quality scoring
        # Handle missing or malformed data
```

#### Step 2.2: Data Processing Pipeline (`processors/data_processor.py`)
- Unified data cleaning for both scraper and API data
- Team name standardization using fuzzy matching
- Date/time parsing with timezone handling
- Odds format conversion and validation
- Duplicate detection and merging strategies

#### Step 2.3: Resume Capability
- Track scraping progress in a separate table
- Support for restarting from last successful position
- Checkpoint mechanism for large historical datasets

### Phase 3: Live Data Pipeline

#### Step 3.1: Enhanced API Client (`api/odds_api_client.py`)
```python
class OddsAPIClient:
    def __init__(self):
        self.base_url = config.ODDS_API_BASE_URL
        self.api_key = config.ODDS_API_KEY
        self.rate_limiter = RateLimiter(calls=500, period=2592000)  # Monthly limit
        
    def get_odds(self, sport='basketball_wnba'):
        # Rate limiting enforcement
        # API usage tracking
        # Response validation
        # Error handling with appropriate retries
        
    def parse_api_response(self, response):
        # Convert nested JSON to flat structure
        # Map API fields to database schema
        # Handle missing bookmakers or markets
```

#### Step 3.2: Intelligent Update Strategy
- Compare odds changes before updating
- Track significant line movements
- Implement smart polling (more frequent during game days)
- Handle API downtime gracefully

### Phase 4: Monitoring & Quality Assurance

#### Step 4.1: Data Quality Monitoring (`monitors/quality_monitor.py`)
- Automated data validation checks
- Anomaly detection for odds outliers
- Completeness monitoring (missing games, bookmakers)
- Freshness monitoring (stale data detection)

#### Step 4.2: Health Checks (`monitors/health_checker.py`)
- Database connectivity tests
- API endpoint availability
- Disk space monitoring
- Process health verification

#### Step 4.3: Alerting System
- Critical error notifications
- Data quality degradation alerts
- API quota warnings
- Configurable notification channels (email, webhook)

### Phase 5: Automation & Deployment

#### Step 5.1: Smart Scheduling
Instead of simple cron, implement intelligent scheduling:
```python
# Dynamic scheduling based on WNBA season calendar
def get_polling_schedule():
    if is_game_day():
        return "every 30 minutes"
    elif is_season():
        return "every 4 hours" 
    else:  # off-season
        return "daily"
```

#### Step 5.2: Process Management
- Use systemd service files for better process management
- Implement graceful shutdown handling
- Add process monitoring and auto-restart capabilities

#### Step 5.3: Backup Strategy
- Automated database backups
- Backup verification and restoration testing
- Cloud storage integration (optional)

## 7. Enhanced Error Handling & Resilience

### Retry Strategies
- Exponential backoff for transient failures
- Circuit breaker pattern for persistent failures
- Different retry policies for different error types

### Data Integrity
- Transaction management for database operations
- Rollback mechanisms for failed batch operations
- Data consistency checks

### Graceful Degradation
- Continue operation when some bookmakers are unavailable
- Fallback to cached data during API outages
- Partial data processing capabilities

## 8. Testing Strategy

### Unit Tests
- Individual component testing
- Mock external dependencies
- Data validation logic testing

### Integration Tests
- End-to-end pipeline testing
- Database integration testing
- API client testing with mock responses

### Performance Tests
- Load testing for historical data processing
- Memory usage monitoring
- Database query performance

## 9. Enhanced Deliverables

### Project Structure
```
wnba-odds-aggregator/
├── src/
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base_scraper.py
│   │   └── oddsshark_scraper.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── odds_api_client.py
│   ├── processors/
│   │   ├── __init__.py
│   │   └── data_processor.py
│   ├── monitors/
│   │   ├── __init__.py
│   │   ├── quality_monitor.py
│   │   └── health_checker.py
│   └── utils/
│       ├── __init__.py
│       ├── config.py
│       ├── database.py
│       ├── logging_config.py
│       ├── validators.py
│       └── team_mapper.py
├── scripts/
│   ├── init_db.py
│   ├── historical_backfill.py
│   ├── live_fetcher.py
│   └── data_quality_report.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── config/
│   ├── .env.example
│   └── logging.yaml
├── docs/
│   ├── setup.md
│   ├── api_reference.md
│   └── troubleshooting.md
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
├── README.md
└── setup.py
```

### Configuration Files
- `systemd/wnba-odds.service`: Service definition for Linux
- `docker/Dockerfile`: Optional containerization
- `scripts/setup.sh`: Automated setup script

### Documentation
- Comprehensive README with setup instructions
- API documentation for internal functions
- Troubleshooting guide with common issues
- Data dictionary and schema documentation

## 10. Key Improvements Summary

1. **Robustness**: Added comprehensive error handling, retry mechanisms, and graceful degradation
2. **Monitoring**: Implemented data quality monitoring, health checks, and alerting
3. **Scalability**: Designed modular architecture with proper separation of concerns
4. **Maintainability**: Added extensive logging, configuration management, and documentation
5. **Data Quality**: Enhanced schema with constraints, validation, and quality scoring
6. **Security**: Improved configuration management and input validation
7. **Testing**: Added comprehensive testing strategy
8. **Operational**: Enhanced automation with intelligent scheduling and process management

This improved plan transforms the original concept into a production-ready system with enterprise-level reliability and maintainability features.