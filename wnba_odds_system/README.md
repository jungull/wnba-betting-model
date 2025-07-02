# WNBA Odds Data Collection System

## 📋 **Project Overview**

This system collects historical WNBA odds data from multiple sources to enhance sports prediction models. It's designed to be respectful to servers, avoid IP bans, and provide comprehensive betting odds data spanning 2021-2025.

**Current Status**: Sustainable collection running (check logs for progress)

## 🗂️ **Directory Structure**

```
wnba_odds_system/
├── README.md                          # This file
├── SETUP.md                          # Quick setup guide
├── scripts/                          # All collection scripts
│   ├── wnba_comprehensive_scraper.py  # Main scraper (multi-source)
│   ├── wnba_gentle_scraper.py        # Conservative scraper
│   ├── monitor_wnba_collection.py    # Progress monitoring
│   ├── collect_wnba_sustainable.sh   # Current collection strategy
│   ├── collect_wnba_fast.sh          # Fast collection (archived)
│   ├── collect_all_wnba_historical.sh # Original collection script
│   └── check_wnba_status.sh          # Quick status checker
├── docs/                             # Documentation
│   ├── WNBA_Odds_Research_Report.md  # Data source analysis
│   ├── WNBA_Odds_Scraping_Strategy.md # Implementation strategy
│   ├── WNBA_Implementation_Next_Steps.md # Action plan
│   └── WNBA_Odds_Setup_Guide.md      # Quick start guide
├── data/                             # Data storage
│   └── odds/                         # WNBA odds files (CSV & Parquet)
├── logs/                             # Collection logs
│   ├── wnba_sustainable_collection.log # Current collection
│   └── wnba_*/                       # Historical logs
└── examples/                         # Sample data and usage
    └── sample_wnba_odds_data.csv     # Example output format
```

## 🚀 **Quick Start**

### **Check Current Status**
```bash
cd wnba_odds_system
./scripts/check_wnba_status.sh
```

### **Monitor Live Progress**
```bash
python3 scripts/monitor_wnba_collection.py --watch
```

### **Start New Collection** (if needed)
```bash
# Sustainable approach (recommended)
./scripts/collect_wnba_sustainable.sh

# Monitor progress
tail -f logs/wnba_sustainable_collection.log
```

## 📊 **Data Structure**

### **Output Format**
Each game record contains:
- **date**: Game date (YYYY-MM-DD)
- **year**: Season year (2021-2025)
- **home_team**: Standardized team name
- **away_team**: Standardized team name  
- **source**: Data source (OddsPortal, ESPN, etc.)
- **data_type**: Type of data (closing_odds, live_odds, results)
- **home_odds**: Decimal odds for home team
- **away_odds**: Decimal odds for away team
- **sportsbook**: Specific sportsbook (FanDuel, DraftKings, etc.)

### **Sample Data**
See `examples/sample_wnba_odds_data.csv` for format example.

## 🛠️ **Core Scripts Explained**

### **1. wnba_comprehensive_scraper.py** 
**Main workhorse scraper**
- **Purpose**: Multi-source WNBA odds collection
- **Sources**: OddsPortal, VegasInsider, BetInf.com
- **Features**: Rate limiting, checkpointing, data standardization
- **Usage**: `python3 wnba_comprehensive_scraper.py --source oddsportal --years 2024-2024 --delay 15.0`

**Key Parameters**:
- `--source`: Choose data source (oddsportal, vegasinsider, betinf, all)
- `--years`: Date range (2021-2024)
- `--delay`: Seconds between requests (15+ recommended)
- `--output`: Output filename prefix

### **2. monitor_wnba_collection.py**
**Real-time monitoring dashboard**
- **Purpose**: Track collection progress and data quality
- **Features**: Live updates, progress bars, file analysis
- **Usage**: `python3 monitor_wnba_collection.py --watch`

**Options**:
- `--detailed`: Show detailed file analysis
- `--watch`: Continuous monitoring mode
- `--interval`: Update frequency (seconds)

### **3. Collection Strategy Scripts**

#### **collect_wnba_sustainable.sh** ⭐ **CURRENT STRATEGY**
- **Purpose**: IP-safe collection with long delays
- **Timeline**: 3-4 hours
- **Safety**: 45-60s delays, 15-20 min breaks
- **Best for**: Avoiding IP bans, sustainable collection

#### **collect_wnba_fast.sh** ⚠️ **ARCHIVED**
- **Purpose**: Fast collection (RISKY - can cause IP bans)
- **Timeline**: 1-2 hours
- **Safety**: Minimal delays
- **Status**: Not recommended - use sustainable approach

## 📈 **Data Sources**

### **Primary Sources**
1. **OddsPortal** - Historical odds 2009+ (main target)
2. **ESPN** - Game results and basic data (safe)
3. **BetInf.com** - Historical results by season (backup)

### **Sportsbooks Covered**
- FanDuel
- DraftKings  
- BetMGM
- Caesars
- ESPN BET
- Other NY/US legal sportsbooks

