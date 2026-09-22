#!/usr/bin/env python3
"""
EUJOBHUB - SCHEDULER MONITOR
Real-time status monitoring while scheduler is running
"""

import json
import csv
import time
from pathlib import Path
from datetime import datetime
from collections import Counter

class SchedulerMonitor:
    def __init__(self):
        self.schedule_file = Path("reels_schedule.json")
        self.log_file = Path("reels_publish_log.csv")
        self.r2_log = Path("r2_upload_log.csv")
    
    def load_schedule(self):
        """Load current schedule"""
        if not self.schedule_file.exists():
            return None
        
        try:
            with open(self.schedule_file, "r") as f:
                return json.load(f)
        except:
            return None
    
    def load_log(self):
        """Load publishing log"""
        if not self.log_file.exists():
            return []
        
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except:
            return []
    
    def get_schedule_stats(self):
        """Get schedule statistics"""
        schedule = self.load_schedule()
        
        if not schedule:
            return None
        
        statuses = Counter(r.get("status", "unknown") for r in schedule)
        
        pending = [r for r in schedule if r.get("status") == "pending"]
        pending_sorted = sorted(pending, key=lambda r: r.get("publish_time", ""))
        
        return {
            "total": len(schedule),
            "pending": statuses["pending"],
            "published": statuses["published"],
            "failed": statuses["failed"],
            "next": pending_sorted[0] if pending_sorted else None,
            "success_rate": (statuses["published"] / len(schedule) * 100) if len(schedule) > 0 else 0
        }
    
    def get_recent_activity(self):
        """Get recent published reels"""
        log = self.load_log()
        
        if not log:
            return []
        
        return log[-10:]
    
    def get_next_reel_info(self):
        """Get info about next reel to publish"""
        schedule = self.load_schedule()
        
        if not schedule:
            return None
        
        pending = [r for r in schedule if r.get("status") == "pending"]
        
        if not pending:
            return None
        
        next_reel = sorted(pending, key=lambda r: r.get("publish_time", ""))[0]
        
        # Calculate wait time
        publish_time = datetime.fromisoformat(next_reel["publish_time"])
        now = datetime.now()
        wait = publish_time - now
        
        hours = wait.total_seconds() / 3600
        minutes = (wait.total_seconds() % 3600) / 60
        
        return {
            "video_number": next_reel["video_number"],
            "publish_time": next_reel["publish_time"],
            "platforms": next_reel["platforms"],
            "hours_until": hours,
            "minutes_until": minutes
        }
    
    def print_dashboard(self):
        """Print real-time dashboard"""
        import os
        import sys
        
        # Clear screen
        os.system("cls" if os.name == "nt" else "clear")
        
        print("\033[1;36m" + "=" * 70)
        print("EUJOBHUB - SCHEDULER MONITOR")
        print("=" * 70 + "\033[0m")
        print(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Schedule Status
        stats = self.get_schedule_stats()
        
        if stats:
            print("\033[1;33m--- SCHEDULE STATUS ---\033[0m")
            print(f"Total reels:    {stats['total']}")
            print(f"✓ Published:    {stats['published']} ({stats['success_rate']:.1f}%)")
            print(f"⏳ Pending:      {stats['pending']}")
            print(f"✗ Failed:       {stats['failed']}")
            print()
        else:
            print("\033[1;31mNo schedule found. Create one first:\033[0m")
            print("  python bulk_reels_scheduler.py\n")
            return
        
        # Next Reel
        next_info = self.get_next_reel_info()
        
        if next_info:
            print("\033[1;33m--- NEXT REEL ---\033[0m")
            print(f"Video #:        {next_info['video_number']}")
            print(f"Platforms:      {', '.join(next_info['platforms'])}")
            print(f"Scheduled:      {next_info['publish_time']}")
            
            if next_info['hours_until'] > 0:
                print(f"Time until:     {int(next_info['hours_until'])}h {int(next_info['minutes_until'])}m")
            else:
                print(f"\033[1;31mOVERDUE - Should have published already!\033[0m")
            print()
        else:
            print("\033[1;32m--- ALL REELS PUBLISHED! ---\033[0m\n")
        
        # Recent Activity
        recent = self.get_recent_activity()
        
        if recent:
            print("\033[1;33m--- RECENT PUBLISHED REELS ---\033[0m")
            for entry in reversed(recent[-5:]):
                video_num = entry.get("video_number")
                status = entry.get("status")
                platforms = entry.get("platforms", "")
                published_at = entry.get("published_at", "")[:16]
                
                symbol = "✓" if status == "published" else "✗"
                print(f"{symbol} #{video_num} ({platforms}) - {published_at}")
            print()
        
        # Summary
        print("\033[1;33m--- SCHEDULER CONTROL ---\033[0m")
        print("In terminal where scheduler is running:")
        print("  Press Ctrl+C to pause")
        print("  Restart anytime to continue where it left off\n")
        
        # Troubleshooting
        if stats["failed"] > 0:
            print("\033[1;31m⚠️  ISSUES DETECTED ---\033[0m")
            print(f"Failed reels: {stats['failed']}")
            print("Fix with: python reels_manager.py → Option 4\n")

def main():
    print("EUJOBHUB - SCHEDULER MONITOR")
    print("Press Ctrl+C to exit\n")
    print("Updating every 10 seconds...\n")
    
    monitor = SchedulerMonitor()
    
    try:
        while True:
            monitor.print_dashboard()
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")

if __name__ == "__main__":
    main()
