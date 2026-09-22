import requests
import time
import csv
import json
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional

# ============================================================
# EUJOBHUB - BULK REELS SCHEDULER
# Publish to Instagram + Facebook on a schedule
# ============================================================

@dataclass
class ReelSchedule:
    """Single reel to publish"""
    video_number: int
    r2_url: str
    title: str
    publish_time: datetime
    platforms: List[str]  # ['instagram', 'facebook'] or either
    caption: str = ""
    ig_container_id: Optional[str] = None
    fb_video_id: Optional[str] = None
    status: str = "pending"  # pending, processing, published, failed
    error: str = ""

# ============================================================
# CONFIG
# ============================================================

SCHEDULE_FILE = Path("reels_schedule.json")
LOG_FILE = Path("reels_publish_log.csv")

# Instagram
IG_USER_ID = "17841469954819666"
IG_TOKEN_FILE = Path("token.txt")

# Facebook
FB_PAGE_ID = "1296275966904719"
FB_USER_TOKEN_FILE = Path("fb_user_token.txt")

# R2
R2_PUBLIC_URL = "https://pub-b920483add26487c964812cdb7716dd3.r2.dev"

API_VERSION = "v26.0"

# Default captions
DEFAULT_IG_CAPTION = """Europe Jobs 2026 🇪🇺

Latest job vacancies across Europe.

Find European job opportunities:
https://eujobhub.com

#EuropeJobs #EUJobs #JobsInEurope #JobVacancies #EuropeJobs2026 #EUJobHub"""

DEFAULT_FB_CAPTION = """Europe Jobs 2026 🇪🇺 | Latest Jobs & Vacancies Across Europe | EUJobHub.com #EuropeJobs #JobsInEurope #EUJobs #JobVacancies #EUJobHub"""

# ============================================================
# LOAD TOKENS
# ============================================================

def load_tokens():
    """
    Load Instagram and Facebook tokens.

    Preferred: environment variables IG_ACCESS_TOKEN / FB_ACCESS_TOKEN
    (set these as GitHub Actions secrets - never commit token files to git).

    Fallback: local token.txt / fb_user_token.txt files, for running
    the script by hand on your own machine.
    """
    import os

    ig_token = os.environ.get("IG_ACCESS_TOKEN")
    fb_token = os.environ.get("FB_ACCESS_TOKEN")

    if ig_token and fb_token:
        return ig_token.strip(), fb_token.strip()

    if not IG_TOKEN_FILE.exists():
        print("ERROR: No IG_ACCESS_TOKEN env var and token.txt (Instagram) not found!")
        raise SystemExit

    if not FB_USER_TOKEN_FILE.exists():
        print("ERROR: No FB_ACCESS_TOKEN env var and fb_user_token.txt (Facebook) not found!")
        raise SystemExit

    ig_token = IG_TOKEN_FILE.read_text(encoding="utf-8").strip()
    fb_token = FB_USER_TOKEN_FILE.read_text(encoding="utf-8").strip()

    return ig_token, fb_token

# ============================================================
# CREATE SCHEDULE
# ============================================================

def create_schedule(num_videos: int, start_time: datetime, interval_hours: int, platforms: List[str]) -> List[ReelSchedule]:
    """
    Create a publishing schedule for multiple reels
    
    Args:
        num_videos: How many reels (e.g., 299)
        start_time: When to publish the first reel
        interval_hours: Hours between each reel
        platforms: ['instagram', 'facebook'] or either
    """
    schedule = []
    
    for i in range(1, num_videos + 1):
        publish_time = start_time + timedelta(hours=interval_hours * (i - 1))
        
        reel = ReelSchedule(
            video_number=i,
            r2_url=f"{R2_PUBLIC_URL}/{i}.mp4",
            title=f"Europe Jobs Video #{i}",
            publish_time=publish_time,
            platforms=platforms,
            caption=DEFAULT_IG_CAPTION
        )
        
        schedule.append(reel)
    
    return schedule

def save_schedule(schedule: List[ReelSchedule]):
    """Save schedule to JSON file"""
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            [asdict(r) for r in schedule],
            f,
            indent=2,
            default=str  # For datetime serialization
        )
    print(f"Schedule saved to {SCHEDULE_FILE}")

