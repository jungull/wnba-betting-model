#!/bin/bash

# Quick WNBA Collection Status Check
echo "🏀 WNBA ODDS COLLECTION STATUS"
echo "================================"
echo "🕐 $(date)"
echo ""

# Check running processes
echo "🔄 Active Collectors:"
ps aux | grep -E "wnba.*scraper|collect.*wnba" | grep -v grep | while read line; do
    pid=$(echo $line | awk '{print $2}')
    cpu=$(echo $line | awk '{print $3}')
    mem=$(echo $line | awk '{print $4}')
    time=$(echo $line | awk '{print $10}')
    echo "   PID $pid: ${cpu}% CPU, ${mem}% Memory, Runtime: $time"
done

# Check data files
echo ""
echo "📁 Data Files:"
if ls data/odds/wnba_* 2>/dev/null | head -5; then
    echo "   $(ls data/odds/wnba_* 2>/dev/null | wc -l) files found"
else
    echo "   No data files created yet (normal in early stages)"
fi

# Check recent log activity
echo ""
echo "📋 Recent Activity:"
if [ -f "logs/wnba_full_collection.log" ]; then
    echo "   Latest from historical collection:"
    tail -3 logs/wnba_full_collection.log | sed 's/^/      /'
else
    echo "   Log file not found"
fi

# Quick recommendations
echo ""
echo "💡 Quick Commands:"
echo "   Monitor: python3 scripts/04_analysis/monitor_wnba_collection.py"
echo "   Watch:   python3 scripts/04_analysis/monitor_wnba_collection.py --watch"
echo "   Logs:    tail -f logs/wnba_full_collection.log"
echo ""

# Estimated completion
echo "⏱️  Estimated completion: $(date -d '+6 hours' +'%I:%M %p')"
echo "🎯 Target: 2,780+ WNBA game records (2021-2025)"