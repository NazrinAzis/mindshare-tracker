-- ============================================
-- MindSHARE Tracker - SQLite Schema
-- ============================================

-- Master list of games to track
CREATE TABLE IF NOT EXISTS games (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,           -- e.g. "Minecraft"
    steam_app_id    INTEGER,                        -- SteamSpy app ID
    twitch_name     TEXT,                           -- Exact name on Twitch (for future)
    genre           TEXT,
    publisher       TEXT,
    developer       TEXT,
    release_date    TEXT,                           -- ISO date string
    business_model  TEXT,                           -- "F2P", "Premium", "Subscription"
    platform        TEXT,                           -- "PC", "Console", "Cross-platform"
    status          TEXT DEFAULT 'released',        -- "released" or "upcoming"
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Weekly SteamSpy snapshots
CREATE TABLE IF NOT EXISTS steam_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES games(id),
    snapshot_date   TEXT NOT NULL,                  -- ISO date of the snapshot (weekly)
    owners_min      INTEGER,                        -- SteamSpy owner range lower bound
    owners_max      INTEGER,                        -- SteamSpy owner range upper bound
    players_forever INTEGER,                        -- Total players ever
    players_2weeks  INTEGER,                        -- Players in last 2 weeks
    peak_ccu        INTEGER,                        -- Peak concurrent users
    average_forever INTEGER,                        -- Avg playtime (minutes) all time
    average_2weeks  INTEGER,                        -- Avg playtime (minutes) last 2 weeks
    positive        INTEGER,                        -- Positive reviews
    negative        INTEGER,                        -- Negative reviews
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(game_id, snapshot_date)
);

-- Weekly Google Trends snapshots
CREATE TABLE IF NOT EXISTS google_trends_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES games(id),
    snapshot_date   TEXT NOT NULL,                  -- ISO date of the snapshot
    interest_score  REAL,                           -- 0-100 relative interest from Google Trends
    geo             TEXT DEFAULT 'worldwide',       -- "worldwide" or ISO country code
    timeframe       TEXT DEFAULT 'today 3-m',       -- pytrends timeframe string
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(game_id, snapshot_date, geo)
);

-- Weekly YouTube snapshots
CREATE TABLE IF NOT EXISTS youtube_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES games(id),
    snapshot_date   TEXT NOT NULL,
    total_results   INTEGER,                        -- Number of videos found
    top_video_views INTEGER,                        -- View count of top result
    top_video_likes INTEGER,
    top_video_id    TEXT,                           -- YouTube video ID
    query_used      TEXT,                           -- The search query used
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(game_id, snapshot_date)
);

-- Reddit activity snapshots
CREATE TABLE IF NOT EXISTS reddit_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES games(id),
    snapshot_date   TEXT NOT NULL,
    post_count      INTEGER,
    total_score     INTEGER,
    top_post_score  INTEGER,
    top_post_title  TEXT,
    created_at      TEXT,
    UNIQUE(game_id, snapshot_date)
);

-- Twitch live stream snapshots
CREATE TABLE IF NOT EXISTS twitch_data (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id             INTEGER NOT NULL REFERENCES games(id),
    snapshot_date       TEXT NOT NULL,
    twitch_game_id      TEXT,
    viewer_count        INTEGER,
    stream_count        INTEGER,
    avg_viewers         INTEGER,
    top_stream_viewers  INTEGER,
    created_at          TEXT,
    UNIQUE(game_id, snapshot_date)
);

-- TikTok video snapshots
CREATE TABLE IF NOT EXISTS tiktok_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         INTEGER NOT NULL REFERENCES games(id),
    snapshot_date   TEXT NOT NULL,
    video_count     INTEGER,
    total_views     INTEGER,
    total_likes     INTEGER,
    top_video_views INTEGER,
    query_used      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(game_id, snapshot_date)
);

-- Computed mindSHARE scores (derived table)
CREATE TABLE IF NOT EXISTS mindshare_scores (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id                 INTEGER NOT NULL REFERENCES games(id),
    snapshot_date           TEXT NOT NULL,
    -- Normalized signals (0-1 scale)
    steam_score_normalized  REAL,
    google_score_normalized REAL,
    youtube_score_normalized REAL,
    reddit_score_normalized  REAL,
    twitch_score_normalized  REAL,
    -- Weights used
    steam_weight            REAL DEFAULT 0.15,
    google_weight           REAL DEFAULT 0.30,
    youtube_weight          REAL DEFAULT 0.20,
    reddit_weight           REAL DEFAULT 0.10,
    twitch_weight           REAL DEFAULT 0.25,
    -- Final score (0-100)
    mindshare_score         REAL,
    created_at              TEXT DEFAULT (datetime('now')),
    UNIQUE(game_id, snapshot_date)
);