def load_schedule() -> List[ReelSchedule]:
    """Load schedule from JSON file"""
    if not SCHEDULE_FILE.exists():
        print("ERROR: reels_schedule.json not found!")
        print("Use create_new_schedule() first.")
        raise SystemExit
    
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    schedule = []
    for item in data:
        item['publish_time'] = datetime.fromisoformat(item['publish_time'])
        schedule.append(ReelSchedule(**item))
    
    return schedule

# ============================================================
# INSTAGRAM REEL PUBLISHING
# ============================================================

def create_instagram_reel(ig_token: str, video_url: str, caption: str) -> Optional[str]:
    """
    Create Instagram reel container
    Returns: container_id or None on failure
    """
    url = f"https://graph.instagram.com/{API_VERSION}/{IG_USER_ID}/media"
    
    data = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": ig_token
    }
    
    try:
        response = requests.post(url, data=data, timeout=120)
        
        if response.status_code != 200:
            print(f"  ❌ Instagram container failed: {response.status_code}")
            print(f"     {response.text}")
            return None
        
        result = response.json()
        container_id = result.get("id")
        
        if container_id:
            print(f"  ✓ Instagram container created: {container_id}")
            return container_id
        else:
            print("  ❌ No container ID returned")
            return None
            
    except Exception as e:
        print(f"  ❌ Instagram error: {e}")
        return None

def wait_instagram_processing(ig_token: str, container_id: str, max_wait_minutes: int = 10) -> bool:
    """Wait for Instagram to finish processing video"""
    url = f"https://graph.instagram.com/{API_VERSION}/{container_id}"
    
    max_attempts = (max_wait_minutes * 60) // 10  # Check every 10 seconds
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(
                url,
                params={
                    "fields": "status_code,status",
                    "access_token": ig_token
                },
                timeout=60
            )
            
            if response.status_code != 200:
                time.sleep(10)
                continue
            
            data = response.json()
            status_code = data.get("status_code")
            
            if status_code == "FINISHED":
                print(f"  ✓ Video processing finished (attempt {attempt + 1})")
                return True
            
            if status_code in ["ERROR", "EXPIRED"]:
                print(f"  ❌ Instagram processing failed: {status_code}")
                return False
            
            # Still processing - wait and retry
            time.sleep(10)
            
        except Exception as e:
            print(f"  ⚠ Check attempt {attempt + 1} failed: {e}")
            time.sleep(10)
    
    print("  ❌ Timeout waiting for Instagram processing")
    return False

