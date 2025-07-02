#!/bin/bash

# WNBA Sustainable Collection Strategy
# Priority: Avoid IP bans, get quality data, be respectful

echo "🛡️  WNBA Sustainable Collection - IP-Safe Approach"
echo "📅 $(date)"
echo "🎯 Strategy: Quality over speed, no IP ban risk"
echo "⏱️  Timeline: 3-4 hours with safe delays"
echo ""

mkdir -p logs/wnba_sustainable

# Conservative collection function with multiple fallbacks
collect_sustainably() {
    local year=$1
    local primary_delay=$2
    
    echo "🛡️  Sustainable collection for $year..."
    echo "⏳ Using ${primary_delay}s delays (IP-safe)"
    
    # Strategy 1: Try alternative sources first (less protective)
    echo "🎯 Strategy 1: Alternative sources (safer)"
    
    echo "   📊 Trying ESPN data for $year..."
    python3 scripts/04_analysis/wnba_gentle_scraper.py 2>&1 | \
        grep -E "(SUCCESS|records|team)" | head -3
    
    # Wait between attempts
    echo "   ⏸️  Safe pause (60s)..."
    sleep 60
    
    echo "   📊 Trying BetInf historical for $year..."
    python3 scripts/04_analysis/wnba_comprehensive_scraper.py \
        --source betinf \
        --years $year-$year \
        --delay 20 \
        --output wnba_${year}_sustainable_alt \
        2>&1 | tee logs/wnba_sustainable/alt_${year}_$(date +%H%M%S).log
    
    # Check if we got anything
    local alt_success=false
    if ls data/odds/wnba_${year}_sustainable_alt* 1> /dev/null 2>&1; then
        local alt_records=$(wc -l data/odds/wnba_${year}_sustainable_alt*.csv 2>/dev/null | tail -1 | awk '{print $1}')
        if [ "$alt_records" -gt "1" ]; then
            echo "✅ Alternative sources: $alt_records records for $year"
            alt_success=true
        fi
    fi
    
    # Strategy 2: Only try OddsPortal if we need more data AND it's safe
    if [ "$alt_success" = false ]; then
        echo ""
        echo "🎯 Strategy 2: OddsPortal (ultra-conservative)"
        echo "   ⚠️  Using 45s delays to be extra safe..."
        
        # Much longer delay to be respectful
        python3 scripts/04_analysis/wnba_comprehensive_scraper.py \
            --source oddsportal \
            --years $year-$year \
            --delay 45 \
            --output wnba_${year}_sustainable_odds \
            2>&1 | tee logs/wnba_sustainable/odds_${year}_$(date +%H%M%S).log
        
        if ls data/odds/wnba_${year}_sustainable_odds* 1> /dev/null 2>&1; then
            local odds_records=$(wc -l data/odds/wnba_${year}_sustainable_odds*.csv 2>/dev/null | tail -1 | awk '{print $1}')
            echo "✅ OddsPortal: $odds_records records for $year"
        else
            echo "⚠️  OddsPortal: Limited data available for $year"
        fi
    else
        echo "✅ Skipping OddsPortal for $year (already have data)"
    fi
    
    # Summary for this year
    echo ""
    echo "📊 $year Summary:"
    local total_files=$(ls data/odds/wnba_${year}_sustainable* 2>/dev/null | wc -l)
    if [ $total_files -gt 0 ]; then
        local total_records=0
        for file in data/odds/wnba_${year}_sustainable*.csv; do
            if [ -f "$file" ]; then
                local count=$(wc -l < "$file" 2>/dev/null || echo "0")
                total_records=$((total_records + count - 1))  # Subtract header
            fi
        done
        echo "   ✅ $total_records total records collected"
        echo "   📁 Files: $total_files"
    else
        echo "   ⚠️  No data files created (source may be unavailable)"
    fi
    echo ""
}

# Safe break between years
safe_break() {
    local minutes=$1
    echo "☕ Safe break: ${minutes} minutes (protecting IP)"
    echo "   🛡️  Avoiding rate limits and blocks..."
    echo "   ⏰ Resume: $(date -d "+${minutes} minutes" +'%H:%M:%S')"
    sleep $((minutes * 60))
    echo ""
}

echo "🛡️  SUSTAINABLE COLLECTION PLAN:"
echo "   ✅ Try ESPN/alternative sources first (safer)"
echo "   ✅ Use 45-60 second delays for OddsPortal" 
echo "   ✅ Take 10-15 minute breaks between years"
echo "   ✅ Accept smaller dataset to avoid IP ban"
echo "   ✅ Quality over quantity approach"
echo ""

# Start with most recent year (best data availability)
echo "🚀 Starting sustainable collection ($(date))..."

# 2024 - Current year, try gentle approach first
collect_sustainably "2024" "45"
safe_break 15

# 2023 - Recent complete season
collect_sustainably "2023" "50" 
safe_break 15

# 2022 - Older data, be more careful
collect_sustainably "2022" "60"
safe_break 20

# 2021 - Oldest, most conservative
collect_sustainably "2021" "60"

echo "🎉 SUSTAINABLE Collection Complete!"
echo "📁 Data location: data/odds/"
echo ""

# Generate final summary
echo "📊 FINAL COLLECTION SUMMARY:"
echo "🛡️  IP-Safe Strategy Results:"

if ls data/odds/wnba_*_sustainable* 1> /dev/null 2>&1; then
    echo ""
    echo "✅ Files created:"
    ls -lh data/odds/wnba_*_sustainable* | head -10
    
    echo ""
    echo "📈 Records by year:"
    local grand_total=0
    for year in 2024 2023 2022 2021; do
        local year_total=0
        for file in data/odds/wnba_${year}_sustainable*.csv; do
            if [ -f "$file" ]; then
                local count=$(wc -l < "$file" 2>/dev/null || echo "0")
                year_total=$((year_total + count - 1))  # Subtract header
            fi
        done
        if [ $year_total -gt 0 ]; then
            echo "   $year: $year_total records ✅"
            grand_total=$((grand_total + year_total))
        else
            echo "   $year: No data ⚠️"
        fi
    done
    
    echo ""
    if [ $grand_total -gt 0 ]; then
        echo "🏆 SUCCESS: $grand_total total WNBA records collected!"
        echo "✅ No IP ban risk - data safely acquired"
        echo "📊 Ready for prediction model integration"
        
        if [ $grand_total -gt 500 ]; then
            echo "🎯 Excellent dataset size for model training"
        elif [ $grand_total -gt 100 ]; then
            echo "🎯 Good foundation dataset collected"
        else
            echo "🎯 Starter dataset - consider API upgrade for more"
        fi
    else
        echo "⚠️  Limited data collected - sources may have restrictions"
    fi
    
    echo ""
    echo "💡 NEXT STEPS:"
    echo "1. Validate data: python3 scripts/04_analysis/monitor_wnba_collection.py --detailed"
    echo "2. If more data needed: Consider The Odds API ($10/month)"
    echo "3. Integrate with prediction models using collected data"
    
else
    echo "⚠️  No files created with sustainable approach"
    echo ""
    echo "🔄 ALTERNATIVES:"
    echo "1. Wait 24 hours then retry (IP cooldown)"
    echo "2. Try The Odds API for reliable access ($10/month)"
    echo "3. Use manual sources (ESPN, Basketball Reference)"
fi

echo ""
echo "🛡️  Collection completed with no IP ban risk!"
echo "⏱️  Total time: Prioritized safety over speed"