### **API Alternatives**
If scraping becomes problematic:
- **The Odds API**: $10/month (reliable)
- **SportsDataIO**: $99/month (professional)

## ⚙️ **Technical Details**

### **Dependencies**
```bash
pip install requests pandas beautifulsoup4 lxml pyarrow
```

### **Rate Limiting Strategy**
- **Conservative delays**: 45-60 seconds between requests
- **Automatic backoff**: Increases delays if rate limited
- **Safe breaks**: 15-20 minutes between collection phases
- **IP protection**: Multiple sources, fallback strategies

### **Checkpointing System**
- **Automatic saves**: Data saved immediately after each successful scrape
- **Multiple formats**: CSV (human readable) + Parquet (analysis optimized)
- **Resume capability**: Can restart from interruption point
- **Progress tracking**: Detailed logs and status monitoring

### **Data Quality**
- **Team name standardization**: "New York Liberty" not "NYL"
- **Date formatting**: ISO format (YYYY-MM-DD)
- **Odds conversion**: Decimal format (universal)
- **Deduplication**: Automatic removal of duplicate records
- **Validation**: Data quality checks and reporting

## 🔧 **Troubleshooting**

### **Common Issues**

#### **No Data Collected**
```bash
# Check if sources are accessible
python3 scripts/wnba_gentle_scraper.py

# Try alternative source
python3 scripts/wnba_comprehensive_scraper.py --source betinf --delay 20
```

#### **Rate Limited**
```bash
# Increase delays
python3 scripts/wnba_comprehensive_scraper.py --delay 60

# Wait 1 hour then retry
sleep 3600 && ./scripts/collect_wnba_sustainable.sh
```

#### **IP Blocked**
```bash
# Wait 24 hours for cooldown
# Consider API alternative:
# - The Odds API: $10/month
# - Different IP/VPN
```

### **Log Analysis**
```bash
# Check recent activity
tail -50 logs/wnba_sustainable_collection.log

# Search for errors
grep -i "error\|failed\|blocked" logs/wnba_sustainable_collection.log

# Monitor rate limiting
grep -i "rate limited" logs/wnba_sustainable_collection.log
```

## 📋 **Current Collection Status**

**As of last update**:
- ✅ Sustainable collection script running
- 🎯 Target: 2021-2025 WNBA historical odds
- ⏱️ Timeline: 3-4 hours with IP-safe delays
- 🛡️ Strategy: Conservative, multi-source approach

**Check Status**:
```bash
./scripts/check_wnba_status.sh
python3 scripts/monitor_wnba_collection.py
```

## 🔄 **Handoff Instructions**

### **To Continue Current Collection**
1. **Check status**: `./scripts/check_wnba_status.sh`
2. **Monitor progress**: `python3 scripts/monitor_wnba_collection.py --watch`
3. **Wait for completion**: Collection runs automatically
4. **Validate data**: Check `data/odds/` for output files

### **To Start Fresh Collection**
1. **Stop existing**: `pkill -f wnba_sustainable`
2. **Start new**: `./scripts/collect_wnba_sustainable.sh`
3. **Monitor**: `tail -f logs/wnba_sustainable_collection.log`

### **To Modify Strategy**
1. **Edit script**: `vim scripts/collect_wnba_sustainable.sh`
2. **Adjust delays**: Change delay parameters (45-60s recommended)
3. **Test first**: Run single year before full collection

### **Integration with Prediction Models**
```python
import pandas as pd

# Load collected data
df = pd.read_csv('data/odds/wnba_2024_sustainable.csv')

# Basic analysis
print(f"Records: {len(df)}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}")
print(f"Teams: {df['home_team'].nunique()} unique teams")
print(f"Sportsbooks: {df['sportsbook'].dropna().nunique()}")

# Feature engineering for ML models
df['odds_spread'] = df['away_odds'] - df['home_odds']
df['favorite'] = df['home_odds'] < df['away_odds']
df['implied_prob_home'] = 1 / df['home_odds']
```

## 📞 **Support & Documentation**

### **Additional Documentation**
- `docs/WNBA_Odds_Research_Report.md` - Comprehensive source analysis
- `docs/WNBA_Odds_Scraping_Strategy.md` - Implementation strategy
- `docs/WNBA_Implementation_Next_Steps.md` - Future roadmap

### **Key Files to Understand**
1. **collect_wnba_sustainable.sh** - Current collection strategy
2. **wnba_comprehensive_scraper.py** - Core scraping logic
3. **monitor_wnba_collection.py** - Progress monitoring

### **Success Metrics**
- **Target**: 500+ game records minimum
- **Quality**: <5% missing data
- **Coverage**: 2021-2024 seasons
- **Safety**: No IP bans or blocks

---

## 🏆 **Expected Outcomes**

Upon completion, you will have:
- **Comprehensive WNBA dataset** (2021-2025)
- **Multiple sportsbook odds** per game
- **Ready-to-use features** for prediction models
- **Sustainable collection process** for ongoing updates
- **Complete documentation** for maintenance

**The system is designed to run safely and provide valuable WNBA betting data for sports prediction enhancement.**