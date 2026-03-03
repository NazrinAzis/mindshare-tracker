"""
dashboard.py — mindSHARE web dashboard
Serves a single-page HTML dashboard from the SQLite database.

Usage:
    python dashboard.py
Then open: http://localhost:8080
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from db import get_connection
from datetime import datetime, date


# ── Data ─────────────────────────────────────────────────────────────────────

def get_dashboard_data():
    with get_connection() as conn:

        # Current snapshot rows with raw signal values
        rows = conn.execute("""
            SELECT
                g.name,
                g.status,
                g.release_date,
                g.genre,
                g.business_model,
                g.platform,
                ms.mindshare_score,
                ms.snapshot_date,
                -- raw Google score (already 0-100 from Trends)
                gt.interest_score        AS google_raw,
                -- raw YouTube top video views
                yt.top_video_views       AS youtube_raw,
                -- raw Steam owner range
                sd.owners_min            AS steam_owners_min,
                sd.owners_max            AS steam_owners_max,
                -- raw Reddit + Twitch
                rd.total_score           AS reddit_raw,
                td.viewer_count          AS twitch_raw,
                -- raw TikTok
                tk.total_views           AS tiktok_raw,
                -- previous snapshot score for delta
                prev.mindshare_score     AS prev_score
            FROM mindshare_scores ms
            JOIN games g ON g.id = ms.game_id
            -- raw signals (latest available per source)
            LEFT JOIN google_trends_data gt
                ON gt.game_id = ms.game_id
                AND gt.snapshot_date = (SELECT MAX(snapshot_date) FROM google_trends_data)
            LEFT JOIN youtube_data yt
                ON yt.game_id = ms.game_id
                AND yt.snapshot_date = (SELECT MAX(snapshot_date) FROM youtube_data)
            LEFT JOIN steam_data sd
                ON sd.game_id = ms.game_id
                AND sd.snapshot_date = (SELECT MAX(snapshot_date) FROM steam_data)
            LEFT JOIN reddit_data rd
                ON rd.game_id = ms.game_id
                AND rd.snapshot_date = (SELECT MAX(snapshot_date) FROM reddit_data)
            LEFT JOIN twitch_data td
                ON td.game_id = ms.game_id
                AND td.snapshot_date = (SELECT MAX(snapshot_date) FROM twitch_data)
            LEFT JOIN tiktok_data tk
                ON tk.game_id = ms.game_id
                AND tk.snapshot_date = (SELECT MAX(snapshot_date) FROM tiktok_data)
            -- previous week's score for delta
            LEFT JOIN mindshare_scores prev
                ON prev.game_id = ms.game_id
                AND prev.snapshot_date = (
                    SELECT MAX(snapshot_date) FROM mindshare_scores
                    WHERE snapshot_date < ms.snapshot_date
                )
            WHERE ms.snapshot_date = (SELECT MAX(snapshot_date) FROM mindshare_scores)
            ORDER BY g.status ASC, ms.mindshare_score DESC
        """).fetchall()

        snapshot_date = rows[0]["snapshot_date"] if rows else date.today().isoformat()
        released = [r for r in rows if (r["status"] or "released") == "released"]
        upcoming = [r for r in rows if (r["status"] or "released") == "upcoming"]
        return released, upcoming, snapshot_date


# ── Formatters ────────────────────────────────────────────────────────────────

def fmt_google(score):
    if score is None:
        return '<span class="raw-na">No data</span>'
    return f'<span class="raw-val">{score:.0f}</span><span class="raw-unit"> / 100</span>'


def fmt_youtube(views):
    if views is None:
        return '<span class="raw-na">No data</span>'
    if views >= 1_000_000:
        return f'<span class="raw-val">{views/1_000_000:.1f}M</span><span class="raw-unit"> views</span>'
    if views >= 1_000:
        return f'<span class="raw-val">{views/1_000:.0f}K</span><span class="raw-unit"> views</span>'
    return f'<span class="raw-val">{views}</span><span class="raw-unit"> views</span>'


def fmt_steam(owners_min, owners_max):
    if owners_min is None:
        return '<span class="raw-na">Not on Steam</span>'
    if owners_min >= 1_000_000:
        label = f"{owners_min // 1_000_000}M+"
    elif owners_min >= 1_000:
        label = f"{owners_min // 1_000}K+"
    else:
        label = f"{owners_min}+"
    return f'<span class="raw-val">{label}</span><span class="raw-unit"> owners</span>'


def fmt_reddit(total_score):
    if total_score is None:
        return '<span class="raw-na">No data</span>'
    if total_score >= 1_000_000:
        return f'<span class="raw-val">{total_score/1_000_000:.1f}M</span><span class="raw-unit"> pts</span>'
    if total_score >= 1_000:
        return f'<span class="raw-val">{total_score/1_000:.0f}K</span><span class="raw-unit"> pts</span>'
    return f'<span class="raw-val">{total_score}</span><span class="raw-unit"> pts</span>'


def fmt_tiktok(total_views):
    if total_views is None:
        return '<span class="raw-na">No data</span>'
    if total_views == 0:
        return '<span class="raw-na">No videos</span>'
    if total_views >= 1_000_000:
        return f'<span class="raw-val">{total_views/1_000_000:.1f}M</span><span class="raw-unit"> views</span>'
    if total_views >= 1_000:
        return f'<span class="raw-val">{total_views/1_000:.0f}K</span><span class="raw-unit"> views</span>'
    return f'<span class="raw-val">{total_views}</span><span class="raw-unit"> views</span>'


def fmt_twitch(viewer_count):
    if viewer_count is None:
        return '<span class="raw-na">No data</span>'
    if viewer_count == 0:
        return '<span class="raw-na">No streams</span>'
    if viewer_count >= 1_000_000:
        return f'<span class="raw-val">{viewer_count/1_000_000:.1f}M</span><span class="raw-unit"> viewers</span>'
    if viewer_count >= 1_000:
        return f'<span class="raw-val">{viewer_count/1_000:.0f}K</span><span class="raw-unit"> viewers</span>'
    return f'<span class="raw-val">{viewer_count}</span><span class="raw-unit"> viewers</span>'


def fmt_delta(current, previous):
    if previous is None:
        return '<span class="delta neutral">New</span>'
    diff = current - previous
    if abs(diff) < 0.1:
        return '<span class="delta neutral">—</span>'
    if diff > 0:
        return f'<span class="delta up">▲ {diff:.1f}</span>'
    return f'<span class="delta down">▼ {abs(diff):.1f}</span>'


def score_color(score):
    if score >= 35:
        return "#00ff88"
    elif score >= 15:
        return "#ffd700"
    else:
        return "#ff4d4d"


def days_until(release_date_str):
    if not release_date_str:
        return None
    try:
        rd = datetime.strptime(release_date_str, "%Y-%m-%d").date()
        return (rd - date.today()).days
    except Exception:
        return None


# ── HTML builders ─────────────────────────────────────────────────────────────

def build_rows_html(rows):
    html = ""
    for rank, row in enumerate(rows, 1):
        score = row["mindshare_score"] or 0
        color = score_color(score)

        rank_color = ""
        if rank == 1:   rank_color = 'style="color:#ffd700"'
        elif rank == 2: rank_color = 'style="color:#c0c0c0"'
        elif rank == 3: rank_color = 'style="color:#cd7f32"'

        # Launch countdown badge
        launch_badge = ""
        d = days_until(row["release_date"])
        if d is not None and d > 0:
            launch_badge = f'<span class="launch-badge">T-{d}d</span>'
        elif d is not None and d <= 0:
            launch_badge = '<span class="launch-badge launched">Launching</span>'

        # Status chip
        status = row["status"] or "released"
        status_cell = (
            '<span class="status-chip upcoming">Upcoming</span>'
            if status == "upcoming"
            else '<span class="status-chip released">Released</span>'
        )

        # Delta vs previous snapshot
        delta_html = fmt_delta(score, row["prev_score"])

        html += f"""
        <tr>
            <td class="rank" {rank_color}>#{rank}</td>
            <td class="game-name">
                <span class="name">{row['name']} {launch_badge}</span>
                <span class="meta">{row['genre'] or ''} &middot; {row['business_model'] or ''} &middot; {row['platform'] or ''}</span>
            </td>
            <td>{status_cell}</td>
            <td class="score-cell">
                <span class="score" style="color:{color}; text-shadow: 0 0 12px {color}88;">{score:.1f}</span>
                <span class="score-delta">{delta_html}</span>
            </td>
            <td class="raw-cell">{fmt_google(row['google_raw'])}</td>
            <td class="raw-cell">{fmt_twitch(row['twitch_raw'])}</td>
            <td class="raw-cell">{fmt_youtube(row['youtube_raw'])}</td>
            <td class="raw-cell">{fmt_steam(row['steam_owners_min'], row['steam_owners_max'])}</td>
            <td class="raw-cell">{fmt_reddit(row['reddit_raw'])}</td>
            <td class="raw-cell">{fmt_tiktok(row['tiktok_raw'])}</td>
        </tr>"""
    return html


def build_html(released, upcoming, snapshot_date):
    formatted_date = datetime.strptime(snapshot_date, "%Y-%m-%d").strftime("%B %d, %Y")
    top_game    = released[0]["name"]             if released else "—"
    top_score   = released[0]["mindshare_score"]  if released else 0
    top_upcoming = upcoming[0]["name"]            if upcoming else "—"

    released_rows = build_rows_html(released)
    upcoming_rows = build_rows_html(upcoming)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>mindSHARE Tracker</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Orbitron:wght@700;900&display=swap');

        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            background: #07070f;
            color: #c8ccd8;
            font-family: 'Inter', sans-serif;
            min-height: 100vh;
            padding: 0 0 80px;
        }}

        /* ── Header ── */
        header {{
            background: linear-gradient(180deg, #0d0d1a 0%, #07070f 100%);
            border-bottom: 1px solid #1e1e3a;
            padding: 32px 48px 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
        }}

        .logo h1 {{
            font-family: 'Orbitron', monospace;
            font-size: 1.9rem;
            font-weight: 900;
            letter-spacing: 0.08em;
            color: #fff;
        }}
        .logo h1 span {{ color: #00ff88; text-shadow: 0 0 20px #00ff8866; }}
        .logo p {{ font-size: 0.8rem; color: #555878; letter-spacing: 0.12em; text-transform: uppercase; margin-top: 4px; }}
        .header-meta {{ text-align: right; }}
        .snapshot-label {{ font-size: 0.7rem; color: #555878; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 4px; }}
        .snapshot-date {{ font-size: 1rem; font-weight: 600; color: #a0a8c8; }}

        /* ── Disclaimer banner ── */
        .disclaimer {{
            background: #0c0c1e;
            border-bottom: 1px solid #1e1e3a;
            padding: 10px 48px;
            font-size: 0.73rem;
            color: #555878;
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .disclaimer strong {{ color: #7878a8; }}
        .disclaimer-dot {{ color: #2a2a44; }}

        /* ── Stats bar ── */
        .stats-bar {{
            display: flex;
            gap: 24px;
            padding: 20px 48px;
            border-bottom: 1px solid #1e1e3a;
            background: #09091a;
            flex-wrap: wrap;
        }}
        .stat {{ display: flex; flex-direction: column; gap: 2px; }}
        .stat-value {{ font-size: 1.4rem; font-weight: 700; color: #fff; }}
        .stat-label {{ font-size: 0.7rem; color: #555878; text-transform: uppercase; letter-spacing: 0.1em; }}
        .stat-divider {{ width: 1px; background: #1e1e3a; margin: 0 8px; }}

        /* ── Section headers ── */
        .section-header {{
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 36px 48px 0;
        }}
        .section-title {{
            font-family: 'Orbitron', monospace;
            font-size: 0.85rem;
            font-weight: 700;
            letter-spacing: 0.15em;
            text-transform: uppercase;
        }}
        .section-title.released {{ color: #00ff88; }}
        .section-title.upcoming {{ color: #bf9aff; }}
        .section-line {{ flex: 1; height: 1px; background: #1e1e3a; }}
        .section-pill {{
            font-size: 0.7rem;
            padding: 3px 10px;
            border-radius: 20px;
            font-weight: 600;
        }}
        .section-pill.released {{ background: #00ff8818; color: #00ff88; border: 1px solid #00ff8840; }}
        .section-pill.upcoming {{ background: #bf9aff18; color: #bf9aff; border: 1px solid #bf9aff40; }}

        /* ── Weight / info bar ── */
        .info-bar {{
            display: flex;
            gap: 10px;
            padding: 12px 48px 16px;
            font-size: 0.72rem;
            color: #555878;
            align-items: center;
            flex-wrap: wrap;
        }}
        .weight-chip {{
            background: #111128;
            border: 1px solid #1e1e3a;
            border-radius: 20px;
            padding: 2px 10px;
            color: #8890b8;
        }}
        .weight-chip b {{ color: #c8ccd8; }}
        .weight-chip.muted {{ opacity: 0.4; }}

        /* ── Legend ── */
        .legend-item {{ display: flex; align-items: center; gap: 6px; }}
        .legend-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}

        /* ── Table ── */
        .table-wrap {{ padding: 0 48px; overflow-x: auto; }}

        table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}

        thead th {{
            padding: 10px 16px;
            text-align: left;
            font-size: 0.68rem;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: #555878;
            border-bottom: 1px solid #1e1e3a;
            white-space: nowrap;
            cursor: default;
        }}

        thead th.center {{ text-align: center; }}

        /* Tooltip on header */
        thead th[data-tip] {{ position: relative; }}
        thead th[data-tip]:hover::after {{
            content: attr(data-tip);
            position: absolute;
            top: calc(100% + 6px);
            left: 0;
            background: #1a1a30;
            border: 1px solid #2e2e50;
            color: #c8ccd8;
            font-size: 0.7rem;
            font-weight: 400;
            letter-spacing: 0;
            text-transform: none;
            padding: 8px 12px;
            border-radius: 6px;
            width: 240px;
            white-space: normal;
            z-index: 100;
            line-height: 1.5;
            box-shadow: 0 4px 20px #00000060;
        }}

        tbody tr {{ border-bottom: 1px solid #111128; transition: background 0.15s; }}
        tbody tr:hover {{ background: #0e0e20; }}
        tbody td {{ padding: 13px 16px; vertical-align: middle; }}

        .rank {{
            font-family: 'Orbitron', monospace;
            font-size: 0.75rem;
            color: #333558;
            font-weight: 700;
            width: 48px;
        }}

        .game-name {{ min-width: 180px; }}
        .name {{ display: block; font-weight: 600; color: #e8ecf8; margin-bottom: 3px; }}
        .meta {{ font-size: 0.72rem; color: #444666; }}

        .score-cell {{ text-align: center; width: 100px; }}
        .score {{ font-family: 'Orbitron', monospace; font-size: 1.2rem; font-weight: 700; display: block; }}
        .score-delta {{ display: block; margin-top: 2px; font-size: 0.7rem; }}

        /* ── Delta ── */
        .delta {{ font-weight: 700; }}
        .delta.up {{ color: #00ff88; }}
        .delta.down {{ color: #ff4d4d; }}
        .delta.neutral {{ color: #444666; }}

        /* ── Raw value cells ── */
        .raw-cell {{ white-space: nowrap; }}
        .raw-val {{ font-weight: 600; color: #e8ecf8; }}
        .raw-unit {{ font-size: 0.78rem; color: #555878; }}
        .raw-na {{ font-size: 0.78rem; color: #333558; font-style: italic; }}

        /* ── Status chip ── */
        .status-chip {{
            display: inline-block;
            font-size: 0.68rem;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 20px;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            white-space: nowrap;
        }}
        .status-chip.released {{ background: #00ff8818; color: #00ff88; border: 1px solid #00ff8840; }}
        .status-chip.upcoming {{ background: #bf9aff18; color: #bf9aff; border: 1px solid #bf9aff40; }}

        /* ── Launch badge ── */
        .launch-badge {{
            display: inline-block;
            font-size: 0.62rem;
            font-weight: 700;
            padding: 1px 7px;
            border-radius: 10px;
            background: #bf9aff22;
            color: #bf9aff;
            border: 1px solid #bf9aff44;
            margin-left: 6px;
            vertical-align: middle;
            letter-spacing: 0.05em;
        }}
        .launch-badge.launched {{ background: #00ff8822; color: #00ff88; border-color: #00ff8844; }}

        /* ── Source badges ── */
        .source-badges {{
            display: flex;
            gap: 8px;
            padding: 0 48px 0;
            margin-bottom: -4px;
        }}
        .source-badge {{
            font-size: 0.65rem;
            color: #333558;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 2px 0;
            border-top: 2px solid #1e1e3a;
            min-width: 140px;
        }}
        .source-badge span {{ color: #444666; }}

        /* ── Footer ── */
        footer {{ text-align: center; margin-top: 60px; font-size: 0.72rem; color: #2a2a44; letter-spacing: 0.08em; }}
    </style>
</head>
<body>

<header>
    <div class="logo">
        <h1>mind<span>SHARE</span></h1>
        <p>Gaming Market Intelligence</p>
    </div>
    <div class="header-meta">
        <div class="snapshot-label">Snapshot date</div>
        <div class="snapshot-date">{formatted_date}</div>
    </div>
</header>

<div class="disclaimer">
    <strong>About this data:</strong>
    All signals are aggregated population-level data — no individual user tracking.
    <span class="disclaimer-dot">&middot;</span>
    mindSHARE scores are <strong>relative to the tracked game list</strong>, not absolute market share.
    <span class="disclaimer-dot">&middot;</span>
    Google Trends &amp; YouTube reflect the last 28 days &middot; Reddit reflects the last 7 days &middot; Twitch is a live snapshot.
    <span class="disclaimer-dot">&middot;</span>
    Steam owners are estimated ranges from SteamSpy.
</div>

<div class="stats-bar">
    <div class="stat">
        <span class="stat-value">{len(released)}</span>
        <span class="stat-label">Released Games</span>
    </div>
    <div class="stat-divider"></div>
    <div class="stat">
        <span class="stat-value" style="color:#bf9aff">{len(upcoming)}</span>
        <span class="stat-label">Upcoming Titles</span>
    </div>
    <div class="stat-divider"></div>
    <div class="stat">
        <span class="stat-value" style="color:#00ff88">{top_game}</span>
        <span class="stat-label">#1 Released</span>
    </div>
    <div class="stat-divider"></div>
    <div class="stat">
        <span class="stat-value">{top_score:.1f}</span>
        <span class="stat-label">Top Score</span>
    </div>
    <div class="stat-divider"></div>
    <div class="stat">
        <span class="stat-value" style="color:#bf9aff">{top_upcoming}</span>
        <span class="stat-label">#1 Pre-launch Buzz</span>
    </div>
</div>

<!-- ══ RELEASED GAMES ══════════════════════════════════════════════════════ -->
<div class="section-header">
    <span class="section-title released">Released Games</span>
    <span class="section-pill released">{len(released)} titles</span>
    <div class="section-line"></div>
</div>

<div class="info-bar">
    <span>Weights:</span>
    <span class="weight-chip">🔍 Google <b>27%</b></span>
    <span class="weight-chip">🟣 Twitch <b>22.5%</b></span>
    <span class="weight-chip">▶ YouTube <b>18%</b></span>
    <span class="weight-chip">🎮 Steam <b>13.5%</b></span>
    <span class="weight-chip">🟠 Reddit <b>9%</b></span>
    <span class="weight-chip">🎵 TikTok <b>10%</b></span>
    &nbsp;&nbsp;
    <span class="legend-item"><span class="legend-dot" style="background:#00ff88"></span>&nbsp;High (&ge;35)</span>&nbsp;
    <span class="legend-item"><span class="legend-dot" style="background:#ffd700"></span>&nbsp;Medium (15–35)</span>&nbsp;
    <span class="legend-item"><span class="legend-dot" style="background:#ff4d4d"></span>&nbsp;Low (&lt;15)</span>
</div>

<div class="table-wrap">
    <table>
        <thead>
            <tr>
                <th>Rank</th>
                <th>Game</th>
                <th>Status</th>
                <th class="center"
                    data-tip="Composite score (0–100) weighted across 6 signals: Google Trends (27%), Twitch (22.5%), YouTube (18%), Steam (13.5%), Reddit (9%), TikTok (10%). Scores are relative to the tracked game list — not absolute market share.">
                    mindSHARE ⓘ</th>
                <th data-tip="Google Trends interest score (0–100). Measures relative search volume over the last 3 months. 100 = peak interest for that term. Source: Google Trends (aggregated, anonymised).">
                    🔍 Google Trends ⓘ</th>
                <th data-tip="Total concurrent viewers across all live streams of this game on Twitch at time of snapshot. Strong real-time engagement signal. Source: Twitch Helix API.">
                    🟣 Twitch Viewers ⓘ</th>
                <th data-tip="View count of the most-viewed recent gameplay video on YouTube, published in the last 28 days. Proxy for active content creation &amp; audience engagement. Source: YouTube Data API v3.">
                    ▶ YouTube Views ⓘ</th>
                <th data-tip="Estimated total Steam owner count (lower bound of range). Reflects cumulative PC installs — not active players. Source: SteamSpy (estimated, not official Valve data).">
                    🎮 Steam Owners ⓘ</th>
                <th data-tip="Sum of upvote scores across the top 100 Reddit posts mentioning this game in the last 7 days. Reflects community discussion volume and sentiment. Source: Reddit public search API.">
                    🟠 Reddit Score ⓘ</th>
                <th data-tip="Total views across the top 100 TikTok videos mentioning this game in the last 28 days. Reflects short-form content reach and viral momentum. Source: TikTok Research API.">
                    🎵 TikTok Views ⓘ</th>
            </tr>
        </thead>
        <tbody>{released_rows}</tbody>
    </table>
</div>

<!-- ══ UPCOMING TITLES ═════════════════════════════════════════════════════ -->
<div class="section-header" style="margin-top:56px;">
    <span class="section-title upcoming">Upcoming Titles — Pre-launch mindSHARE</span>
    <span class="section-pill upcoming">{len(upcoming)} titles</span>
    <div class="section-line"></div>
</div>

<div class="info-bar">
    <span>Weights:</span>
    <span class="weight-chip">🔍 Google <b>31.5%</b></span>
    <span class="weight-chip">🟠 Reddit <b>22.5%</b></span>
    <span class="weight-chip">▶ YouTube <b>22.5%</b></span>
    <span class="weight-chip">🟣 Twitch <b>13.5%</b></span>
    <span class="weight-chip">🎵 TikTok <b>10%</b></span>
    <span class="weight-chip muted">🎮 Steam <b>0%</b></span>
    &nbsp;&nbsp;
    <span style="color:#bf9aff88; font-size:0.7rem;">
        Steam excluded — no player data pre-launch &middot; T-Xd = days until release
    </span>
</div>

<div class="table-wrap">
    <table>
        <thead>
            <tr>
                <th>Rank</th>
                <th>Game</th>
                <th>Status</th>
                <th class="center"
                    data-tip="Pre-launch mindSHARE: composite buzz score weighted across Google (31.5%), Reddit (22.5%), YouTube (22.5%), Twitch (13.5%), TikTok (10%). Steam excluded — no player data pre-launch.">
                    Pre-launch Score ⓘ</th>
                <th data-tip="Google Trends interest score (0–100). Measures relative search volume over the last 3 months. Higher = more people searching for this title. Source: Google Trends.">
                    🔍 Google Trends ⓘ</th>
                <th data-tip="Total concurrent viewers across all live streams of this game on Twitch. Even pre-launch, developer streams and early access streams drive viewership. Source: Twitch Helix API.">
                    🟣 Twitch Viewers ⓘ</th>
                <th data-tip="View count of the most-viewed recent trailer or preview video on YouTube in the last 28 days. Key pre-launch hype signal. Source: YouTube Data API v3.">
                    ▶ YouTube Views ⓘ</th>
                <th data-tip="Not applicable for upcoming games — SteamSpy only tracks released titles. Will populate after launch.">
                    🎮 Steam Owners ⓘ</th>
                <th data-tip="Sum of upvote scores across the top 100 Reddit posts mentioning this game in the last 7 days. Strong pre-launch community buzz signal. Source: Reddit public search API.">
                    🟠 Reddit Score ⓘ</th>
                <th data-tip="Total views across the top 100 TikTok videos mentioning this game in the last 28 days. Key pre-launch viral signal. Source: TikTok Research API.">
                    🎵 TikTok Views ⓘ</th>
            </tr>
        </thead>
        <tbody>{upcoming_rows}</tbody>
    </table>
</div>

<footer>
    mindSHARE TRACKER &mdash; DATA REFRESHES WEEKLY &mdash;
    POWERED BY STEAMSPY &middot; GOOGLE TRENDS &middot; YOUTUBE DATA API V3 &middot; REDDIT &middot; TWITCH HELIX API &middot; TIKTOK RESEARCH API &mdash;
    ALL DATA AGGREGATED &middot; NO USER-LEVEL TRACKING
</footer>

</body>
</html>"""


# ── Server ────────────────────────────────────────────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_response(404)
            self.end_headers()
            return

        released, upcoming, snapshot_date = get_dashboard_data()
        html = build_html(released, upcoming, snapshot_date)
        encoded = html.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = 8080
    server = HTTPServer(("localhost", port), DashboardHandler)
    print(f"mindSHARE dashboard running at http://localhost:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
