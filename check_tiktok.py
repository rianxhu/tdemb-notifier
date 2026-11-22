import os
import sys
import json
import time
from datetime import datetime
import requests

TIKTOK_USERNAME = "tordadavideastmallbuy"
STATE_FILE = "state.json"
MAX_SEEN = 200

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
ROLE_ID = os.environ.get("DISCORD_ROLE_ID")

APIFY_URL = f"https://api.apify.com/v2/acts/clockworks~tiktok-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"

def get_create_time(item):
    t = item.get("createTime")
    if isinstance(t, (int, float)) and t > 0:
        return int(t)
    iso = item.get("createTimeISO")
    if iso:
        try:
            return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())
        except ValueError:
            pass
    return 0

def get_recent_videos():
    payload = {
        "profiles": [TIKTOK_USERNAME],
        "resultsPerPage": 5,
        "profileScrapeSections": ["videos"],
        "profileSorting": "latest",
        "excludePinnedPosts": True,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
    }
    resp = requests.post(APIFY_URL, json=payload, timeout=120)
    resp.raise_for_status()
    items = resp.json()

    videos = []
    for item in items:
        video_id = str(item.get("id") or "")
        video_url = item.get("webVideoUrl")
        if not video_id or not video_url:
            continue
        videos.append({
            "id": video_id,
            "url": video_url,
            "title": item.get("text") or "Új TikTok videó",
            "time": get_create_time(item),
        })

    # Feltöltési idő szerint rendezzük (régi -> új), nem bízunk a lista sorrendjében
    videos.sort(key=lambda v: v["time"])
    return videos

def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        return {"seen": list(data.get("seen", [])), "last_time": int(data.get("last_time", 0))}
    except (ValueError, OSError):
        return None

def save_state(state):
    state["seen"] = state["seen"][-MAX_SEEN:]
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def post_to_discord(video_url, title):
    if not WEBHOOK_URL:
        print("Missing DISCORD_WEBHOOK_URL secret.")
        sys.exit(1)
    embed_url = video_url.replace("tiktok.com", "tnktok.com")
    mention = f"<@&{ROLE_ID}> " if ROLE_ID else ""
    payload = {
        "content": f"{mention}📹 Új TikTok videó!\n**{title}**\n{embed_url}",
        "allowed_mentions": {"roles": [ROLE_ID] if ROLE_ID else []},
    }
    # Átmeneti Discord-hibánál (429, 5xx) vár és újrapróbálja
    for attempt in range(4):
        resp = requests.post(WEBHOOK_URL, json=payload, timeout=15)
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = 10 * (attempt + 1)
            print(f"Discord hiba ({resp.status_code}), újrapróbálás {wait} mp múlva...")
            time.sleep(wait)
            continue
        break
    resp.raise_for_status()

def main():
    videos = get_recent_videos()
    if not videos:
        print("No videos found or fetch failed.")
        return

    state = load_state()

    if state is None:
        # Első futás: minden jelenlegi videót "látottnak" jelölünk, nem posztolunk
        state = {"seen": [v["id"] for v in videos], "last_time": max(v["time"] for v in videos)}
        save_state(state)
        print(f"Baseline set ({len(videos)} videos marked as seen).")
        return

    seen = set(state["seen"])

    # Csak az kerül ki, amit még sosem láttunk ÉS frissebb az eddigi legfrissebbnél
    new_videos = [v for v in videos if v["id"] not in seen and v["time"] > state["last_time"]]

    # A nem látott, de régebbi videókat (pl. becsúszott régi/kitűzött) csendben látottnak jelöljük
    for v in videos:
        if v["id"] not in seen and v not in new_videos:
            state["seen"].append(v["id"])
            seen.add(v["id"])

    if not new_videos:
        save_state(state)
        print("No new video.")
        return

    for v in new_videos:
        print(f"New video detected: {v['id']}")
        post_to_discord(v["url"], v["title"])
        state["seen"].append(v["id"])
        seen.add(v["id"])
        state["last_time"] = max(state["last_time"], v["time"])
        save_state(state)

if __name__ == "__main__":
    main()
