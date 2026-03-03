"""
run_pipeline.py — Runs the full data ingestion pipeline in sequence

Usage:
    python run_pipeline.py              # Run all steps
    python run_pipeline.py --steam      # Steam only
    python run_pipeline.py --google     # Google Trends only
    python run_pipeline.py --youtube    # YouTube only
    python run_pipeline.py --reddit     # Reddit only
    python run_pipeline.py --twitch     # Twitch only
    python run_pipeline.py --tiktok     # TikTok only
    python run_pipeline.py --score      # Compute scores only (no fetching)
"""

import argparse


def main():
    parser = argparse.ArgumentParser(description="mindSHARE data pipeline")
    parser.add_argument("--steam",   action="store_true", help="Fetch Steam data only")
    parser.add_argument("--google",  action="store_true", help="Fetch Google Trends only")
    parser.add_argument("--youtube", action="store_true", help="Fetch YouTube data only")
    parser.add_argument("--reddit",  action="store_true", help="Fetch Reddit data only")
    parser.add_argument("--twitch",  action="store_true", help="Fetch Twitch data only")
    parser.add_argument("--tiktok",  action="store_true", help="Fetch TikTok data only")
    parser.add_argument("--score",   action="store_true", help="Compute mindSHARE scores only")
    args = parser.parse_args()

    run_all = not any([args.steam, args.google, args.youtube, args.reddit, args.twitch, args.tiktok, args.score])

    from db import init_db
    init_db()

    if run_all or args.steam:
        print("\n" + "="*50)
        print("STEP 1: Steam (SteamSpy)")
        print("="*50)
        import fetch_steam
        fetch_steam.run()

    if run_all or args.google:
        print("\n" + "="*50)
        print("STEP 2: Google Trends")
        print("="*50)
        import fetch_google
        fetch_google.run()

    if run_all or args.youtube:
        print("\n" + "="*50)
        print("STEP 3: YouTube")
        print("="*50)
        import fetch_youtube
        fetch_youtube.run()

    if run_all or args.reddit:
        print("\n" + "="*50)
        print("STEP 4: Reddit")
        print("="*50)
        import fetch_reddit
        fetch_reddit.run()

    if run_all or args.twitch:
        print("\n" + "="*50)
        print("STEP 5: Twitch")
        print("="*50)
        import fetch_twitch
        fetch_twitch.run()

    if run_all or args.tiktok:
        print("\n" + "="*50)
        print("STEP 6: TikTok")
        print("="*50)
        import fetch_tiktok
        fetch_tiktok.run()

    if run_all or args.score:
        print("\n" + "="*50)
        print("STEP 7: Compute mindSHARE scores")
        print("="*50)
        import compute_mindshare
        compute_mindshare.run()

    print("\n🎉 Pipeline complete!")


if __name__ == "__main__":
    main()
