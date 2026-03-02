"""
fetch_steam.py — Pulls game data from SteamSpy API and stores it in SQLite
SteamSpy docs: https://steamspy.com/api.php
No API key required. Rate limit: 1 request/second.
"""

import time
import requests
from datetime import date
from db import get_connection

STEAMSPY_URL = "https://steamspy.com/api.php"
SNAPSHOT_DATE = date.today().isoformat()


def fetch_steamspy(app_id: int) -> dict | None:
    """Fetch game data from SteamSpy for a given Steam app ID."""
    try:
        response = requests.get(
            STEAMSPY_URL,
            params={"request": "appdetails", "appid": app_id},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        # SteamSpy returns error responses as dicts with no "appid" key
        if "appid" not in data:
            print(f"  ⚠️  No data for app_id {app_id}")
            return None

        return data
    except Exception as e:
        print(f"  ❌ Error fetching app_id {app_id}: {e}")
        return None


def parse_owners(owners_str: str) -> tuple[int, int]:
    """Parse '10,000,000 .. 20,000,000' into (10000000, 20000000)."""
    try:
        parts = owners_str.replace(",", "").split("..")
        return int(parts[0].strip()), int(parts[1].strip())
    except Exception:
        return 0, 0


def save_steam_data(game_id: int, data: dict):
    owners_min, owners_max = parse_owners(data.get("owners", "0 .. 0"))

    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO steam_data (
                game_id, snapshot_date,
                owners_min, owners_max,
                players_forever, players_2weeks,
                peak_ccu, average_forever, average_2weeks,
                positive, negative
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game_id,
            SNAPSHOT_DATE,
            owners_min,
            owners_max,
            data.get("players_forever", 0),
            data.get("players_2weeks", 0),
            data.get("peak_ccu", 0),
            data.get("average_forever", 0),
            data.get("average_2weeks", 0),
            data.get("positive", 0),
            data.get("negative", 0),
        ))
    print(f"  ✅ Saved Steam data for game_id {game_id} (app_id: {data['appid']})")


def run():
    print(f"\n🎮 Fetching Steam data — snapshot date: {SNAPSHOT_DATE}\n")

    with get_connection() as conn:
        games = conn.execute(
            "SELECT id, name, steam_app_id FROM games WHERE steam_app_id IS NOT NULL"
        ).fetchall()

    print(f"Found {len(games)} games with Steam app IDs\n")

    for game in games:
        print(f"→ {game['name']} (app_id: {game['steam_app_id']})")
        data = fetch_steamspy(game["steam_app_id"])
        if data:
            save_steam_data(game["id"], data)
        time.sleep(1.2)  # Respect SteamSpy rate limit (1 req/sec)

    print("\n✅ Steam fetch complete.")


if __name__ == "__main__":
    run()