-- ============================================
-- Seed: initial games to track
-- ============================================
INSERT OR IGNORE INTO games (name, steam_app_id, genre, publisher, business_model, platform) VALUES
    ('Minecraft', 1672970, 'Sandbox', 'Mojang', 'Premium', 'Cross-platform'),
    ('Counter-Strike 2', 730, 'FPS', 'Valve', 'F2P', 'PC'),
    ('Dota 2', 570, 'MOBA', 'Valve', 'F2P', 'PC'),
    ('Fortnite', NULL, 'Battle Royale', 'Epic Games', 'F2P', 'Cross-platform'),
    ('Apex Legends', 1172470, 'Battle Royale', 'EA', 'F2P', 'Cross-platform'),
    ('League of Legends', NULL, 'MOBA', 'Riot Games', 'F2P', 'PC'),
    ('Valorant', NULL, 'FPS', 'Riot Games', 'F2P', 'PC'),
    ('PUBG', 578080, 'Battle Royale', 'Krafton', 'Premium', 'Cross-platform'),
    ('Elden Ring', 1245620, 'Action RPG', 'Bandai Namco', 'Premium', 'Cross-platform'),
    ('Baldur''s Gate 3', 1086940, 'RPG', 'Larian Studios', 'Premium', 'Cross-platform'),
    ('Cyberpunk 2077', 1091500, 'Action RPG', 'CD Projekt Red', 'Premium', 'Cross-platform'),
    ('Helldivers 2', 553850, 'Co-op Shooter', 'Sony', 'Premium', 'Cross-platform'),
    ('Path of Exile 2', 2694490, 'ARPG', 'Grinding Gear Games', 'F2P', 'Cross-platform'),
    ('Palworld', 1623730, 'Survival', 'Pocketpair', 'Premium', 'Cross-platform'),
    ('GTA V', 271590, 'Open World', 'Rockstar', 'Premium', 'Cross-platform'),
    ('Rust', 252490, 'Survival', 'Facepunch Studios', 'Premium', 'PC'),
    ('Stardew Valley', 413150, 'Farming Sim', 'ConcernedApe', 'Premium', 'Cross-platform'),
    ('Dead by Daylight', 381210, 'Horror', 'Behaviour Interactive', 'Premium', 'Cross-platform'),
    ('Warframe', 230410, 'Action', 'Digital Extremes', 'F2P', 'Cross-platform'),
    ('World of Warcraft', NULL, 'MMORPG', 'Blizzard', 'Subscription', 'PC'),
    ('Overwatch 2', NULL, 'FPS', 'Blizzard', 'F2P', 'Cross-platform'),
    ('Call of Duty: Warzone', NULL, 'Battle Royale', 'Activision', 'F2P', 'Cross-platform'),
    ('Rainbow Six Siege', 359550, 'FPS', 'Ubisoft', 'Premium', 'Cross-platform'),
    ('Escape from Tarkov', NULL, 'FPS', 'Battlestate Games', 'Premium', 'PC'),
    ('Diablo IV', NULL, 'Action RPG', 'Blizzard', 'Premium', 'Cross-platform'),
    ('Dark Souls III', 374320, 'Action RPG', 'Bandai Namco', 'Premium', 'Cross-platform'),
    ('Monster Hunter: World', 582010, 'Action RPG', 'Capcom', 'Premium', 'Cross-platform'),
    ('Monster Hunter Wilds', 2246340, 'Action RPG', 'Capcom', 'Premium', 'Cross-platform'),
    ('ARK: Survival Evolved', 346110, 'Survival', 'Studio Wildcard', 'Premium', 'Cross-platform'),
    ('Valheim', 892970, 'Survival', 'Coffee Stain', 'Premium', 'PC'),
    ('7 Days to Die', 251570, 'Survival', 'The Fun Pimps', 'Premium', 'Cross-platform'),
    ('Final Fantasy XIV', 39210, 'MMORPG', 'Square Enix', 'Subscription', 'Cross-platform'),
    ('Lost Ark', 1599340, 'MMORPG', 'Smilegate', 'F2P', 'PC'),
    ('Rocket League', 252950, 'Sports', 'Psyonix', 'F2P', 'Cross-platform'),
    ('EA FC 25', NULL, 'Sports', 'EA', 'Premium', 'Cross-platform'),
    ('Civilization VI', 289070, 'Strategy', '2K Games', 'Premium', 'PC'),
    ('Total War: Warhammer III', 1142710, 'Strategy', 'Sega', 'Premium', 'PC'),
    ('Fall Guys', 1097150, 'Battle Royale', 'Mediatonic', 'F2P', 'Cross-platform');
