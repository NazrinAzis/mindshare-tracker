"""
fetch_twitch.py — Pulls live stream data from Twitch Helix API

Setup:
  1. Go to https://dev.twitch.tv/console
  2. Register a new application (any name, redirect URL: http://localhost)
  3. Copy Client ID and Client Secret
  4. Add to twitchAPI.env:
       TWITCH_CLIENT_ID=your_client_id
       TWITCH_CLIENT_SECRET=your_client_secret

Free tier: no rate limit concerns for our use case (~47 games).

Signal captured:
  - viewer_count        : total concurrent viewers across all streams
  - stream_count        : number of active streams for the game
  - avg_viewers         : average viewers per stream
  - top_stream_viewers  : viewers on the single most-watched stream
"""

import os
import requests
from datetime import date
from dotenv import load_dotenv
from db import get_connection

load_dotenv("twitchAPI.env")

SNAPSHOT_DATE = date.today().isoformat()
TWITCH_CLIENT_ID     = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")


def get_twitch_token() -> str:
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        raise ValueError(
            "Twitch credentials not set. Create twitchAPI.env with:\n"
            "  TWITCH_CLIENT_ID=your_client_id\n"
            "  TWITCH_CLIENT_SECRET=your_client_secret\n"
            "Get credentials at: https://dev.twitch.tv/console"
        )
    resp = requests.post(
        "https://id.twitch.tv/oauth2/token",
        params={
            "client_id":     TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type":    "client_credentials",
        },
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_twitch_game_id(token: str, game_name: str) -> str | None:
    """Look up Twitch's internal game ID by name."""
    resp = requests.get(
        "https://api.twitch.tv/helix/games",
        params={"name": game_name},
        headers={
            "Client-Id":     TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}",
        },
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return data[0]["id"] if data else None


def fetch_twitch_streams(token: str, game_id: str) -> dict:
    """Fetch top 20 streams for a game and aggregate viewer stats."""
    resp = requests.get(
        "https://api.twitch.tv/helix/streams",
        params={"game_id": game_id, "first": 20},
        headers={
            "Client-Id":     TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}",
        },
        timeout=10
    )
    resp.raise_for_status()
    streams = resp.json().get("data", [])

    if not streams:
        return {"viewer_count": 0, "stream_count": 0, "avg_viewers": 0, "top_stream_viewers": 0}

    viewers = [s.get("viewer_count", 0) for s in streams]
    return {
        "viewer_count":       sum(viewers),
        "stream_count":       len(streams),
        "avg_viewers":        sum(viewers) // len(viewers),
        "top_stream_viewers": max(viewers),
    }


def save_twitch_data(game_id: int, twitch_game_id: str | None, data: dict):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO twitch_data (
                game_id, snapshot_date,
                twitch_game_id, viewer_count, stream_count,
                avg_viewers, top_stream_viewers, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            game_id, SNAPSHOT_DATE,
            twitch_game_id,
            data["viewer_count"],
            data["stream_count"],
            data["avg_viewers"],
            data["top_stream_viewers"],
        ))


def run():
    print(f"\n🟣 Fetching Twitch data — snapshot date: {SNAPSHOT_DATE}\n")

    token = get_twitch_token()

    with get_connection() as conn:
        games = conn.execute("SELECT id, name FROM games").fetchall()

    print(f"Found {len(games)} games to process\n")

    for game in games:
        print(f"→ {game['name']}")
        try:
            twitch_game_id = get_twitch_game_id(token, game["name"])
            if not twitch_game_id:
                print(f"  ⚠️  Not found on Twitch")
                save_twitch_data(game["id"], None, {
                    "viewer_count": 0, "stream_count": 0,
                    "avg_viewers": 0, "top_stream_viewers": 0
                })
                continue

            data = fetch_twitch_streams(token, twitch_game_id)
            save_twitch_data(game["id"], twitch_game_id, data)
            print(f"  ✅ viewers={data['viewer_count']:,} | streams={data['stream_count']} | top={data['top_stream_viewers']:,}")

        except Exception as e:
            print(f"  ❌ Error: {e}")

    print("\n✅ Twitch fetch complete.")


if __name__ == "__main__":
    run()
