#!/usr/bin/env python3
"""
EUJOBHUB - QUICK SCHEDULER TEST
Verify all tokens, credentials, and APIs are working
"""

import requests
from pathlib import Path
import sys

print("=" * 70)
print("EUJOBHUB - SCHEDULER SETUP TEST")
print("=" * 70)
print()

# ============================================================
# 1. CHECK FILES
# ============================================================

print("1️⃣  CHECKING FILES...")
print("-" * 70)

files_ok = True

# Instagram token
if Path("token.txt").exists():
    print("✓ token.txt found")
else:
    print("✗ token.txt NOT FOUND - need Instagram access token")
    files_ok = False

# Facebook user token
if Path("fb_user_token.txt").exists():
    print("✓ fb_user_token.txt found")
else:
    print("✗ fb_user_token.txt NOT FOUND - need Facebook user token")
    files_ok = False

# Scheduler script
if Path("bulk_reels_scheduler.py").exists():
    print("✓ bulk_reels_scheduler.py found")
else:
    print("✗ bulk_reels_scheduler.py NOT FOUND")
    files_ok = False

if not files_ok:
    print("\n⚠️  Missing required files. Cannot continue.\n")
    sys.exit(1)

print()

# ============================================================
# 2. VERIFY INSTAGRAM TOKEN
# ============================================================

print("2️⃣  TESTING INSTAGRAM TOKEN...")
print("-" * 70)

ig_token = Path("token.txt").read_text(encoding="utf-8").strip()

if not ig_token:
    print("✗ Instagram token is empty\n")
    sys.exit(1)

print(f"Token length: {len(ig_token)} chars")

try:
    response = requests.get(
        "https://graph.instagram.com/v26.0/me",
        params={"access_token": ig_token},
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        user_id = data.get("id")
        username = data.get("username")
        print(f"✓ Instagram token is VALID")
        print(f"  User ID: {user_id}")
        print(f"  Username: {username}")
    else:
        print(f"✗ Instagram token INVALID (HTTP {response.status_code})")
        print(f"  {response.text}")
        sys.exit(1)

except Exception as e:
    print(f"✗ Cannot reach Instagram API: {e}")
    sys.exit(1)

print()

# ============================================================
# 3. VERIFY FACEBOOK TOKEN & PAGE
# ============================================================

print("3️⃣  TESTING FACEBOOK TOKEN...")
print("-" * 70)

fb_token = Path("fb_user_token.txt").read_text(encoding="utf-8").strip()

if not fb_token:
    print("✗ Facebook token is empty\n")
    sys.exit(1)

print(f"Token length: {len(fb_token)} chars")

try:
    # Test user token
    response = requests.get(
        "https://graph.facebook.com/v26.0/me",
        params={"access_token": fb_token},
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        user_id = data.get("id")
        name = data.get("name")
        print(f"✓ Facebook user token is VALID")
        print(f"  User ID: {user_id}")
        print(f"  Name: {name}")
    else:
        print(f"✗ Facebook token INVALID (HTTP {response.status_code})")
        print(f"  {response.text}")
        sys.exit(1)

except Exception as e:
    print(f"✗ Cannot reach Facebook API: {e}")
    sys.exit(1)

# Test page access
print("\nChecking page access...")

PAGE_ID = "1296275966904719"

try:
    response = requests.get(
        f"https://graph.facebook.com/v26.0/{PAGE_ID}",
        params={
            "fields": "id,name,access_token",
            "access_token": fb_token
        },
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        page_name = data.get("name")
        has_page_token = "access_token" in data
        
        print(f"✓ Can access Facebook page: {page_name}")
        if has_page_token:
            print(f"✓ Can get page access token")
        else:
            print(f"⚠️  No page access token (need page admin permissions)")
    else:
        print(f"✗ Cannot access page (HTTP {response.status_code})")
        print(f"  {response.text}")
        sys.exit(1)

except Exception as e:
    print(f"✗ Cannot check page: {e}")
    sys.exit(1)

print()

# ============================================================
# 4. VERIFY R2 BUCKET ACCESS
# ============================================================

print("4️⃣  TESTING R2 BUCKET...")
print("-" * 70)

try:
    # Try to access a video from R2
    video_url = "https://pub-b920483add26487c964812cdb7716dd3.r2.dev/1.mp4"
    
    response = requests.head(video_url, timeout=10)
    
    if response.status_code == 200:
        print(f"✓ R2 bucket is ACCESSIBLE")
        print(f"  URL: {video_url}")
        content_length = response.headers.get("content-length", "unknown")
        if content_length != "unknown":
            size_mb = int(content_length) / (1024 * 1024)
            print(f"  Video size: {size_mb:.1f} MB")
    else:
        print(f"⚠️  R2 URL returned {response.status_code}")
        print(f"  Make sure videos are uploaded to R2 first")

except Exception as e:
    print(f"⚠️  Cannot reach R2: {e}")
    print(f"  (This is OK if videos aren't uploaded yet)")

print()

# ============================================================
# 5. VERIFY REQUESTS LIBRARY
# ============================================================

print("5️⃣  CHECKING DEPENDENCIES...")
print("-" * 70)

try:
    import requests
    print(f"✓ requests library installed (v{requests.__version__})")
except ImportError:
    print("✗ requests library NOT installed")
    print("  Run: pip install requests --break-system-packages")
    sys.exit(1)

print()

# ============================================================
# 6. READY TO USE
# ============================================================

print("=" * 70)
print("✓ ALL CHECKS PASSED!")
print("=" * 70)
print()
print("Next steps:")
print("1. Create schedule:  python bulk_reels_scheduler.py")
print("2. Select option 1 (Create new schedule)")
print("3. Answer the questions")
print("4. Select option 3 (Start scheduler)")
print()
print("Your schedule will be saved in: reels_schedule.json")
print("Publishing log will be in: reels_publish_log.csv")
print()
