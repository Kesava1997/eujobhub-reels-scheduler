#!/usr/bin/env python3
"""
EUJOBHUB - REELS MANAGER
Manage videos, monitor publishing, and fix issues
"""

import json
import csv
from pathlib import Path
from datetime import datetime
from collections import Counter
import requests

print("=" * 70)
print("EUJOBHUB - REELS MANAGER")
print("=" * 70)

def menu():
    print("\n" + "=" * 70)
    print("REELS MANAGER MENU")
    print("=" * 70)
    print("1. Check R2 video inventory")
    print("2. View schedule statistics")
    print("3. View publishing results")
    print("4. Find and fix failed reels")
    print("5. Verify video URLs")
    print("6. Export schedule to CSV")
    print("7. Compare schedule vs log")
    print("8. Clear old logs")
    print("9. Generate report")
    print("10. Exit")
    print("=" * 70)

def check_r2_inventory():
    """List videos in R2 bucket"""
    print("\n--- R2 VIDEO INVENTORY ---\n")
    
    # Try to read from bulk upload log
    log_file = Path("r2_upload_log.csv")
    
    if not log_file.exists():
        print("No R2 upload log found (r2_upload_log.csv)")
        return
    
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            videos = {
                "uploaded": [],
                "failed": [],
                "skipped": []
            }
            
            for row in reader:
                status = row.get("status", "").upper()
                filename = row.get("file", "")
                
                if status == "UPLOADED":
                    videos["uploaded"].append(filename)
                elif status == "FAILED":
                    videos["failed"].append(filename)
                elif status == "SKIPPED":
                    videos["skipped"].append(filename)
            
            print(f"✓ Uploaded: {len(videos['uploaded'])} videos")
            print(f"✗ Failed: {len(videos['failed'])} videos")
            print(f"~ Skipped: {len(videos['skipped'])} videos")
            
            if videos["failed"]:
                print("\nFailed uploads (retry these):")
                for f in videos["failed"][:10]:
                    print(f"  - {f}")
            
            # Check if URLs are accessible
            print("\nVerifying R2 accessibility...")
            test_url = "https://pub-b920483add26487c964812cdb7716dd3.r2.dev/1.mp4"
            
            try:
                response = requests.head(test_url, timeout=10)
                if response.status_code == 200:
                    print("✓ R2 bucket is accessible")
                else:
                    print(f"⚠ R2 returned {response.status_code}")
            except:
                print("✗ Cannot reach R2 bucket")
    
    except Exception as e:
        print(f"ERROR: {e}")

def view_schedule_stats():
    """View schedule statistics"""
    print("\n--- SCHEDULE STATISTICS ---\n")
    
    schedule_file = Path("reels_schedule.json")
    
    if not schedule_file.exists():
        print("No schedule found (create one first)")
        return
    
    try:
        with open(schedule_file, "r") as f:
            schedule = json.load(f)
        
        # Count by status
        statuses = [r.get("status", "unknown") for r in schedule]
        status_count = Counter(statuses)
        
        print(f"Total reels: {len(schedule)}")
        print(f"Pending: {status_count['pending']}")
        print(f"Published: {status_count['published']}")
        print(f"Failed: {status_count['failed']}")
        
        # Earliest and latest dates
        if schedule:
            times = [r.get("publish_time") for r in schedule if r.get("publish_time")]
            if times:
                earliest = min(times)
                latest = max(times)
                print(f"\nSchedule period:")
                print(f"  From: {earliest}")
                print(f"  To:   {latest}")
        
        # Next pending
        pending = [r for r in schedule if r.get("status") == "pending"]
        if pending:
            next_reel = sorted(pending, key=lambda r: r.get("publish_time", ""))[0]
            print(f"\nNext pending:")
            print(f"  Video #{next_reel['video_number']}")
            print(f"  Time: {next_reel['publish_time']}")
            print(f"  Platforms: {', '.join(next_reel.get('platforms', []))}")
        
        # Summary
        success_rate = (status_count['published'] / len(schedule) * 100) if len(schedule) > 0 else 0
        print(f"\nSuccess rate: {success_rate:.1f}%")
    
    except Exception as e:
        print(f"ERROR: {e}")

def view_publishing_results():
    """View recent publishing results"""
    print("\n--- PUBLISHING RESULTS ---\n")
    
    log_file = Path("reels_publish_log.csv")
    
    if not log_file.exists():
        print("No publishing log yet")
        return
    
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        print(f"Total published: {len(rows)}\n")
        
        # Count platforms
        ig_count = sum(1 for r in rows if "instagram" in r.get("platforms", ""))
        fb_count = sum(1 for r in rows if "facebook" in r.get("platforms", ""))
        
        print(f"Instagram: {ig_count}")
        print(f"Facebook: {fb_count}")
        
        # Recent results
        print("\nRecent 10:")
        for row in rows[-10:]:
            video_num = row.get("video_number")
            status = row.get("status")
            platforms = row.get("platforms")
            time = row.get("published_at", "")[:19]
            
            symbol = "✓" if status == "published" else "✗"
            print(f"  {symbol} #{video_num} ({platforms}) - {time}")
        
        # Errors
        errors = [r for r in rows if r.get("error")]
        if errors:
            print(f"\nErrors ({len(errors)}):")
            for err in errors[-5:]:
                print(f"  #{err['video_number']}: {err['error'][:50]}")
    
    except Exception as e:
        print(f"ERROR: {e}")

