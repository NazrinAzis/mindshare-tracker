# mindSHARE Tracker

A data pipeline and dashboard that measures **how much attention a video game is getting right now**. It pulls signals from six platforms and combines them into one 0–100 **mindSHARE score**, so released and upcoming games can be compared on equal footing.

## How the score works

Each signal is min-max normalized to 0–1 across all tracked games for the snapshot date. The signals are then weighted and scaled to 0–100.

| Signal | Released games | Upcoming games |
| --- | --- | --- |
| Google Trends | 0.27 | 0.315 |
| Twitch viewers | 0.225 | 0.135 |
| YouTube views | 0.18 | 0.225 |
| Steam owners | 0.135 | — |
| Reddit | 0.09 (score) | 0.225 (posts) |
| TikTok views | 0.10 | 0.10 |

Upcoming games have no Steam data, so their weight moves to search and community buzz.

## Data sources

- **Steam**: owner estimates
- **Google Trends**: search interest, via `pytrends`
- **YouTube**: video views, via the YouTube Data API
- **Reddit**: post volume and engagement
- **Twitch**: live viewers
- **TikTok**: video views

## Getting started

```bash
pip install -r requirements.txt
```

Create a `.env` file:

| Variable | Purpose |
| --- | --- |
| `YOUTUBE_API_KEY` | YouTube Data API v3 |
| `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` | Twitch API |
| `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` | TikTok API |

Run the pipeline, then start the dashboard:

```bash
python run_pipeline.py        # fetch all sources and compute scores
python dashboard.py           # open http://localhost:8080
```

You can also run single steps: `--steam`, `--google`, `--youtube`, `--reddit`, `--twitch`, `--tiktok`, or `--score` to recompute scores without fetching.

## Project structure

```
fetch_*.py            One fetcher per platform
compute_mindshare.py  Normalization and weighted scoring
run_pipeline.py       Runs the full pipeline in order
dashboard.py          Single-page web dashboard
db.py / schema.sql    SQLite storage (mindshare.db)
```

## Tech stack

Python · SQLite · Google Trends (pytrends) · YouTube Data API · Twitch API · TikTok API · deployable on any Procfile host (Railway / Heroku)

## Author

Built by [Nazrin Qayyum Azis](https://www.linkedin.com/in/nazrinqayyum), a product manager in Amsterdam who works on gaming and data products.
