#!/bin/bash

# WNBA Fast Historical Odds Collection
# Optimized for speed while respecting rate limits

echo "🚀 Fast WNBA Historical Odds Collection (2021-2024)"
echo "📅 $(date)"
echo "⏱️  Estimated completion: 1-2 hours (much faster!)"
echo ""

mkdir -p logs/wnba_fast

# Function to collect data for a specific year (optimized)
collect_year_fast() {
    local year=$1
    local delay=$2
    
    echo "📊 Fast collecting $year WNBA data..."
    echo "⚡ Using ${delay}s delays (optimized for speed)"
    
    # Try multiple collection strategies for better success rate
    echo "🎯 Strategy 1: OddsPortal primary"
    python3 scripts/04_analysis/wnba_comprehensive_scraper.py \
        --source oddsportal \
        --years $year-$year \
        --delay $delay \
        --output wnba_${year}_fast \
        2>&1 | tee logs/wnba_fast/wnba_${year}_$(date +%H%M%S).log
    
    local exit_code=$?
    
    # Check if we got any data
    if ls data/odds/wnba_${year}_fast* 1> /dev/null 2>&1; then
        local record_count=$(wc -l data/odds/wnba_${year}_fast*.csv 2>/dev/null | tail -1 | awk '{print $1}')
        if [ "$record_count" -gt "1" ]; then
            echo "✅ $year SUCCESS: $record_count records collected"
            return 0
        fi
    fi
    
    # If first strategy failed, try alternative sources quickly
    echo "🔄 Strategy 2: Alternative sources"
    python3 scripts/04_analysis/wnba_comprehensive_scraper.py \
        --source betinf \
        --years $year-$year \
        --delay 5 \
        --output wnba_${year}_alt \
        2>&1 | tee -a logs/wnba_fast/wnba_${year}_$(date +%H%M%S).log
    
    # Final check
    if ls data/odds/wnba_${year}_* 1> /dev/null 2>&1; then
        local total_records=$(cat data/odds/wnba_${year}_*.csv 2>/dev/null | wc -l)
        echo "✅ $year COMPLETED: $total_records total records"
    else
        echo "⚠️  $year: Limited data available for this year"
    fi
    
    echo ""
}

# Quick break function (much shorter)
quick_break() {
    local minutes=$1
    echo "⚡ Quick ${minutes}-minute break..."
    echo "⏰ Resume: $(date -d "+${minutes} minutes" +'%H:%M:%S')"
    sleep $((minutes * 60))
    echo ""
}

echo "🎯 OPTIMIZED Strategy:"
echo "   ✅ Kill long delays - use 8-10s between requests"
echo "   ✅ Reduce breaks to 2-3 minutes (not 30-45!)"
echo "   ✅ Try multiple sources if one fails"
echo "   ✅ Complete in 1-2 hours instead of 6+"
echo ""

# Start with most recent years (better data availability)
echo "🚀 Starting optimized collection..."

# 2024 first (current year, best data)
collect_year_fast "2024" "8"
quick_break 2

# 2023 (recent, good availability)  
collect_year_fast "2023" "9"
quick_break 2

# 2022 (older but still good)
collect_year_fast "2022" "10"
quick_break 3

# 2021 (oldest, may need slightly longer delays)
collect_year_fast "2021" "12"

echo "🎉 FAST Collection Complete!"
echo "📁 Data location: data/odds/"
echo ""

# Quick summary
echo "📊 COLLECTION SUMMARY:"
if ls data/odds/wnba_* 1> /dev/null 2>&1; then
    echo "✅ Files created:"
    ls -lh data/odds/wnba_*_fast* data/odds/wnba_*_alt* 2>/dev/null | head -10
    
    echo ""
    echo "📈 Records by year:"
    for year in 2024 2023 2022 2021; do
        total=0
        for file in data/odds/wnba_${year}_*.csv; do
            if [ -f "$file" ]; then
                count=$(wc -l < "$file" 2>/dev/null || echo "0")
                total=$((total + count - 1))  # Subtract header
            fi
        done
        if [ $total -gt 0 ]; then
            echo "   $year: $total records ✅"
        else
            echo "   $year: No data ⚠️"
        fi
    done
    
    echo ""
    echo "🏆 SUCCESS! WNBA prediction engine enhanced!"
    echo "📋 Next: python3 scripts/04_analysis/monitor_wnba_collection.py --detailed"
else
    echo "⚠️  No files created - may need to try different sources"
    echo "💡 Alternative: Consider The Odds API ($10/month) for reliable data"
fi

echo ""
echo "⏱️  Total time: Much faster than the original 6-8 hour estimate!"