import os
import sys
import requests

TIKTOK_USERNAME = "tordadavideastmallbuy"
STATE_FILE = "last_video.txt"

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

APIFY_URL = f"https://api.apify.com/v2/acts/clockworks~tiktok-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"

def get_latest_video():
    payload = {
        "profiles": [TIKTOK_USERNAME],
        "resultsPerPage": 3,
        "profileScrapeSections": ["videos"],
        "profileSorting": "latest",
        "excludePinnedPosts": True,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
    }
    resp = requests.post(APIFY_URL, json=payload, timeout=120)
    resp.raise_for_status()
    items = resp.json()

    if not items:
        return None

    latest = items[0]
    video_id = latest.get("id") or latest.get("webVideoUrl")
    video_url = latest.get("webVideoUrl")
    title = latest.get("text") or "Új TikTok videó"
    return video_id, video_url, title

def load_last_id():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, "r") as f:
        return f.read().strip() or None

def save_last_id(video_id):
    with open(STATE_FILE, "w") as f:
        f.write(str(video_id))

def post_to_discord(video_url, title):
    if not WEBHOOK_URL:
        print("Missing DISCORD_WEBHOOK_URL secret.")
        sys.exit(1)
    payload = {"content": f"📹 Új TikTok videó!\n**{title}**\n{video_url}"}
    resp = requests.post(WEBHOOK_URL, json=payload, timeout=15)
    resp.raise_for_status()

def main():
    result = get_latest_video()
    if not result:
        print("No videos found or fetch failed.")
        return

    video_id, video_url, title = result
    last_id = load_last_id()

    if last_id is None:
        save_last_id(video_id)
        print(f"Baseline set to {video_id}")
        return

    if str(video_id) != str(last_id):
        print(f"New video detected: {video_id}")
        post_to_discord(video_url, title)
        save_last_id(video_id)
    else:
        print("No new video.")

if __name__ == "__main__":
    main()
