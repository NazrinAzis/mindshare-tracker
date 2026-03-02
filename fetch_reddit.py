"""
fetch_reddit.py — Pulls post activity from Reddit's public search API

No API key required. Uses Reddit's public JSON API with a User-Agent header.
Rate limit: ~60 requests/minute unauthenticated.

Signal captured:
  - post_count      : number of posts mentioning the game in the last week
  - total_score     : sum of upvote scores (measures community engagement depth)
  - top_post_score  : score of the most upvoted post (viral content indicator)
"""

import time
import requests
from datetime import date
from db import get_connection

SNAPSHOT_DATE = date.today().isoformat()

HEADERS = {
    "User-Agent": "mindshare-tracker/1.0 (gaming market intelligence tool)"
}

SEARCH_URL = "https://www.reddit.com/search.json"


def fetch_reddit_data(game_name: str) -> dict | None:
    """Search Reddit for posts mentioning the game in the last week."""
    try:
        response = requests.get(
            SEARCH_URL,
            params={
                "q":      game_name,
                "sort":   "top",
                "t":      "week",
                "limit":  100,
                "type":   "link",
            },
            headers=HEADERS,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        posts = data.get("data", {}).get("children", [])
        if not posts:
            return {"post_count": 0, "total_score": 0, "top_post_score": 0, "top_post_title": None}

        scores = [p["data"].get("score", 0) for p in posts]
        top_post = max(posts, key=lambda p: p["data"].get("score", 0))

        return {
            "post_count":     len(posts),
            "total_score":    sum(scores),
            "top_post_score": top_post["data"].get("score", 0),
            "top_post_title": top_post["data"].get("title", "")[:200],
        }

    except Exception as e:
        print(f"  ❌ Error fetching Reddit data for '{game_name}': {e}")
        return None


def save_reddit_data(game_id: int, data: dict):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO reddit_data (
                game_id, snapshot_date,
                post_count, total_score, top_post_score, top_post_title, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            game_id, SNAPSHOT_DATE,
            data["post_count"],
            data["total_score"],
            data["top_post_score"],
            data["top_post_title"],
        ))


def run():
    print(f"\n🟠 Fetching Reddit data — snapshot date: {SNAPSHOT_DATE}\n")

    with get_connection() as conn:
        games = conn.execute("SELECT id, name FROM games").fetchall()

    print(f"Found {len(games)} games to process\n")

    for game in games:
        print(f"→ {game['name']}")
        data = fetch_reddit_data(game["name"])
        if data:
            save_reddit_data(game["id"], data)
            print(f"  ✅ posts={data['post_count']} | total_score={data['total_score']:,} | top={data['top_post_score']:,}")
        time.sleep(1.0)  # Respect rate limit

    print("\n✅ Reddit fetch complete.")


if __name__ == "__main__":
    run()
