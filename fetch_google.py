"""
fetch_google.py — Pulls relative search interest from Google Trends via pytrends
pytrends docs: https://github.com/GeneralMills/pytrends

Install: pip install pytrends

Note: Google Trends returns *relative* scores (0-100) where 100 = peak interest.
      When comparing multiple games, pytrends normalizes them against each other.
      We fetch games in batches of 5 (Google Trends limit) and anchor each batch
      to a common "anchor" game (e.g. "Minecraft") to allow cross-batch comparison.
"""

import time
from datetime import date
from pytrends.request import TrendReq
from db import get_connection

SNAPSHOT_DATE = date.today().isoformat()
ANCHOR_GAME = "Minecraft"       # Used as a reference point across all batches
GEO = ""                        # "" = worldwide, "US" = United States, etc.
TIMEFRAME = "today 3-m"         # Last 3 months
BATCH_SIZE = 4                  # Max 5 keywords per request; we use 4 + anchor = 5


def get_all_games() -> list[dict]:
    with get_connection() as conn:
        return conn.execute("SELECT id, name FROM games").fetchall()


def chunk_games(games: list, size: int) -> list[list]:
    """Split games list into batches, excluding the anchor game."""
    non_anchor = [g for g in games if g["name"] != ANCHOR_GAME]
    return [non_anchor[i:i+size] for i in range(0, len(non_anchor), size)]


def fetch_trends_batch(pytrends: TrendReq, keywords: list[str]) -> dict:
    """
    Fetch Google Trends interest for a batch of keywords.
    Returns dict: {keyword: interest_score (0-100)}
    """
    pytrends.build_payload(keywords, cat=0, timeframe=TIMEFRAME, geo=GEO)
    df = pytrends.interest_over_time()

    if df.empty:
        return {kw: None for kw in keywords}

    # Take the mean interest over the timeframe for each keyword
    results = {}
    for kw in keywords:
        if kw in df.columns:
            results[kw] = round(df[kw].mean(), 2)
        else:
            results[kw] = None
    return results


def save_google_data(game_id: int, interest_score: float):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO google_trends_data (
                game_id, snapshot_date, interest_score, geo, timeframe
            ) VALUES (?, ?, ?, ?, ?)
        """, (game_id, SNAPSHOT_DATE, interest_score, GEO or "worldwide", TIMEFRAME))


def run():
    print(f"\n🔍 Fetching Google Trends data — snapshot date: {SNAPSHOT_DATE}\n")

    pytrends = TrendReq(hl="en-US", tz=0)
    all_games = get_all_games()
    game_lookup = {g["name"]: g["id"] for g in all_games}

    # First, get the anchor game's score solo
    print(f"→ Fetching anchor game: {ANCHOR_GAME}")
    anchor_result = fetch_trends_batch(pytrends, [ANCHOR_GAME])
    anchor_score = anchor_result.get(ANCHOR_GAME) or 0
    print(f"  {ANCHOR_GAME}: {anchor_score}")
    save_google_data(game_lookup[ANCHOR_GAME], anchor_score)
    time.sleep(2)

    # Fetch remaining games in batches of BATCH_SIZE, always including anchor for normalization
    batches = chunk_games(all_games, BATCH_SIZE)
    print(f"\nFetching {len(batches)} batches of up to {BATCH_SIZE} games...\n")

    for i, batch in enumerate(batches):
        keywords = [ANCHOR_GAME] + [g["name"] for g in batch]
        print(f"Batch {i+1}/{len(batches)}: {[g['name'] for g in batch]}")

        results = fetch_trends_batch(pytrends, keywords)

        # Normalize scores relative to anchor
        batch_anchor_score = results.get(ANCHOR_GAME) or 1  # avoid div by zero
        normalization_factor = anchor_score / batch_anchor_score if batch_anchor_score else 1

        for game in batch:
            raw_score = results.get(game["name"])
            if raw_score is not None:
                normalized_score = round(raw_score * normalization_factor, 2)
                normalized_score = min(normalized_score, 100)  # cap at 100
            else:
                normalized_score = None

            print(f"  {game['name']}: raw={raw_score}, normalized={normalized_score}")
            if normalized_score is not None:
                save_google_data(game["id"], normalized_score)

        time.sleep(2)  # Be respectful to Google Trends

    print("\n✅ Google Trends fetch complete.")


if __name__ == "__main__":
    run()
