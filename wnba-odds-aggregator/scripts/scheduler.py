import schedule
import time
import subprocess

def fetch_live_odds():
    subprocess.run(["python", "scripts/live_fetcher.py"])

def backup_db():
    subprocess.run(["python", "scripts/backup_db.py"])

def data_quality_report():
    subprocess.run(["python", "scripts/data_quality_report.py"])

schedule.every().day.at("11:00").do(fetch_live_odds)
schedule.every().day.at("11:10").do(data_quality_report)
schedule.every().day.at("11:15").do(backup_db)

if __name__ == "__main__":
    print("Scheduler started. Will run live odds fetcher at 11:00, data quality at 11:10, and backup at 11:15 AM daily.")
    while True:
        schedule.run_pending()
        time.sleep(60) 