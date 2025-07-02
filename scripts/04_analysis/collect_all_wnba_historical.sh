#!/bin/bash

# WNBA Historical Odds Collection Script
# Collects data from 2021-2024 systematically with proper delays

echo "🏀 Starting WNBA Historical Odds Collection (2021-2024)"
echo "📅 $(date)"
echo "⏱️  Estimated completion: 6-8 hours"
echo ""

# Create log directory
mkdir -p logs/wnba_collection

# Function to collect data for a specific year
collect_year() {
    local year=$1
    local delay=$2
    
    echo "📊 Collecting $year WNBA data..."
    echo "⏳ Using ${delay}s delays to respect rate limits"
    
    # Run the scraper
    python3 scripts/04_analysis/wnba_comprehensive_scraper.py \
        --source oddsportal \
        --years $year-$year \
        --delay $delay \
        --output wnba_${year}_historical \
        2>&1 | tee logs/wnba_collection/wnba_${year}_$(date +%Y%m%d_%H%M%S).log
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "✅ $year collection completed successfully"
        
        # Check if data was actually collected
        if ls data/odds/wnba_${year}_historical* 1> /dev/null 2>&1; then
            local record_count=$(wc -l data/odds/wnba_${year}_historical*.csv 2>/dev/null | tail -1 | awk '{print $1}')
            echo "📊 Collected approximately $record_count records for $year"
        else
            echo "⚠️  No data files found for $year"
        fi
    else
        echo "❌ $year collection failed with exit code $exit_code"
        echo "📝 Check logs/wnba_collection/wnba_${year}_*.log for details"
    fi
    
    echo ""
}

# Function to take a break between collections
take_break() {
    local minutes=$1
    echo "☕ Taking a ${minutes}-minute break to be respectful to servers..."
    echo "⏰ Resume time: $(date -d "+${minutes} minutes" +'%H:%M:%S')"
    sleep $((minutes * 60))
    echo "🚀 Resuming collection..."
    echo ""
}

# Main collection sequence
echo "🎯 Collection Strategy:"
echo "   - Start with 2023 (most recent complete season)"
echo "   - Then 2022, 2021 (working backwards)"
echo "   - 2024 is already running in background"
echo "   - Use increasing delays for older years"
echo ""

# Wait a moment to let any existing 2024 collection finish/stabilize
echo "⏳ Waiting 2 minutes for any existing collection to stabilize..."
sleep 120

# Collect 2023 data (recent, good data availability)
collect_year "2023" "12"
take_break 30

# Collect 2022 data (older, might need longer delays)
collect_year "2022" "15"
take_break 45

# Collect 2021 data (oldest, use longest delays)
collect_year "2021" "18"

echo "🎉 WNBA Historical Collection Complete!"
echo "📁 Data saved in: data/odds/"
echo "📋 Collection summary:"

# Generate summary
if ls data/odds/wnba_*_historical* 1> /dev/null 2>&1; then
    echo ""
    echo "📊 Files collected:"
    ls -lh data/odds/wnba_*_historical*
    
    echo ""
    echo "📈 Total records by year:"
    for file in data/odds/wnba_*_historical*.csv; do
        if [ -f "$file" ]; then
            year=$(echo "$file" | grep -o '20[0-9][0-9]')
            records=$(wc -l < "$file" 2>/dev/null || echo "0")
            echo "   $year: $records records"
        fi
    done
    
    echo ""
    echo "✅ Next steps:"
    echo "1. Run: python3 scripts/04_analysis/validate_wnba_data.py"
    echo "2. Integrate with your prediction models"
    echo "3. Set up daily collection for current 2025 season"
else
    echo "⚠️  No data files found. Check logs for details."
fi

echo ""
echo "🏆 Your WNBA prediction engine is now enhanced with historical odds data!"