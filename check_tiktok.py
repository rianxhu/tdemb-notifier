import os
import sys
import requests

TIKTOK_USERNAME = "tordadavideastmallbuy"
STATE_FILE = "last_video.txt"

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

APIFY_URL = f"https://api.apify.com/v2/acts/clockworks~tiktok-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"

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
        video_id = item.get("id") or item.get("webVideoUrl")
        video_url = item.get("webVideoUrl")
        title = item.get("text") or "Új TikTok videó"
        videos.append((video_id, video_url, title))

    # items jönnek: legfrissebb elöl -> fordítsuk időrendi (régi -> új) sorrendbe
    videos.reverse()
    return videos

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
    videos = get_recent_videos()
    if not videos:
        print("No videos found or fetch failed.")
        return

    last_id = load_last_id()

    if last_id is None:
        # Első futás: csak a legújabbat mentjük el baseline-ként, nem posztolunk
        newest_id = videos[-1][0]
        save_last_id(newest_id)
        print(f"Baseline set to {newest_id}")
        return

    # Keressük meg, hol tartunk a listában az utoljára látott videóhoz képest
    known_ids = [v[0] for v in videos]
    if str(last_id) in [str(i) for i in known_ids]:
        start_index = [str(i) for i in known_ids].index(str(last_id)) + 1
    else:
        # Az utoljára látott videó nincs benne a lekért listában (pl. túl sok
        # idő telt el) -> csak a legutolsót posztoljuk, hogy elkerüljük a
        # régi videók tömeges újraposztolását
        start_index = len(videos) - 1

    new_videos = videos[start_index:]

    if not new_videos:
        print("No new video.")
        return

    for video_id, video_url, title in new_videos:
        print(f"New video detected: {video_id}")
        post_to_discord(video_url, title)

    save_last_id(new_videos[-1][0])

if __name__ == "__main__":
    main()
