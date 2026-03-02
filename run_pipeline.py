"""
run_pipeline.py — Runs the full data ingestion pipeline in sequence

Usage:
    python run_pipeline.py              # Run all steps
    python run_pipeline.py --steam      # Steam only
    python run_pipeline.py --google     # Google Trends only
    python run_pipeline.py --youtube    # YouTube only
    python run_pipeline.py --score      # Compute scores only (no fetching)
"""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="mindSHARE data pipeline")
    parser.add_argument("--steam", action="store_true", help="Fetch Steam data only")
    parser.add_argument("--google", action="store_true", help="Fetch Google Trends only")
    parser.add_argument("--youtube", action="store_true", help="Fetch YouTube data only")
    parser.add_argument("--score", action="store_true", help="Compute mindSHARE scores only")
    args = parser.parse_args()

    run_all = not any([args.steam, args.google, args.youtube, args.score])

    # Always initialize DB first
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

    if run_all or args.score:
        print("\n" + "="*50)
        print("STEP 4: Compute mindSHARE scores")
        print("="*50)
        import compute_mindshare
        compute_mindshare.run()

    print("\n🎉 Pipeline complete!")


if __name__ == "__main__":
    main()
