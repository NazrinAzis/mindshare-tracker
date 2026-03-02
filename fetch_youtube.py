"""
fetch_youtube.py — Pulls video data from YouTube Data API v3

Setup:
  1. Go to https://console.cloud.google.com
  2. Create a project → Enable "YouTube Data API v3"
  3. Create credentials → API Key
  4. Set your key in .env or pass via environment variable YOUTUBE_API_KEY

Install: pip install google-api-python-client python-dotenv

Free tier: 10,000 units/day. A search.list call costs 100 units.
With 20 games, that's 2,000 units — well within the free tier.
"""

import os
from datetime import date, timedelta
from googleapiclient.discovery import build
from dotenv import load_dotenv
from db import get_connection

load_dotenv("youtubeAPI.env")

SNAPSHOT_DATE = date.today().isoformat()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Search for videos published in the last 28 days to measure recent buzz
PUBLISHED_AFTER = (date.today() - timedelta(days=28)).strftime("%Y-%m-%dT00:00:00Z")


def get_youtube_client():
    if not YOUTUBE_API_KEY:
        raise ValueError(
            "YOUTUBE_API_KEY not set. Add it to your .env file:\n"
            "  YOUTUBE_API_KEY=your_key_here"
        )
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def fetch_youtube_data(youtube, game_name: str) -> dict | None:
    """Search YouTube for a game and return stats on the top result."""
    query = f"{game_name} gameplay 2025"

    try:
        # Search for videos
        search_response = youtube.search().list(
            q=query,
            part="id,snippet",
            type="video",
            order="relevance",
            publishedAfter=PUBLISHED_AFTER,
            maxResults=5
        ).execute()

        total_results = search_response.get("pageInfo", {}).get("totalResults", 0)
        items = search_response.get("items", [])

        if not items:
            return {"total_results": total_results, "top_video_views": 0,
                    "top_video_likes": 0, "top_video_id": None, "query_used": query}

        # Get stats for the top video
        top_video_id = items[0]["id"]["videoId"]
        stats_response = youtube.videos().list(
            part="statistics",
            id=top_video_id
        ).execute()

        stats = stats_response["items"][0]["statistics"] if stats_response["items"] else {}

        return {
            "total_results": total_results,
            "top_video_views": int(stats.get("viewCount", 0)),
            "top_video_likes": int(stats.get("likeCount", 0)),
            "top_video_id": top_video_id,
            "query_used": query
        }

    except Exception as e:
        print(f"  ❌ Error fetching YouTube data for '{game_name}': {e}")
        return None


def save_youtube_data(game_id: int, data: dict):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO youtube_data (
                game_id, snapshot_date,
                total_results, top_video_views, top_video_likes,
                top_video_id, query_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            game_id,
            SNAPSHOT_DATE,
            data["total_results"],
            data["top_video_views"],
            data["top_video_likes"],
            data["top_video_id"],
            data["query_used"]
        ))


def run():
    print(f"\n▶️  Fetching YouTube data — snapshot date: {SNAPSHOT_DATE}\n")
    print(f"Searching for videos published after: {PUBLISHED_AFTER}\n")

    youtube = get_youtube_client()

    with get_connection() as conn:
        games = conn.execute("SELECT id, name FROM games").fetchall()

    print(f"Found {len(games)} games to process\n")

    for game in games:
        print(f"→ {game['name']}")
        data = fetch_youtube_data(youtube, game["name"])
        if data:
            save_youtube_data(game["id"], data)
            print(f"  ✅ total_results={data['total_results']:,} | top_views={data['top_video_views']:,}")

    print("\n✅ YouTube fetch complete.")


if __name__ == "__main__":
    run()