def find_and_fix_failures():
    """Find failed reels and fix them"""
    print("\n--- FIX FAILED REELS ---\n")
    
    schedule_file = Path("reels_schedule.json")
    
    if not schedule_file.exists():
        print("No schedule found")
        return
    
    try:
        with open(schedule_file, "r") as f:
            schedule = json.load(f)
        
        failed = [r for r in schedule if r.get("status") == "failed"]
        
        if not failed:
            print("No failed reels!")
            return
        
        print(f"Found {len(failed)} failed reels:\n")
        
        for i, reel in enumerate(failed[:10]):
            print(f"{i+1}. Video #{reel['video_number']}")
            if reel.get("error"):
                print(f"   Error: {reel['error'][:60]}")
            print()
        
        # Ask to restore
        restore = input("Restore all failed reels to pending? (yes/no): ").strip().lower()
        
        if restore == "yes":
            for reel in failed:
                reel["status"] = "pending"
                reel["error"] = ""
            
            with open(schedule_file, "w") as f:
                json.dump(schedule, f, indent=2, default=str)
            
            print(f"\n✓ {len(failed)} reels restored to pending")
            print("Restart scheduler to try again")
        else:
            print("\nNo changes made")
    
    except Exception as e:
        print(f"ERROR: {e}")

def verify_video_urls():
    """Check if all R2 video URLs are accessible"""
    print("\n--- VERIFY VIDEO URLs ---\n")
    
    schedule_file = Path("reels_schedule.json")
    
    if not schedule_file.exists():
        print("No schedule found")
        return
    
    try:
        with open(schedule_file, "r") as f:
            schedule = json.load(f)
        
        print("Checking video URLs...")
        print("(Testing first 10 videos)\n")
        
        working = 0
        broken = 0
        
        for reel in schedule[:10]:
            url = reel.get("r2_url")
            video_num = reel.get("video_number")
            
            try:
                response = requests.head(url, timeout=10)
                
                if response.status_code == 200:
                    size_mb = int(response.headers.get("content-length", 0)) / (1024 * 1024)
                    print(f"✓ Video #{video_num}: {size_mb:.1f} MB")
                    working += 1
                else:
                    print(f"✗ Video #{video_num}: HTTP {response.status_code}")
                    broken += 1
            
            except Exception as e:
                print(f"✗ Video #{video_num}: {e}")
                broken += 1
        
        print(f"\nResult: {working} working, {broken} broken")
    
    except Exception as e:
        print(f"ERROR: {e}")

def export_to_csv():
    """Export schedule to CSV"""
    print("\n--- EXPORT SCHEDULE ---\n")
    
    schedule_file = Path("reels_schedule.json")
    
    if not schedule_file.exists():
        print("No schedule found")
        return
    
    try:
        with open(schedule_file, "r") as f:
            schedule = json.load(f)
        
        output_file = Path("schedule_export.csv")
        
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            
            writer.writerow([
                "Video #",
                "Status",
                "Platforms",
                "Scheduled Time",
                "Instagram Container ID",
                "Facebook Video ID",
                "Error"
            ])
            
            for reel in schedule:
                writer.writerow([
                    reel.get("video_number"),
                    reel.get("status"),
                    ", ".join(reel.get("platforms", [])),
                    reel.get("publish_time"),
                    reel.get("ig_container_id", ""),
                    reel.get("fb_video_id", ""),
                    reel.get("error", "")
                ])
        
        print(f"✓ Exported to {output_file}")
        print(f"  Rows: {len(schedule)}")
    
    except Exception as e:
        print(f"ERROR: {e}")

