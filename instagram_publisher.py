#!/usr/bin/env python3
"""
EUJOBHUB - INSTAGRAM-ONLY PUBLISHER
Publishes due reels to Instagram only. Never touches Facebook fields.
Tracks its own status in "ig_status" per reel, independent of Facebook.

Run modes:
  python instagram_publisher.py --run-once   -> CI / cron mode (no prompts)
"""

import os
import sys
import time
import json
import requests
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================

SCHEDULE_FILE = Path("reels_schedule.json")
LOG_FILE = Path("ig_publish_log.csv")

IG_USER_ID = "17841469954819666"
IG_TOKEN_FILE = Path("token.txt")

API_VERSION = "v26.0"

DEFAULT_IG_CAPTION = """Europe Jobs 2026 🇪🇺

Latest job vacancies across Europe.

Find European job opportunities:
https://eujobhub.com

#EuropeJobs #EUJobs #JobsInEurope #JobVacancies #EuropeJobs2026 #EUJobHub"""


# ============================================================
# TOKEN
# ============================================================

def load_ig_token() -> str:
    token = os.environ.get("IG_ACCESS_TOKEN")
    if token:
        return token.strip()

    if not IG_TOKEN_FILE.exists():
        print("ERROR: No IG_ACCESS_TOKEN env var and token.txt not found!")
        raise SystemExit(1)

    return IG_TOKEN_FILE.read_text(encoding="utf-8").strip()


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


def needs_instagram(reel: dict) -> bool:
    """True if this reel wants Instagram and hasn't succeeded there yet."""
    if "instagram" not in reel.get("platforms", []):
        return False
    ig_status = reel.get("ig_status", "pending")
    return ig_status in ("pending", "failed") and is_due(reel)


# ============================================================
# INSTAGRAM API
# ============================================================

def create_instagram_reel(ig_token: str, video_url: str, caption: str):
    url = f"https://graph.instagram.com/{API_VERSION}/{IG_USER_ID}/media"
    data = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": ig_token,
    }
    try:
        response = requests.post(url, data=data, timeout=120)
        if response.status_code != 200:
            print(f"  ❌ Instagram container failed: {response.status_code}")
            print(f"     {response.text}")
            return None
        container_id = response.json().get("id")
        if container_id:
            print(f"  ✓ Instagram container created: {container_id}")
            return container_id
        print("  ❌ No container ID returned")
        return None
    except Exception as e:
        print(f"  ❌ Instagram error: {e}")
        return None


def wait_instagram_processing(ig_token: str, container_id: str, max_wait_minutes: int = 10) -> bool:
    url = f"https://graph.instagram.com/{API_VERSION}/{container_id}"
    max_attempts = (max_wait_minutes * 60) // 10

    for attempt in range(max_attempts):
        try:
            response = requests.get(
                url,
                params={"fields": "status_code,status", "access_token": ig_token},
                timeout=60,
            )
            if response.status_code != 200:
                time.sleep(10)
                continue

            status_code = response.json().get("status_code")

            if status_code == "FINISHED":
                print(f"  ✓ Video processing finished (attempt {attempt + 1})")
                return True
            if status_code in ("ERROR", "EXPIRED"):
                print(f"  ❌ Instagram processing failed: {status_code}")
                return False

            time.sleep(10)
        except Exception as e:
            print(f"  ⚠ Check attempt {attempt + 1} failed: {e}")
            time.sleep(10)

    print("  ❌ Timeout waiting for Instagram processing")
    return False


def publish_instagram_reel(ig_token: str, container_id: str):
    url = f"https://graph.instagram.com/{API_VERSION}/{IG_USER_ID}/media_publish"
    try:
        response = requests.post(
            url,
            data={"creation_id": container_id, "access_token": ig_token},
            timeout=120,
        )
        if response.status_code == 200:
            media_id = response.json().get("id")
            print(f"  ✓ Published to Instagram (ID: {media_id})")
            return media_id
        print(f"  ❌ Instagram publish failed: {response.status_code}")
        print(f"     {response.text}")
        return None
    except Exception as e:
        print(f"  ❌ Instagram publish error: {e}")
        return None


# ============================================================
# LOGGING
# ============================================================

def log_result(reel: dict):
    is_new = not LOG_FILE.exists()
    import csv
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["video_number", "ig_status", "ig_container_id",
                              "publish_time", "published_at", "ig_error"])
        writer.writerow([
            reel["video_number"],
            reel.get("ig_status", ""),
            reel.get("ig_container_id", ""),
            reel.get("publish_time", ""),
            datetime.now().isoformat(),
            reel.get("ig_error", ""),
        ])


# ============================================================
# MAIN (single pass, for CI/cron)
# ============================================================

def run_once():
    print("=" * 70)
    print("EUJOBHUB - INSTAGRAM PUBLISHER (single pass / CI mode)")
    print("=" * 70)

    ig_token = load_ig_token()
    print("Instagram token loaded\n")

    schedule = load_schedule()
    due = [r for r in schedule if needs_instagram(r)]

    if not due:
        upcoming = sorted(
            (r for r in schedule
             if "instagram" in r.get("platforms", [])
             and r.get("ig_status", "pending") in ("pending", "failed")),
            key=lambda r: r["publish_time"],
        )
        if upcoming:
            print(f"No Instagram reel due yet. Next up: #{upcoming[0]['video_number']} "
                  f"at {upcoming[0]['publish_time']}")
        else:
            print("No Instagram reels left to publish - all done!")
        return

    print(f"{len(due)} reel(s) due for Instagram. Publishing...\n")

    for reel in due:
        print(f"\n📹 Video #{reel['video_number']}: {reel['r2_url']}")
        caption = reel.get("caption") or DEFAULT_IG_CAPTION

        container_id = create_instagram_reel(ig_token, reel["r2_url"], caption)
        success = False
        if container_id:
            reel["ig_container_id"] = container_id
            if wait_instagram_processing(ig_token, container_id):
                media_id = publish_instagram_reel(ig_token, container_id)
                if media_id:
                    success = True

        reel["ig_status"] = "published" if success else "failed"
        reel["ig_error"] = "" if success else "Instagram publish failed - see run logs"

        save_schedule(schedule)
        log_result(reel)
        print(f"  -> #{reel['video_number']} Instagram: {reel['ig_status']}")

    print("\nRun complete.")


if __name__ == "__main__":
    if "--run-once" in sys.argv:
        run_once()
    else:
        print("Usage: python instagram_publisher.py --run-once")
