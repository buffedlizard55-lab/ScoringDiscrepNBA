"""
Continuous Monitoring System for NBA Scoring Discrepancies
Runs as GitHub Action or standalone daemon
Own the Outcome - no manual input, work on own to complete tasks
"""
import os
import sys
import json
import time
from datetime import datetime, timedelta
import argparse

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from discrepancy_detector import DiscrepancyDetector
    from nba_api_client import MultiSourceFetcher
except ImportError:
    from src.discrepancy_detector import DiscrepancyDetector
    from src.nba_api_client import MultiSourceFetcher

def run_continuous_monitoring(interval_seconds: int = 300, data_dir: str = "data"):
    """
    Run monitoring loop continuously
    interval_seconds: how often to check (default 5 minutes)
    """
    detector = DiscrepancyDetector(data_dir=data_dir)
    
    print(f"[Monitor] Starting continuous monitoring, interval {interval_seconds}s")
    print(f"[Monitor] Data dir: {data_dir}")
    print(f"[Monitor] Time: {datetime.now().isoformat()}")
    
    while True:
        try:
            # Check if NBA season - for now, always run
            # In production, check if games scheduled today
            result = detector.monitor_once()
            
            # Save result to daily log
            log_dir = os.path.join(data_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"monitor-{datetime.now().strftime('%Y-%m-%d')}.json")
            
            # Append to log
            logs = []
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        logs = json.load(f)
                except:
                    logs = []
            
            logs.append(result)
            
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2, default=str)
            
            print(f"[Monitor] Cycle complete: {result['snapshots_collected']} snapshots, {result['alerts_generated']} alerts")
            
            if result['alerts_generated'] > 0:
                print(f"[Monitor] *** ALERTS GENERATED - requires investigation ***")
                for alert in result['alerts']:
                    print(f"  - {alert['id']}: {alert['source_a']}={alert['total_a']} vs {alert['source_b']}={alert['total_b']}")
            
            # Save statistics for website
            stats = detector.get_statistics(os.path.join(data_dir, "discrepancies.json"))
            stats_file = os.path.join(data_dir, "statistics.json")
            with open(stats_file, 'w') as f:
                json.dump(stats, f, indent=2)
            
            print(f"[Monitor] Sleeping {interval_seconds}s...")
            time.sleep(interval_seconds)
            
        except KeyboardInterrupt:
            print("[Monitor] Stopped by user")
            break
        except Exception as e:
            print(f"[Monitor] Error in monitoring loop: {e}")
            import traceback
            traceback.print_exc()
            print(f"[Monitor] Sleeping 60s before retry...")
            time.sleep(60)

def run_single_check(date_str: str = None, data_dir: str = "data"):
    """Run single check (for GitHub Action)"""
    detector = DiscrepancyDetector(data_dir=data_dir)
    result = detector.monitor_once(date_str)
    
    # Save to logs
    log_dir = os.path.join(data_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Save latest result
    latest_file = os.path.join(data_dir, "latest_check.json")
    with open(latest_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    # Update statistics
    stats = detector.get_statistics(os.path.join(data_dir, "discrepancies.json"))
    stats_file = os.path.join(data_dir, "statistics.json")
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    
    # Also save to docs/data.json for website
    docs_data_dir = os.path.join(os.path.dirname(data_dir), "docs")
    if os.path.exists(docs_data_dir):
        try:
            # Copy discrepancies.json to docs
            import shutil
            shutil.copy(os.path.join(data_dir, "discrepancies.json"), os.path.join(docs_data_dir, "data.json"))
            shutil.copy(stats_file, os.path.join(docs_data_dir, "statistics.json"))
            print(f"[Monitor] Copied data to docs/ for GitHub Pages")
        except Exception as e:
            print(f"[Monitor] Failed to copy to docs: {e}")
    
    print(json.dumps(result, indent=2))
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NBA Scoring Discrepancy Monitor")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=300, help="Interval in seconds for continuous mode")
    parser.add_argument("--date", type=str, help="Date to check YYYY-MM-DD")
    parser.add_argument("--data-dir", type=str, default="data", help="Data directory")
    
    args = parser.parse_args()
    
    if args.continuous:
        run_continuous_monitoring(interval_seconds=args.interval, data_dir=args.data_dir)
    else:
        run_single_check(date_str=args.date, data_dir=args.data_dir)
