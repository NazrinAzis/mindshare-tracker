"""
compute_mindshare.py — Normalizes raw signals and computes the composite mindSHARE score

Scoring logic:
  - Each signal is normalized to a 0-1 scale using min-max normalization
    across all games for that snapshot date
  - Signals are combined using configurable weights
  - Final score is scaled to 0-100

Released game weights:
  Google Trends  → 0.27
  Twitch Viewers → 0.225
  YouTube Views  → 0.18
  Steam Owners   → 0.135
  Reddit Score   → 0.09
  TikTok Views   → 0.10

Upcoming game weights (no Steam data):
  Google Trends  → 0.315
  Reddit Posts   → 0.225
  YouTube Views  → 0.225
  Twitch Viewers → 0.135
  TikTok Views   → 0.10
  Steam          → 0.00
"""

from datetime import date
from db import get_connection

SNAPSHOT_DATE = date.today().isoformat()

WEIGHTS_RELEASED = {
    "google":  0.27,
    "twitch":  0.225,
    "youtube": 0.18,
    "steam":   0.135,
    "reddit":  0.09,
    "tiktok":  0.10,
}

WEIGHTS_UPCOMING = {
    "google":  0.315,
    "reddit":  0.225,
    "youtube": 0.225,
    "twitch":  0.135,
    "tiktok":  0.10,
    "steam":   0.00,
}


def min_max_normalize(values: list[float]) -> list[float]:
    valid = [v for v in values if v is not None]
    if not valid or max(valid) == min(valid):
        return [0.0 if v is None else 0.5 for v in values]
    min_v, max_v = min(valid), max(valid)
    return [None if v is None else (v - min_v) / (max_v - min_v) for v in values]


def run():
    print(f"\n📊 Computing mindSHARE scores — snapshot date: {SNAPSHOT_DATE}\n")

    with get_connection() as conn:
        games = conn.execute("SELECT id, name, status FROM games").fetchall()
        game_ids    = [g["id"] for g in games]
        game_names  = {g["id"]: g["name"] for g in games}
        game_status = {g["id"]: g["status"] or "released" for g in games}

        def latest(table, field):
            raw = {}
            for r in conn.execute(f"""
                SELECT game_id, {field} FROM {table}
                WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM {table})
            """).fetchall():
                raw[r["game_id"]] = r[field]
            return raw

        google_raw  = latest("google_trends_data", "interest_score")
        youtube_raw = latest("youtube_data",        "top_video_views")
        steam_raw   = latest("steam_data",          "owners_min")
        reddit_raw  = latest("reddit_data",         "total_score")
        twitch_raw  = latest("twitch_data",         "viewer_count")
        tiktok_raw  = latest("tiktok_data",         "total_views")

    # Normalize all signals across the full game list
    google_norm  = min_max_normalize([google_raw.get(gid)  for gid in game_ids])
    youtube_norm = min_max_normalize([youtube_raw.get(gid) for gid in game_ids])
    steam_norm   = min_max_normalize([steam_raw.get(gid)   for gid in game_ids])
    reddit_norm  = min_max_normalize([reddit_raw.get(gid)  for gid in game_ids])
    twitch_norm  = min_max_normalize([twitch_raw.get(gid)  for gid in game_ids])
    tiktok_norm  = min_max_normalize([tiktok_raw.get(gid)  for gid in game_ids])

    results = []
    for i, game_id in enumerate(game_ids):
        g  = google_norm[i]  or 0
        y  = youtube_norm[i] or 0
        s  = steam_norm[i]   or 0
        r  = reddit_norm[i]  or 0
        t  = twitch_norm[i]  or 0
        tk = tiktok_norm[i]  or 0

        status    = game_status[game_id]
        has_steam = steam_raw.get(game_id) is not None

        if status == "upcoming":
            W = WEIGHTS_UPCOMING
            w_s = 0.0
        elif not has_steam:
            # Released but not on Steam — redistribute Steam weight proportionally
            base = {k: v for k, v in WEIGHTS_RELEASED.items() if k != "steam"}
            total = sum(base.values())
            W = {k: v / total for k, v in base.items()}
            w_s = 0.0
        else:
            W = WEIGHTS_RELEASED
            w_s = W["steam"]

        w_g  = W["google"]
        w_y  = W["youtube"]
        w_r  = W["reddit"]
        w_t  = W["twitch"]
        w_tk = W["tiktok"]

        score = round((g*w_g + y*w_y + s*w_s + r*w_r + t*w_t + tk*w_tk) * 100, 2)
        results.append((game_id, game_names[game_id], status, score, g, y, s, r, t, tk, w_g, w_y, w_s, w_r, w_t, w_tk))

    results.sort(key=lambda x: x[3], reverse=True)

    with get_connection() as conn:
        for (game_id, name, status, score,
             g_n, y_n, s_n, r_n, t_n, tk_n,
             w_g, w_y, w_s, w_r, w_t, w_tk) in results:
            conn.execute("""
                INSERT OR REPLACE INTO mindshare_scores (
                    game_id, snapshot_date,
                    google_score_normalized, youtube_score_normalized,
                    steam_score_normalized, reddit_score_normalized, twitch_score_normalized,
                    tiktok_score_normalized,
                    google_weight, youtube_weight, steam_weight, reddit_weight, twitch_weight,
                    tiktok_weight,
                    mindshare_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id, SNAPSHOT_DATE,
                round(g_n, 4), round(y_n, 4), round(s_n, 4), round(r_n, 4), round(t_n, 4),
                round(tk_n, 4),
                round(w_g, 4), round(w_y, 4), round(w_s, 4), round(w_r, 4), round(w_t, 4),
                round(w_tk, 4),
                score
            ))

    released = [r for r in results if r[2] == "released"]
    upcoming = [r for r in results if r[2] == "upcoming"]

    def print_table(rows, label):
        print(f"\n{'─'*104}")
        print(f"  {label}")
        print(f"{'─'*104}")
        print(f"{'Rank':<6} {'Game':<28} {'Score':>8}  {'Google':>7}  {'Twitch':>7}  {'YouTube':>7}  {'Steam':>7}  {'Reddit':>7}  {'TikTok':>7}")
        print(f"{'─'*104}")
        for rank, (gid, name, status, score, g, y, s, r, t, tk, *_) in enumerate(rows, 1):
            print(f"{rank:<6} {name:<28} {score:>8.1f}  {g*100:>6.1f}%  {t*100:>6.1f}%  {y*100:>6.1f}%  {s*100:>6.1f}%  {r*100:>6.1f}%  {tk*100:>6.1f}%")

    print_table(released, "RELEASED GAMES — mindSHARE  (Google 27% / Twitch 22.5% / YouTube 18% / Steam 13.5% / Reddit 9% / TikTok 10%)")
    print_table(upcoming, "UPCOMING GAMES — Pre-launch mindSHARE  (Google 31.5% / Reddit 22.5% / YouTube 22.5% / Twitch 13.5% / TikTok 10%)")
    print(f"\n✅ Scores saved for {len(results)} games ({len(released)} released, {len(upcoming)} upcoming).")


if __name__ == "__main__":
    run()
