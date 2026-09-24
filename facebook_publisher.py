#!/usr/bin/env python3
"""
EUJOBHUB - FACEBOOK-ONLY PUBLISHER
Publishes due reels to Facebook only. Never touches Instagram fields.
Tracks its own status in "fb_status" per reel, independent of Instagram.

Run modes:
  python facebook_publisher.py --run-once   -> CI / cron mode (no prompts)
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================

SCHEDULE_FILE = Path("reels_schedule.json")
LOG_FILE = Path("fb_publish_log.csv")

FB_PAGE_ID = "1296275966904719"
FB_USER_TOKEN_FILE = Path("fb_user_token.txt")

API_VERSION = "v26.0"

DEFAULT_FB_CAPTION = ("Europe Jobs 2026 🇪🇺 | Latest Jobs & Vacancies Across Europe | "
                      "EUJobHub.com #EuropeJobs #JobsInEurope #EUJobs #JobVacancies #EUJobHub")


# ============================================================
# TOKEN
# ============================================================

def load_fb_token() -> str:
    token = os.environ.get("FB_ACCESS_TOKEN")
    if token:
        return token.strip()

    if not FB_USER_TOKEN_FILE.exists():
        print("ERROR: No FB_ACCESS_TOKEN env var and fb_user_token.txt not found!")
        raise SystemExit(1)

    return FB_USER_TOKEN_FILE.read_text(encoding="utf-8").strip()


# ============================================================
# SCHEDULE I/O
# ============================================================

def load_schedule() -> list:
    if not SCHEDULE_FILE.exists():
        print("ERROR: reels_schedule.json not found!")
        raise SystemExit(1)
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_schedule(schedule: list):
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(schedule, f, indent=2, ensure_ascii=False)
    print(f"Schedule saved to {SCHEDULE_FILE}")


def is_due(reel: dict) -> bool:
    try:
        publish_time = datetime.fromisoformat(reel["publish_time"])
    except Exception:
        return False
    return publish_time <= datetime.now()


def needs_facebook(reel: dict) -> bool:
    """True if this reel wants Facebook and hasn't succeeded there yet."""
    if "facebook" not in reel.get("platforms", []):
        return False
    fb_status = reel.get("fb_status", "pending")
    return fb_status in ("pending", "failed") and is_due(reel)


# ============================================================
# FACEBOOK API
# ============================================================

def get_facebook_page_token(fb_user_token: str):
    url = f"https://graph.facebook.com/{API_VERSION}/me/accounts"
    try:
        response = requests.get(
            url,
            params={"access_token": fb_user_token, "fields": "id,name,access_token"},
            timeout=60,
        )
        if response.status_code != 200:
            print(f"  ❌ Failed to get Facebook page token: {response.status_code}")
            print(f"     {response.text}")
            return None

        data = response.json().get("data", [])
        for page in data:
            if page.get("id") == FB_PAGE_ID:
                print("  ✓ Facebook page token obtained")
                return page.get("access_token")

        print(f"  ❌ Facebook page {FB_PAGE_ID} not found in /me/accounts "
              f"(token may lack pages_show_list, or Page wasn't selected during login)")
        return None
    except Exception as e:
        print(f"  ❌ Facebook token error: {e}")
        return None


def start_facebook_reel_upload(fb_page_token: str):
    url = f"https://graph.facebook.com/{API_VERSION}/{FB_PAGE_ID}/video_reels"
    try:
        response = requests.post(
            url,
            params={"upload_phase": "start", "access_token": fb_page_token},
            timeout=60,
        )
        if response.status_code != 200:
            print(f"  ❌ Facebook upload start failed: {response.status_code}")
            print(f"     {response.text}")
            return None

        data = response.json()
        video_id = data.get("video_id")
        upload_url = data.get("upload_url")
        if video_id:
            print(f"  ✓ Facebook upload started (video_id: {video_id})")
            return (video_id, upload_url)
        print("  ❌ No video_id from Facebook")
        return None
    except Exception as e:
        print(f"  ❌ Facebook upload start error: {e}")
        return None


def download_video_from_r2(r2_url: str, temp_path: Path) -> bool:
    try:
        response = requests.get(r2_url, timeout=300)
        if response.status_code == 200:
            with open(temp_path, "wb") as f:
                f.write(response.content)
            return True
        print(f"  ❌ R2 download failed: {response.status_code}")
        return False
    except Exception as e:
        print(f"  ❌ R2 download error: {e}")
        return False