def publish_instagram_reel(ig_token: str, container_id: str) -> bool:
    """Publish Instagram reel after it's processed"""
    url = f"https://graph.instagram.com/{API_VERSION}/{IG_USER_ID}/media_publish"
    
    try:
        response = requests.post(
            url,
            data={
                "creation_id": container_id,
                "access_token": ig_token
            },
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            media_id = result.get("id")
            print(f"  ✓ Published to Instagram (ID: {media_id})")
            return True
        else:
            print(f"  ❌ Instagram publish failed: {response.status_code}")
            print(f"     {response.text}")
            return False
            
    except Exception as e:
        print(f"  ❌ Instagram publish error: {e}")
        return False

# ============================================================
# FACEBOOK REEL PUBLISHING
# ============================================================

def get_facebook_page_token(fb_user_token: str) -> Optional[str]:
    """Get Facebook page access token from user token"""
    url = f"https://graph.facebook.com/{API_VERSION}/me/accounts"
    
    try:
        response = requests.get(
            url,
            params={
                "access_token": fb_user_token,
                "fields": "id,name,access_token"
            },
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"  ❌ Failed to get Facebook page token: {response.status_code}")
            return None
        
        data = response.json().get("data", [])
        
        for page in data:
            if page.get("id") == FB_PAGE_ID:
                token = page.get("access_token")
                print(f"  ✓ Facebook page token obtained")
                return token
        
        print(f"  ❌ Facebook page {FB_PAGE_ID} not found")
        return None
        
    except Exception as e:
        print(f"  ❌ Facebook token error: {e}")
        return None

def start_facebook_reel_upload(fb_page_token: str) -> Optional[tuple]:
    """
    Start Facebook reel upload
    Returns: (video_id, upload_url) or None on failure
    """
    url = f"https://graph.facebook.com/{API_VERSION}/{FB_PAGE_ID}/video_reels"
    
    try:
        response = requests.post(
            url,
            params={
                "upload_phase": "start",
                "access_token": fb_page_token
            },
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"  ❌ Facebook upload start failed: {response.status_code}")
            return None
        
        data = response.json()
        video_id = data.get("video_id")
        upload_url = data.get("upload_url")
        
        if video_id:
            print(f"  ✓ Facebook upload started (video_id: {video_id})")
            return (video_id, upload_url)
        else:
            print("  ❌ No video_id from Facebook")
            return None
            
    except Exception as e:
        print(f"  ❌ Facebook upload start error: {e}")
        return None

def publish_facebook_reel(fb_page_token: str, video_id: str, caption: str) -> bool:
    """Publish Facebook reel after upload"""
    url = f"https://graph.facebook.com/{API_VERSION}/{FB_PAGE_ID}/video_reels"
    
    try:
        response = requests.post(
            url,
            params={
                "upload_phase": "finish",
                "video_id": video_id,
                "video_state": "PUBLISHED",
                "description": caption,
                "access_token": fb_page_token
            },
            timeout=60
        )
        
        if response.status_code == 200:
            print(f"  ✓ Published to Facebook")
            return True
        else:
            print(f"  ❌ Facebook publish failed: {response.status_code}")
            print(f"     {response.text}")
            return False
            
    except Exception as e:
        print(f"  ❌ Facebook publish error: {e}")
        return False

# ============================================================
# DOWNLOAD AND UPLOAD VIDEO (for Facebook direct upload)
# ============================================================

def download_video_from_r2(r2_url: str, temp_path: Path) -> bool:
    """Download video from R2 (needed for Facebook upload)"""
    try:
        response = requests.get(r2_url, timeout=300)
        
        if response.status_code == 200:
            with open(temp_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            print(f"  ❌ R2 download failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ R2 download error: {e}")
        return False

def upload_video_to_facebook(fb_page_token: str, upload_url: str, video_path: Path) -> bool:
    """Upload video file to Facebook"""
    try:
        file_size = video_path.stat().st_size
        
        headers = {
            "Authorization": f"OAuth {fb_page_token}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream"
        }
        
        with open(video_path, "rb") as video:
            response = requests.post(
                upload_url,
                headers=headers,
                data=video,
                timeout=300
            )
        
        if response.status_code in [200, 201]:
            print(f"  ✓ Video uploaded to Facebook")
            return True
        else:
            print(f"  ❌ Facebook upload failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Facebook video upload error: {e}")
        return False

# ============================================================
# MAIN PUBLISHING FUNCTION
# ============================================================

def publish_reel(reel: ReelSchedule, ig_token: str, fb_user_token: str) -> ReelSchedule:
    """Publish a single reel to specified platforms"""
    
    print(f"\n📹 Video #{reel.video_number}: {reel.r2_url}")
    
    # ============================================================
    # INSTAGRAM
    # ============================================================
    
    ig_success = False
    if "instagram" in reel.platforms:
        print("  📸 Publishing to Instagram...")
        
        container_id = create_instagram_reel(ig_token, reel.r2_url, reel.caption)
        
        if container_id:
            reel.ig_container_id = container_id
            
            if wait_instagram_processing(ig_token, container_id):
                if publish_instagram_reel(ig_token, container_id):
                    ig_success = True
    
    # ============================================================
    # FACEBOOK
    # ============================================================
    
    fb_success = False
    if "facebook" in reel.platforms:
        print("  📘 Publishing to Facebook...")
        
        fb_page_token = get_facebook_page_token(fb_user_token)
        
        if fb_page_token:
            result = start_facebook_reel_upload(fb_page_token)
            
            if result:
                video_id, upload_url = result
                reel.fb_video_id = video_id
                
                # Download video from R2 and upload to Facebook
                temp_video = Path("temp_fb_video.mp4")
                
                if download_video_from_r2(reel.r2_url, temp_video):
                    if upload_url:
                        if upload_video_to_facebook(fb_page_token, upload_url, temp_video):
                            if publish_facebook_reel(fb_page_token, video_id, reel.caption):
                                fb_success = True
                    else:
                        # No upload URL returned, but video_id exists
                        if publish_facebook_reel(fb_page_token, video_id, reel.caption):
                            fb_success = True
                    
                    # Clean up temp file
                    try:
                        temp_video.unlink()
                    except:
                        pass
    
    # ============================================================
    # UPDATE STATUS
    # ============================================================
    
    platforms_success = []
    if ig_success:
        platforms_success.append("instagram")
    if fb_success:
        platforms_success.append("facebook")
    
    if platforms_success:
        reel.status = "published"
    else:
        reel.status = "failed"
        reel.error = "Failed to publish to any platform"
    
    return reel

# ============================================================
# SCHEDULER LOOP
# ============================================================

def run_scheduler():
    """Main scheduler loop - runs continuously"""
    
    print("=" * 70)
    print("EUJOBHUB - BULK REELS SCHEDULER")
    print("=" * 70)
    
    # Load tokens
    try:
        ig_token, fb_user_token = load_tokens()
        print("✓ Tokens loaded successfully\n")
    except:
        return
    
    # Load schedule
    schedule = load_schedule()
    print(f"Loaded {len(schedule)} reels\n")
    
    # Filter to reels that need publishing
    pending = [r for r in schedule if r.status == "pending"]
    print(f"Reels to publish: {len(pending)}\n")
    
    if not pending:
        print("No reels to publish!")
        return
    
    # Publish each reel at scheduled time
    for reel in pending:
        # Wait until scheduled time
        wait_seconds = (reel.publish_time - datetime.now()).total_seconds()
        
        if wait_seconds > 0:
            wait_hours = wait_seconds / 3600
            print(f"⏰ Waiting {wait_hours:.1f} hours until {reel.publish_time.strftime('%Y-%m-%d %H:%M')}")
            time.sleep(wait_seconds)
        
        # Publish
        published = publish_reel(reel, ig_token, fb_user_token)
        
        # Save updated schedule
        schedule[schedule.index(reel)] = published
        save_schedule(schedule)
        
        # Log result
        log_reel(published)
    
    print("\n" + "=" * 70)
    print("ALL REELS PUBLISHED!")
    print("=" * 70)

def run_scheduler_once():
    """
    Non-interactive, single-pass version of the scheduler for CI use
    (GitHub Actions cron, cron jobs, etc).

    - Never calls input()
    - Never sleeps for hours - it checks once whether any reel is
      currently due, publishes just that reel (or reels, if more than
      one is overdue), saves the schedule, and exits.
    - Trigger it repeatedly on a schedule (e.g. every 30-60 min) via
      GitHub Actions `cron:` so it publishes each reel close to its
      publish_time without needing a process that runs for days.
    """
    print("=" * 70)
    print("EUJOBHUB - BULK REELS SCHEDULER (single pass / CI mode)")
    print("=" * 70)

    try:
        ig_token, fb_user_token = load_tokens()
        print("Tokens loaded successfully\n")
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR loading tokens: {e}")
        raise SystemExit(1)

    schedule = load_schedule()
    now = datetime.now()

    due = [r for r in schedule if r.status == "pending" and r.publish_time <= now]

    if not due:
        upcoming = sorted(
            (r for r in schedule if r.status == "pending"),
            key=lambda r: r.publish_time,
        )
        if upcoming:
            print(f"No reel due yet. Next up: #{upcoming[0].video_number} "
                  f"at {upcoming[0].publish_time.strftime('%Y-%m-%d %H:%M')}")
        else:
            print("No pending reels left - all done!")
        return

    print(f"{len(due)} reel(s) due now. Publishing...\n")

    for reel in due:
        published = publish_reel(reel, ig_token, fb_user_token)
        schedule[schedule.index(reel)] = published
        save_schedule(schedule)
        log_reel(published)
        print(f"  -> #{published.video_number}: {published.status}"
              + (f" ({published.error})" if published.error else ""))

    print("\nRun complete.")


# ============================================================
# LOGGING
# ============================================================

def log_reel(reel: ReelSchedule):
    """Log reel publish result"""
    
    # Create log file if it doesn't exist
    if not LOG_FILE.exists():
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
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
    
    # Append result
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            reel.video_number,
            reel.status,
            ",".join(reel.platforms),
            reel.ig_container_id or "",
            reel.fb_video_id or "",
            reel.publish_time.isoformat(),
            datetime.now().isoformat(),
            reel.error
        ])

