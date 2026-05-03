"""
Extraction FBref via soccerdata.
Refactorisé depuis DataBaseHome.ipynb.
Usage : python -m data.scraper --season 2526
"""
from __future__ import annotations

import time
from pathlib import Path

from config import DATA_DIR, SEASONS, TEAM_SEASON_STATS, PLAYER_SEASON_STATS, \
    TEAM_MATCH_STATS, PLAYER_MATCH_STATS


def scrape_season(season_key: str, sleep: float = 2.0) -> None:
    """
    Télécharge toutes les stats FBref pour une saison et les sauvegarde en CSV.
    season_key : clé dans SEASONS (ex: '2526')
    """
    try:
        import soccerdata as sd
    except ImportError:
        raise ImportError("pip install soccerdata")

    out_dir = DATA_DIR / season_key
    out_dir.mkdir(exist_ok=True)

    fbref = sd.FBref(leagues="Big 5 European Leagues Combined", seasons=season_key)

    # Team season stats
    for stat_type in TEAM_SEASON_STATS:
        path = out_dir / f"FB_team_season_stats_{stat_type}.csv"
        if path.exists():
            print(f"  [skip] {path.name}")
            continue
        try:
            df = fbref.read_team_season_stats(stat_type=stat_type)
            df.to_csv(path)
            print(f"  [ok]   {path.name}")
        except Exception as e:
            print(f"  [err]  {path.name}: {e}")
        time.sleep(sleep)

    # Team match stats
    for stat_type in TEAM_MATCH_STATS:
        path = out_dir / f"FB_team_match_stats_{stat_type}.csv"
        if path.exists():
            print(f"  [skip] {path.name}")
            continue
        try:
            df = fbref.read_team_match_stats(stat_type=stat_type)
            df.to_csv(path)
            print(f"  [ok]   {path.name}")
        except Exception as e:
            print(f"  [err]  {path.name}: {e}")
        time.sleep(sleep)

    # Player season stats
    for stat_type in PLAYER_SEASON_STATS:
        path = out_dir / f"FB_player_season_stats_{stat_type}.csv"
        if path.exists():
            print(f"  [skip] {path.name}")
            continue
        try:
            df = fbref.read_player_season_stats(stat_type=stat_type)
            df.to_csv(path)
            print(f"  [ok]   {path.name}")
        except Exception as e:
            print(f"  [err]  {path.name}: {e}")
        time.sleep(sleep)

    # Player match stats
    for stat_type in PLAYER_MATCH_STATS:
        path = out_dir / f"FB_player_match_stats_{stat_type}.csv"
        if path.exists():
            print(f"  [skip] {path.name}")
            continue
        try:
            df = fbref.read_player_match_stats(stat_type=stat_type)
            df.to_csv(path)
            print(f"  [ok]   {path.name}")
        except Exception as e:
            print(f"  [err]  {path.name}: {e}")
        time.sleep(sleep)

    # Schedule, lineups, events
    for name, reader in [
        ("FB_schedule",    fbref.read_schedule),
        ("FB_lineups",     fbref.read_lineups),
        ("FB_events",      fbref.read_events),
        ("FB_shot_events", fbref.read_shot_events),
    ]:
        path = out_dir / f"{name}.csv"
        if path.exists():
            print(f"  [skip] {path.name}")
            continue
        try:
            df = reader()
            df.to_csv(path, index=False)
            print(f"  [ok]   {path.name}")
        except Exception as e:
            print(f"  [err]  {path.name}: {e}")
        time.sleep(sleep)

    print(f"\nSaison {season_key} terminée → {out_dir}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", required=True, choices=list(SEASONS.keys()))
    parser.add_argument("--sleep", type=float, default=2.0)
    args = parser.parse_args()
    scrape_season(args.season, args.sleep)