def upload_video_to_facebook(fb_page_token: str, upload_url: str, video_path: Path) -> bool:
    try:
        file_size = video_path.stat().st_size
        headers = {
            "Authorization": f"OAuth {fb_page_token}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream",
        }
        with open(video_path, "rb") as video:
            response = requests.post(upload_url, headers=headers, data=video, timeout=300)

        if response.status_code in (200, 201):
            print("  ✓ Video uploaded to Facebook")
            return True
        print(f"  ❌ Facebook upload failed: {response.status_code}")
        print(f"     {response.text}")
        return False
    except Exception as e:
        print(f"  ❌ Facebook video upload error: {e}")
        return False


def publish_facebook_reel(fb_page_token: str, video_id: str, caption: str) -> bool:
    url = f"https://graph.facebook.com/{API_VERSION}/{FB_PAGE_ID}/video_reels"
    try:
        response = requests.post(
            url,
            params={
                "upload_phase": "finish",
                "video_id": video_id,
                "video_state": "PUBLISHED",
                "description": caption,
                "access_token": fb_page_token,
            },
            timeout=60,
        )
        if response.status_code == 200:
            print("  ✓ Published to Facebook")
            return True
        print(f"  ❌ Facebook publish failed: {response.status_code}")
        print(f"     {response.text}")
        return False
    except Exception as e:
        print(f"  ❌ Facebook publish error: {e}")
        return False


# ============================================================
# LOGGING
# ============================================================

def log_result(reel: dict):
    is_new = not LOG_FILE.exists()
    import csv
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["video_number", "fb_status", "fb_video_id",
                              "publish_time", "published_at", "fb_error"])
        writer.writerow([
            reel["video_number"],
            reel.get("fb_status", ""),
            reel.get("fb_video_id", ""),
            reel.get("publish_time", ""),
            datetime.now().isoformat(),
            reel.get("fb_error", ""),
        ])


# ============================================================
# MAIN (single pass, for CI/cron)
# ============================================================

def run_once():
    print("=" * 70)
    print("EUJOBHUB - FACEBOOK PUBLISHER (single pass / CI mode)")
    print("=" * 70)

    fb_token = load_fb_token()
    print("Facebook token loaded\n")

    schedule = load_schedule()
    due = [r for r in schedule if needs_facebook(r)]

    if not due:
        upcoming = sorted(
            (r for r in schedule
             if "facebook" in r.get("platforms", [])
             and r.get("fb_status", "pending") in ("pending", "failed")),
            key=lambda r: r["publish_time"],
        )
        if upcoming:
            print(f"No Facebook reel due yet. Next up: #{upcoming[0]['video_number']} "
                  f"at {upcoming[0]['publish_time']}")
        else:
            print("No Facebook reels left to publish - all done!")
        return

    print(f"{len(due)} reel(s) due for Facebook. Publishing...\n")

    for reel in due:
        print(f"\n📹 Video #{reel['video_number']}: {reel['r2_url']}")
        caption = reel.get("caption") or DEFAULT_FB_CAPTION

        success = False
        fb_page_token = get_facebook_page_token(fb_token)

        if fb_page_token:
            result = start_facebook_reel_upload(fb_page_token)
            if result:
                video_id, upload_url = result
                reel["fb_video_id"] = video_id
                temp_video = Path("temp_fb_video.mp4")

                if download_video_from_r2(reel["r2_url"], temp_video):
                    if upload_url:
                        if upload_video_to_facebook(fb_page_token, upload_url, temp_video):
                            if publish_facebook_reel(fb_page_token, video_id, caption):
                                success = True
                    else:
                        if publish_facebook_reel(fb_page_token, video_id, caption):
                            success = True

                    try:
                        temp_video.unlink()
                    except Exception:
                        pass

        reel["fb_status"] = "published" if success else "failed"
        reel["fb_error"] = "" if success else "Facebook publish failed - see run logs"

        save_schedule(schedule)
        log_result(reel)
        print(f"  -> #{reel['video_number']} Facebook: {reel['fb_status']}")

    print("\nRun complete.")


if __name__ == "__main__":
    if "--run-once" in sys.argv:
        run_once()
    else:
        print("Usage: python facebook_publisher.py --run-once")