# ============================================================
# CLI INTERFACE
# ============================================================

def print_menu():
    print("\n" + "=" * 70)
    print("EUJOBHUB - REELS SCHEDULER MENU")
    print("=" * 70)
    print("1. Create new schedule (set number of videos, timing, platforms)")
    print("2. View current schedule")
    print("3. Start scheduler (publish on schedule)")
    print("4. Publish one reel now (for testing)")
    print("5. View publishing log")
    print("6. Exit")
    print("=" * 70)

def main():
    while True:
        print_menu()
        choice = input("\nSelect option (1-6): ").strip()
        
        if choice == "1":
            print("\n--- CREATE NEW SCHEDULE ---")
            try:
                num_videos = int(input("How many videos? (e.g., 299): "))
                interval = int(input("Hours between each reel? (e.g., 3): "))
                
                start_date = input("Start date (YYYY-MM-DD): ")
                start_time = input("Start time (HH:MM, 24-hour): ")
                
                start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
                
                platforms_input = input("Platforms (instagram,facebook): ").lower().split(",")
                platforms = [p.strip() for p in platforms_input]
                
                schedule = create_schedule(num_videos, start_datetime, interval, platforms)
                save_schedule(schedule)
                print(f"\n✓ Schedule created for {num_videos} reels starting {start_datetime}")
                
            except Exception as e:
                print(f"ERROR: {e}")
        
        elif choice == "2":
            print("\n--- CURRENT SCHEDULE ---")
            try:
                schedule = load_schedule()
                
                pending = sum(1 for r in schedule if r.status == "pending")
                published = sum(1 for r in schedule if r.status == "published")
                failed = sum(1 for r in schedule if r.status == "failed")
                
                print(f"\nTotal: {len(schedule)}")
                print(f"Pending: {pending}")
                print(f"Published: {published}")
                print(f"Failed: {failed}")
                
                print("\nNext 10 pending reels:")
                next_pending = [r for r in schedule if r.status == "pending"][:10]
                
                for reel in next_pending:
                    print(f"  #{reel.video_number}: {reel.publish_time.strftime('%Y-%m-%d %H:%M')} → {','.join(reel.platforms)}")
                
            except Exception as e:
                print(f"ERROR: {e}")
        
        elif choice == "3":
            print("\n--- START SCHEDULER ---")
            try:
                run_scheduler()
            except KeyboardInterrupt:
                print("\n\nScheduler stopped by user.")
            except Exception as e:
                print(f"ERROR: {e}")
        
        elif choice == "4":
            print("\n--- PUBLISH ONE REEL NOW ---")
            try:
                ig_token, fb_user_token = load_tokens()
                
                video_num = int(input("Video number (e.g., 1): "))
                platforms_input = input("Platforms (instagram,facebook): ").lower().split(",")
                platforms = [p.strip() for p in platforms_input]
                
                reel = ReelSchedule(
                    video_number=video_num,
                    r2_url=f"{R2_PUBLIC_URL}/{video_num}.mp4",
                    title=f"Europe Jobs Video #{video_num}",
                    publish_time=datetime.now(),
                    platforms=platforms,
                    caption=DEFAULT_IG_CAPTION
                )
                
                published = publish_reel(reel, ig_token, fb_user_token)
                log_reel(published)
                
                print(f"\n✓ Status: {published.status}")
                if published.error:
                    print(f"  Error: {published.error}")
                
            except Exception as e:
                print(f"ERROR: {e}")
        
        elif choice == "5":
            print("\n--- PUBLISHING LOG ---")
            try:
                if LOG_FILE.exists():
                    with open(LOG_FILE, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    
                    print(f"\nTotal published: {len(lines) - 1}")
                    print("\nRecent 10:")
                    for line in lines[-11:-1]:
                        print(f"  {line.strip()}")
                else:
                    print("No log file yet")
                
            except Exception as e:
                print(f"ERROR: {e}")
        
        elif choice == "6":
            print("Goodbye!")
            break
        
        else:
            print("Invalid option")

if __name__ == "__main__":
    import sys
    if "--run-once" in sys.argv:
        run_scheduler_once()
    else:
        main()
