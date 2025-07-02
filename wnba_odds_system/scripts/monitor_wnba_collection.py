#!/usr/bin/env python3
"""
WNBA Data Collection Monitor
Real-time monitoring of WNBA odds collection progress

Usage:
    python3 monitor_wnba_collection.py
    python3 monitor_wnba_collection.py --detailed
"""

import os
import sys
import time
import glob
import pandas as pd
from datetime import datetime
import argparse
import subprocess

def get_collection_status():
    """Check if any WNBA scrapers are currently running"""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        processes = result.stdout
        
        running_scrapers = []
        for line in processes.split('\n'):
            if 'wnba_comprehensive_scraper' in line and 'grep' not in line:
                parts = line.split()
                if len(parts) >= 11:
                    pid = parts[1]
                    cpu = parts[2]
                    mem = parts[3]
                    runtime = parts[9]
                    running_scrapers.append({
                        'pid': pid,
                        'cpu': f"{cpu}%",
                        'memory': f"{mem}%",
                        'runtime': runtime
                    })
        
        return running_scrapers
    except Exception as e:
        print(f"Error checking process status: {e}")
        return []

def scan_data_files():
    """Scan for collected WNBA data files"""
    data_dir = "data/odds"
    files_found = []
    
    if not os.path.exists(data_dir):
        return files_found
    
    # Look for WNBA data files
    patterns = [
        "wnba_*_historical*.csv",
        "wnba_*_historical*.parquet", 
        "wnba_gentle_collection*.csv",
        "wnba_odds_scraped*.csv"
    ]
    
    for pattern in patterns:
        matches = glob.glob(os.path.join(data_dir, pattern))
        for file_path in matches:
            try:
                stat_info = os.stat(file_path)
                file_size = stat_info.st_size
                mod_time = datetime.fromtimestamp(stat_info.st_mtime)
                
                # Try to get record count
                record_count = "Unknown"
                if file_path.endswith('.csv'):
                    try:
                        df = pd.read_csv(file_path)
                        record_count = len(df)
                    except:
                        try:
                            # Fallback: count lines
                            with open(file_path, 'r') as f:
                                record_count = sum(1 for line in f) - 1  # Subtract header
                        except:
                            pass
                
                files_found.append({
                    'filename': os.path.basename(file_path),
                    'size_mb': round(file_size / 1024 / 1024, 2),
                    'records': record_count,
                    'modified': mod_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'path': file_path
                })
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
    
    return sorted(files_found, key=lambda x: x['modified'], reverse=True)

def analyze_data_quality(files_info):
    """Analyze the quality and coverage of collected data"""
    total_records = 0
    years_covered = set()
    sources_found = set()
    
    for file_info in files_info:
        if isinstance(file_info['records'], int):
            total_records += file_info['records']
        
        # Extract year from filename
        filename = file_info['filename']
        for year in ['2021', '2022', '2023', '2024', '2025']:
            if year in filename:
                years_covered.add(year)
                break
        
        # Try to analyze source from the file
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(file_info['path'], nrows=10)  # Read just a few rows
                if 'source' in df.columns:
                    sources_found.update(df['source'].dropna().unique())
        except:
            pass
    
    return {
        'total_records': total_records,
        'years_covered': sorted(years_covered),
        'sources_found': list(sources_found),
        'files_count': len(files_info)
    }