def compare_schedule_vs_log():
    """Compare schedule with publishing log"""
    print("\n--- COMPARE SCHEDULE VS LOG ---\n")
    
    schedule_file = Path("reels_schedule.json")
    log_file = Path("reels_publish_log.csv")
    
    if not schedule_file.exists():
        print("No schedule found")
        return
    
    if not log_file.exists():
        print("No publishing log found")
        return
    
    try:
        with open(schedule_file, "r") as f:
            schedule = json.load(f)
        
        with open(log_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            log_videos = {int(r["video_number"]): r for r in reader}
        
        # Find discrepancies
        schedule_set = {r["video_number"] for r in schedule}
        log_set = set(log_videos.keys())
        
        in_schedule_not_log = schedule_set - log_set
        in_log_not_schedule = log_set - schedule_set
        
        print(f"Schedule: {len(schedule)} reels")
        print(f"Log: {len(log_videos)} entries")
        
        if in_schedule_not_log:
            print(f"\nIn schedule but not logged yet: {len(in_schedule_not_log)}")
            print(f"  (Videos pending or in progress)")
        
        if in_log_not_schedule:
            print(f"\nIn log but not in schedule: {len(in_log_not_schedule)}")
            print(f"  {sorted(list(in_log_not_schedule))[:20]}")
    
    except Exception as e:
        print(f"ERROR: {e}")

def clear_old_logs():
    """Archive old logs"""
    print("\n--- ARCHIVE OLD LOGS ---\n")
    
    log_file = Path("reels_publish_log.csv")
    
    if not log_file.exists():
        print("No log to archive")
        return
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"reels_publish_log_archive_{timestamp}.csv"
        
        import shutil
        shutil.copy(log_file, archive_name)
        
        # Clear log
        with open(log_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "video_number",
                "status",
                "platforms",
                "ig_container_id",
                "fb_video_id",
                "publish_time",
                "published_at",
                "error"
            ])
        
        print(f"✓ Current log archived to {archive_name}")
        print(f"✓ New log created")
    
    except Exception as e:
        print(f"ERROR: {e}")

def generate_report():
    """Generate comprehensive report"""
    print("\n--- GENERATING REPORT ---\n")
    
    schedule_file = Path("reels_schedule.json")
    log_file = Path("reels_publish_log.csv")
    r2_log = Path("r2_upload_log.csv")
    
    report_file = Path("reels_report.txt")
    
    try:
        with open(report_file, "w", encoding="utf-8") as report:
            report.write("=" * 70 + "\n")
            report.write("EUJOBHUB - REELS PUBLISHING REPORT\n")
            report.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            report.write("=" * 70 + "\n\n")
            
            # Schedule stats
            if schedule_file.exists():
                with open(schedule_file, "r") as f:
                    schedule = json.load(f)
                
                statuses = Counter(r.get("status") for r in schedule)
                
                report.write("SCHEDULE STATUS\n")
                report.write("-" * 70 + "\n")
                report.write(f"Total reels: {len(schedule)}\n")
                report.write(f"Pending: {statuses['pending']}\n")
                report.write(f"Published: {statuses['published']}\n")
                report.write(f"Failed: {statuses['failed']}\n")
                
                if len(schedule) > 0:
                    success = statuses['published'] / len(schedule) * 100
                    report.write(f"Success rate: {success:.1f}%\n")
                report.write("\n")
            
            # Publishing results
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                
                ig_count = sum(1 for r in rows if "instagram" in r.get("platforms", ""))
                fb_count = sum(1 for r in rows if "facebook" in r.get("platforms", ""))
                
                report.write("PUBLISHING RESULTS\n")
                report.write("-" * 70 + "\n")
                report.write(f"Total published: {len(rows)}\n")
                report.write(f"Instagram: {ig_count}\n")
                report.write(f"Facebook: {fb_count}\n")
                
                errors = [r for r in rows if r.get("error")]
                report.write(f"Errors: {len(errors)}\n")
                report.write("\n")
            
            # R2 uploads
            if r2_log.exists():
                with open(r2_log, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                
                uploaded = sum(1 for r in rows if r.get("status") == "UPLOADED")
                failed = sum(1 for r in rows if r.get("status") == "FAILED")
                
                report.write("R2 VIDEO UPLOADS\n")
                report.write("-" * 70 + "\n")
                report.write(f"Total uploaded: {uploaded}\n")
                report.write(f"Failed: {failed}\n")
                report.write("\n")
            
            report.write("=" * 70 + "\n")
            report.write("END OF REPORT\n")
            report.write("=" * 70 + "\n")
        
        print(f"✓ Report generated: {report_file}")
        
        with open(report_file, "r") as f:
            print("\n" + f.read())
    
    except Exception as e:
        print(f"ERROR: {e}")

def main():
    while True:
        menu()
        choice = input("Select option (1-10): ").strip()
        
        if choice == "1":
            check_r2_inventory()
        elif choice == "2":
            view_schedule_stats()
        elif choice == "3":
            view_publishing_results()
        elif choice == "4":
            find_and_fix_failures()
        elif choice == "5":
            verify_video_urls()
        elif choice == "6":
            export_to_csv()
        elif choice == "7":
            compare_schedule_vs_log()
        elif choice == "8":
            clear_old_logs()
        elif choice == "9":
            generate_report()
        elif choice == "10":
            print("Goodbye!")
            break
        else:
            print("Invalid option")

if __name__ == "__main__":
    main()
