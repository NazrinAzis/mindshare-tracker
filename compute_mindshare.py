"""
compute_mindshare.py — Normalizes raw signals and computes the composite mindSHARE score

Scoring logic:
  - Each signal is normalized to a 0-1 scale using min-max normalization
    across all games for that snapshot date
  - Signals are then combined using configurable weights
  - Final score is scaled to 0-100

Released game weights:
  Google Trends  → 0.45
  YouTube        → 0.35
  Steam          → 0.20

Upcoming game weights (no Steam data available):
  Google Trends  → 0.60  (broad awareness / search buzz)
  YouTube        → 0.40  (trailer views / hype content)
  Steam          → 0.00
"""

from datetime import date
from db import get_connection

SNAPSHOT_DATE = date.today().isoformat()

WEIGHTS_RELEASED = {"google": 0.45, "youtube": 0.35, "steam": 0.20}
WEIGHTS_UPCOMING = {"google": 0.60, "youtube": 0.40, "steam": 0.00}


def min_max_normalize(values: list[float]) -> list[float]:
    """Normalize a list of values to 0-1 range."""
    valid = [v for v in values if v is not None]
    if not valid or max(valid) == min(valid):
        return [0.0 if v is None else 0.5 for v in values]
    min_v, max_v = min(valid), max(valid)
    return [
        None if v is None else (v - min_v) / (max_v - min_v)
        for v in values
    ]


def run():
    print(f"\n📊 Computing mindSHARE scores — snapshot date: {SNAPSHOT_DATE}\n")

    with get_connection() as conn:
        games = conn.execute("SELECT id, name, status FROM games").fetchall()
        game_ids   = [g["id"] for g in games]
        game_names = {g["id"]: g["name"] for g in games}
        game_status = {g["id"]: g["status"] or "released" for g in games}

        # --- Collect raw signals ---

        # Use the latest available snapshot per signal (each may be fetched on different dates)
        google_raw = {}
        for r in conn.execute("""
            SELECT game_id, interest_score FROM google_trends_data
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM google_trends_data)
        """).fetchall():
            google_raw[r["game_id"]] = r["interest_score"]

        youtube_raw = {}
        for r in conn.execute("""
            SELECT game_id, top_video_views FROM youtube_data
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM youtube_data)
        """).fetchall():
            youtube_raw[r["game_id"]] = r["top_video_views"]

        # Steam — use owners_min (players_2weeks not reliable from SteamSpy)
        steam_raw = {}
        for r in conn.execute("""
            SELECT game_id, owners_min FROM steam_data
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM steam_data)
        """).fetchall():
            steam_raw[r["game_id"]] = r["owners_min"]

    # --- Normalize each signal across ALL games together ---
    google_values  = [google_raw.get(gid) for gid in game_ids]
    youtube_values = [youtube_raw.get(gid) for gid in game_ids]
    steam_values   = [steam_raw.get(gid) for gid in game_ids]

    google_norm  = min_max_normalize(google_values)
    youtube_norm = min_max_normalize(youtube_values)
    steam_norm   = min_max_normalize(steam_values)

    # --- Compute composite scores ---
    results = []
    for i, game_id in enumerate(game_ids):
        g = google_norm[i]  if google_norm[i]  is not None else 0
        y = youtube_norm[i] if youtube_norm[i] is not None else 0
        s = steam_norm[i]   if steam_norm[i]   is not None else 0

        status = game_status[game_id]
        has_steam = steam_raw.get(game_id) is not None

        if status == "upcoming":
            # Pre-launch: no Steam signal, fixed Google/YouTube weights
            w_g, w_y, w_s = WEIGHTS_UPCOMING["google"], WEIGHTS_UPCOMING["youtube"], 0.0
        elif not has_steam:
            # Released but no Steam presence (e.g. Fortnite) — redistribute Steam weight
            total = WEIGHTS_RELEASED["google"] + WEIGHTS_RELEASED["youtube"]
            w_g = WEIGHTS_RELEASED["google"] / total
            w_y = WEIGHTS_RELEASED["youtube"] / total
            w_s = 0.0
        else:
            w_g = WEIGHTS_RELEASED["google"]
            w_y = WEIGHTS_RELEASED["youtube"]
            w_s = WEIGHTS_RELEASED["steam"]

        score = round((g * w_g + y * w_y + s * w_s) * 100, 2)
        results.append((game_id, game_names[game_id], status, score, g, y, s, w_g, w_y, w_s))

    results.sort(key=lambda x: x[3], reverse=True)

    # --- Save to DB ---
    with get_connection() as conn:
        for game_id, name, status, score, g_norm, y_norm, s_norm, w_g, w_y, w_s in results:
            conn.execute("""
                INSERT OR REPLACE INTO mindshare_scores (
                    game_id, snapshot_date,
                    google_score_normalized, youtube_score_normalized, steam_score_normalized,
                    google_weight, youtube_weight, steam_weight,
                    mindshare_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id, SNAPSHOT_DATE,
                round(g_norm, 4), round(y_norm, 4), round(s_norm, 4),
                round(w_g, 4), round(w_y, 4), round(w_s, 4),
                score
            ))

    # --- Print leaderboard (two sections) ---
    released  = [r for r in results if r[2] == "released"]
    upcoming  = [r for r in results if r[2] == "upcoming"]

    def print_table(rows, label):
        print(f"\n{'─'*78}")
        print(f"  {label}")
        print(f"{'─'*78}")
        print(f"{'Rank':<6} {'Game':<30} {'Score':>10}  {'Google':>8}  {'YouTube':>8}  {'Steam':>8}")
        print(f"{'─'*78}")
        for rank, (game_id, name, status, score, g, y, s, *_) in enumerate(rows, 1):
            print(f"{rank:<6} {name:<30} {score:>10.1f}  {g*100:>7.1f}%  {y*100:>7.1f}%  {s*100:>7.1f}%")

    print_table(released, "RELEASED GAMES — mindSHARE  (Google 45% / YouTube 35% / Steam 20%)")
    print_table(upcoming, "UPCOMING GAMES — Pre-launch mindSHARE  (Google 60% / YouTube 40%)")
    print(f"\n✅ Scores saved for {len(results)} games ({len(released)} released, {len(upcoming)} upcoming).")


if __name__ == "__main__":
    run()