def print_status_summary(running_scrapers, files_info, quality_info):
    """Print a formatted status summary"""
    print(f"\n📊 WNBA DATA COLLECTION STATUS")
    print(f"{'='*50}")
    print(f"🕐 Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Running processes
    print(f"\n🔄 Active Scrapers: {len(running_scrapers)}")
    if running_scrapers:
        for scraper in running_scrapers:
            print(f"   PID {scraper['pid']}: CPU {scraper['cpu']}, Memory {scraper['memory']}, Runtime {scraper['runtime']}")
    else:
        print("   No active scrapers running")
    
    # Data files
    print(f"\n📁 Data Files Found: {quality_info['files_count']}")
    if files_info:
        print(f"   Total Records: {quality_info['total_records']:,}")
        print(f"   Years Covered: {', '.join(quality_info['years_covered'])}")
        print(f"   Sources: {', '.join(quality_info['sources_found']) if quality_info['sources_found'] else 'Not detected'}")
        
        print(f"\n📋 Recent Files:")
        for file_info in files_info[:5]:  # Show top 5 most recent
            print(f"   {file_info['filename']} - {file_info['records']} records, {file_info['size_mb']} MB")
    else:
        print("   No data files found yet")

def print_detailed_analysis(files_info):
    """Print detailed analysis of all files"""
    print(f"\n🔍 DETAILED FILE ANALYSIS")
    print(f"{'='*50}")
    
    if not files_info:
        print("No files to analyze")
        return
    
    for file_info in files_info:
        print(f"\n📄 {file_info['filename']}")
        print(f"   Size: {file_info['size_mb']} MB")
        print(f"   Records: {file_info['records']}")
        print(f"   Modified: {file_info['modified']}")
        print(f"   Path: {file_info['path']}")
        
        # Try to get more details from the file
        if file_info['filename'].endswith('.csv'):
            try:
                df = pd.read_csv(file_info['path'], nrows=5)
                print(f"   Columns: {', '.join(df.columns)}")
                if 'date' in df.columns:
                    dates = pd.to_datetime(df['date'], errors='coerce').dropna()
                    if not dates.empty:
                        print(f"   Date Range: {dates.min().strftime('%Y-%m-%d')} to {dates.max().strftime('%Y-%m-%d')}")
                if 'team' in df.columns:
                    teams = df['team'].dropna().unique()[:5]
                    print(f"   Teams (sample): {', '.join(teams)}")
            except Exception as e:
                print(f"   Analysis Error: {e}")

def get_collection_progress():
    """Estimate overall collection progress"""
    target_years = ['2021', '2022', '2023', '2024']
    files_info = scan_data_files()
    
    years_with_data = set()
    for file_info in files_info:
        filename = file_info['filename']
        for year in target_years:
            if year in filename and isinstance(file_info['records'], int) and file_info['records'] > 0:
                years_with_data.add(year)
    
    progress_pct = (len(years_with_data) / len(target_years)) * 100
    
    return {
        'target_years': target_years,
        'completed_years': list(years_with_data),
        'progress_percent': progress_pct
    }

def main():
    parser = argparse.ArgumentParser(description="Monitor WNBA data collection progress")
    parser.add_argument("--detailed", action="store_true", help="Show detailed file analysis")
    parser.add_argument("--watch", action="store_true", help="Continuous monitoring mode")
    parser.add_argument("--interval", type=int, default=30, help="Update interval for watch mode (seconds)")
    
    args = parser.parse_args()
    
    def run_check():
        running_scrapers = get_collection_status()
        files_info = scan_data_files()
        quality_info = analyze_data_quality(files_info)
        progress_info = get_collection_progress()
        
        print_status_summary(running_scrapers, files_info, quality_info)
        
        # Progress bar
        print(f"\n📈 Collection Progress: {progress_info['progress_percent']:.1f}%")
        completed = len(progress_info['completed_years'])
        total = len(progress_info['target_years'])
        bar_length = 20
        filled = int(bar_length * completed / total)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"   [{bar}] {completed}/{total} years completed")
        
        if args.detailed:
            print_detailed_analysis(files_info)
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        if not running_scrapers and progress_info['progress_percent'] < 100:
            print("   🚀 Start collection: ./scripts/04_analysis/collect_all_wnba_historical.sh")
        elif running_scrapers:
            print("   ⏳ Collection in progress - be patient!")
        if progress_info['progress_percent'] >= 75:
            print("   📊 Ready to analyze data and integrate with prediction models")
        
        return running_scrapers, files_info, quality_info
    
    if args.watch:
        print("👀 Starting continuous monitoring mode...")
        print(f"🔄 Updating every {args.interval} seconds")
        print("📊 Press Ctrl+C to exit")
        
        try:
            while True:
                os.system('clear' if os.name == 'posix' else 'cls')
                run_check()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n⏹️  Monitoring stopped")
    else:
        run_check()

if __name__ == "__main__":
    main()