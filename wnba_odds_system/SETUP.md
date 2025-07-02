# WNBA Odds System - Quick Setup Guide

## ⚡ **5-Minute Setup**

### **1. Dependencies**
```bash
# Install required Python packages
pip install requests pandas beautifulsoup4 lxml pyarrow

# Verify installation
python3 -c "import requests, pandas, bs4; print('✅ Dependencies installed')"
```

### **2. Check Current Status**
```bash
cd wnba_odds_system

# Quick status check
./scripts/check_wnba_status.sh

# Live monitoring dashboard
python3 scripts/monitor_wnba_collection.py
```

### **3. Current Collection Status**
As of handoff, a sustainable collection process is running:
- **Collection Type**: IP-safe with conservative delays
- **Target**: 2021-2025 WNBA historical odds  
- **Timeline**: 3-4 hours total
- **Status**: Check logs for current progress

## 🔍 **What's Running Right Now**

```bash
# Check if collection is active
ps aux | grep wnba

# View live logs
tail -f logs/wnba_sustainable_collection.log

# Monitor progress
python3 scripts/monitor_wnba_collection.py --watch
```

## 📊 **Expected Data Output**

Files will appear in `data/odds/` as collection progresses:
- `wnba_2024_sustainable_*.csv` - 2024 season data
- `wnba_2023_sustainable_*.csv` - 2023 season data  
- `wnba_2022_sustainable_*.csv` - 2022 season data
- `wnba_2021_sustainable_*.csv` - 2021 season data

**Each file contains**:
- Game date, teams, odds data
- Multiple sportsbooks (FanDuel, DraftKings, etc.)
- Standardized format ready for ML models

## 🚨 **If Something Goes Wrong**

### **Collection Stopped**
```bash
# Check if process is running
ps aux | grep wnba_sustainable

# Restart if needed
./scripts/collect_wnba_sustainable.sh

# Monitor restart
tail -f logs/wnba_sustainable_collection.log
```

### **No Data Being Collected**
```bash
# Try gentle alternative
python3 scripts/wnba_gentle_scraper.py

# Check with different source
python3 scripts/wnba_comprehensive_scraper.py --source betinf --delay 30
```

### **Rate Limited / IP Issues**
```bash
# Stop current collection
pkill -f wnba_sustainable

# Wait 1 hour for cooldown
sleep 3600

# Restart with longer delays
# Edit scripts/collect_wnba_sustainable.sh and increase delay from 45s to 60s+
```

## 🎯 **Quick Actions**

| Task | Command |
|------|---------|
| **Check Status** | `./scripts/check_wnba_status.sh` |
| **Live Monitor** | `python3 scripts/monitor_wnba_collection.py --watch` |
| **View Logs** | `tail -f logs/wnba_sustainable_collection.log` |
| **Stop Collection** | `pkill -f wnba_sustainable` |
| **Start Collection** | `./scripts/collect_wnba_sustainable.sh` |
| **View Data** | `ls -la data/odds/` |

## 📈 **Success Indicators**

✅ **Collection Working**:
- Process running (check with `ps aux | grep wnba`)
- Log file updating (`tail -f logs/wnba_sustainable_collection.log`)
- Files appearing in `data/odds/`

⚠️ **Needs Attention**:
- No process running
- Logs show "Rate limited" repeatedly  
- No files created after 2+ hours

## 🔄 **Handoff Checklist**

- [ ] Verify dependencies installed
- [ ] Check current collection status
- [ ] Understand log locations
- [ ] Know how to restart if needed
- [ ] Familiar with monitoring tools
- [ ] Understand data output format

## 📞 **Need Help?**

1. **Check logs first**: `tail -50 logs/wnba_sustainable_collection.log`
2. **Try monitoring tool**: `python3 scripts/monitor_wnba_collection.py --detailed`
3. **Review main documentation**: `README.md`
4. **Check troubleshooting section**: `README.md` → Troubleshooting

## 🏆 **Expected Final Result**

When complete, you'll have:
- **500-1,500 WNBA game records** (2021-2025)
- **Multiple sportsbook odds** per game
- **Clean, standardized data** ready for ML models
- **Sustainable collection process** for future updates

**The system is designed to be low-maintenance and respectful to data sources.**