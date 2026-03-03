"""
fetch_tiktok.py — Pulls video data from TikTok Research API

Setup:
  1. Apply for TikTok Research API access at https://developers.tiktok.com/products/research-api/
  2. Create an app and obtain Client Key and Client Secret
  3. Add credentials to tiktokAPI.env:
       TIKTOK_CLIENT_KEY=your_client_key_here
       TIKTOK_CLIENT_SECRET=your_client_secret_here

Auth: Client credentials OAuth2 (no user login required for Research API)

Signal captured:
  - video_count     : number of videos returned (up to 100)
  - total_views     : sum of view_count across top 100 videos
  - total_likes     : sum of like_count across top 100 videos
  - top_video_views : highest single-video view count
"""

import os
import requests
from datetime import date, timedelta
from dotenv import load_dotenv
from db import get_connection

load_dotenv("tiktokAPI.env")

SNAPSHOT_DATE       = date.today().isoformat()
TIKTOK_CLIENT_KEY   = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")

# Last 28 days
_today = date.today()
DATE_START = (_today - timedelta(days=28)).strftime("%Y%m%d")
DATE_END   = _today.strftime("%Y%m%d")


def get_tiktok_token() -> str:
    if not TIKTOK_CLIENT_KEY or not TIKTOK_CLIENT_SECRET:
        raise ValueError(
            "TikTok credentials not set. Create tiktokAPI.env with:\n"
            "  TIKTOK_CLIENT_KEY=your_client_key_here\n"
            "  TIKTOK_CLIENT_SECRET=your_client_secret_here\n"
            "Apply for access at: https://developers.tiktok.com/products/research-api/"
        )
    resp = requests.post(
        "https://open.tiktok.com/v2/oauth/token/",
        data={
            "client_key":    TIKTOK_CLIENT_KEY,
            "client_secret": TIKTOK_CLIENT_SECRET,
            "grant_type":    "client_credentials",
        },
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()["data"]["access_token"]


def fetch_tiktok_data(token: str, game_name: str) -> dict:
    """Query TikTok Research API for videos mentioning the game and aggregate stats."""
    resp = requests.post(
        "https://open.tiktok.com/research/video/query/",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        json={
            "query": {
                "and": [
                    {"operation": "IN", "field_name": "keyword", "field_values": [game_name]}
                ]
            },
            "start_date": DATE_START,
            "end_date":   DATE_END,
            "max_count":  100,
            "fields":     ["view_count", "like_count", "comment_count", "share_count", "id", "create_time"],
        },
        timeout=15
    )
    resp.raise_for_status()
    videos = resp.json().get("data", {}).get("videos", [])

    if not videos:
        return {
            "video_count":     0,
            "total_views":     0,
            "total_likes":     0,
            "top_video_views": 0,
            "query_used":      game_name,
        }

    views = [v.get("view_count", 0) or 0 for v in videos]
    likes = [v.get("like_count", 0) or 0 for v in videos]
    return {
        "video_count":     len(videos),
        "total_views":     sum(views),
        "total_likes":     sum(likes),
        "top_video_views": max(views),
        "query_used":      game_name,
    }


def save_tiktok_data(game_id: int, data: dict):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO tiktok_data (
                game_id, snapshot_date,
                video_count, total_views, total_likes,
                top_video_views, query_used, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            game_id, SNAPSHOT_DATE,
            data["video_count"],
            data["total_views"],
            data["total_likes"],
            data["top_video_views"],
            data["query_used"],
        ))


def run():
    print(f"\n🎵 Fetching TikTok data — snapshot date: {SNAPSHOT_DATE}\n")
    print(f"Searching videos from {DATE_START} to {DATE_END}\n")

    token = get_tiktok_token()

    with get_connection() as conn:
        games = conn.execute("SELECT id, name FROM games").fetchall()

    print(f"Found {len(games)} games to process\n")

    for game in games:
        print(f"→ {game['name']}")
        try:
            data = fetch_tiktok_data(token, game["name"])
            save_tiktok_data(game["id"], data)
            print(f"  ✅ videos={data['video_count']} | total_views={data['total_views']:,} | top={data['top_video_views']:,}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    print("\n✅ TikTok fetch complete.")


if __name__ == "__main__":
    run()
