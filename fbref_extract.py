"""
fbref_extract.py
Extraction des stats FBref (Big 5) pour toutes les saisons.
Lancement : python fbref_extract.py [--phase {1,2,all}]
  --phase 1   : stats saison uniquement (rapide)
  --phase 2   : stats match uniquement  (long)
  --phase all : phases 1 + 2            (défaut)
"""

import argparse
import logging
import random
import sys
import time
from pathlib import Path

import soccerdata as sd

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("fbref_extract.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────
SEASONS = ['2021', '2022', '2023', '2024', '2025']

LEAGUES_COMBINED = 'Big 5 European Leagues Combined'
LEAGUES_PER_COUNTRY = [
    'ENG-Premier League',
    'ESP-La Liga',
    'GER-Bundesliga',
    'ITA-Serie A',
    'FRA-Ligue 1',
]

# True = ré-écrase les CSVs existants. False = saute ce qui est déjà là.
FORCE = False

# Politesse FBref + paramètres retry
SLEEP_BASE = 3      # secondes entre requêtes (jitter ajouté)
MAX_RETRIES = 4     # tentatives par appel
BACKOFF_BASE = 30   # délai initial en secondes (×2, ×4, …)

STAT_TYPES_TEAM_SEASON = [
    'standard', 'keeper', 'keeper_adv', 'shooting', 'passing', 'passing_types',
    'goal_shot_creation', 'defense', 'possession', 'playing_time', 'misc',
]
STAT_TYPES_TEAM_MATCH = [
    'schedule', 'keeper', 'shooting', 'passing', 'passing_types',
    'goal_shot_creation', 'defense', 'possession', 'misc',
]
STAT_TYPES_PLAYER_SEASON = [
    'standard', 'shooting', 'passing', 'passing_types',
    'goal_shot_creation', 'defense', 'possession', 'playing_time', 'misc',
    'keeper', 'keeper_adv',
]
STAT_TYPES_PLAYER_MATCH = [
    'summary', 'keepers', 'passing', 'passing_types', 'defense', 'possession', 'misc',
]

BASE_DIR = Path.cwd() / "data"


# ── Helpers ────────────────────────────────────────────────────────────────
def season_folder(season: str) -> str:
    """FBref season '2024' → folder '2425'."""
    yy = int(season) % 100
    return f"{yy:02d}{(yy + 1) % 100:02d}"


def polite_sleep():
    """Pause + jitter pour éviter de marteler FBref."""
    time.sleep(SLEEP_BASE + random.uniform(0, 1.5))


def with_retry(fn, label: str):
    """Exécute fn() avec retry exponentiel. Lève la dernière exception."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            msg = str(e)
            if 'should be in' in msg or 'Invalid argument' in msg or 'has no attribute' in msg:
                raise
            if attempt == MAX_RETRIES:
                raise
            wait = BACKOFF_BASE * (2 ** (attempt - 1))
            log.warning(f"↻ {label}: tentative {attempt}/{MAX_RETRIES} — {msg[:120]} — pause {wait}s")
            time.sleep(wait)


def safe_save(df, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=True)
    log.info(f"✓ {path.name}  ({len(df)} lignes)")


def fetch_one(label: str, path: Path, fn) -> bool:
    """Récupère un dataset, l'écrit, retourne True si OK."""
    if path.exists() and not FORCE:
        log.info(f"· {path.name}  (déjà présent — skip)")
        return True
    try:
        polite_sleep()
        df = with_retry(fn, label)
        safe_save(df, path)
        return True
    except KeyboardInterrupt:
        raise
    except Exception as e:
        log.error(f"✗ {label}: {str(e)[:200]}")
        return False


# ── Extraction ─────────────────────────────────────────────────────────────
def fetch_for_season(season: str, include_match_level: bool = True) -> None:
    folder = BASE_DIR / season_folder(season)
    folder.mkdir(parents=True, exist_ok=True)
    log.info(f"=== Saison {season} → {folder.name}/ ===")

    fb_combined    = sd.FBref(leagues=LEAGUES_COMBINED,    seasons=season)
    fb_per_country = sd.FBref(leagues=LEAGUES_PER_COUNTRY, seasons=season)

    # 1) Stats équipe — saison
    for stat in STAT_TYPES_TEAM_SEASON:
        fetch_one(
            f'team_season_{stat}',
            folder / f'FB_team_season_stats_{stat}.csv',
            lambda s=stat: fb_combined.read_team_season_stats(stat_type=s),
        )

    # 2) Stats joueur — saison
    for stat in STAT_TYPES_PLAYER_SEASON:
        fetch_one(
            f'player_season_{stat}',
            folder / f'FB_player_season_stats_{stat}.csv',
            lambda s=stat: fb_combined.read_player_season_stats(stat_type=s),
        )

    if not include_match_level:
        return

    # 3) Calendrier + tirs
    fetch_one('schedule',    folder / 'FB_schedule.csv',    fb_per_country.read_schedule)
    fetch_one('shot_events', folder / 'FB_shot_events.csv', fb_per_country.read_shot_events)

    # 4) Stats par match (très long)
    for stat in STAT_TYPES_TEAM_MATCH:
        fetch_one(
            f'team_match_{stat}',
            folder / f'FB_team_match_stats_{stat}.csv',
            lambda s=stat: fb_per_country.read_team_match_stats(stat_type=s),
        )
    for stat in STAT_TYPES_PLAYER_MATCH:
        fetch_one(
            f'player_match_{stat}',
            folder / f'FB_player_match_stats_{stat}.csv',
            lambda s=stat: fb_per_country.read_player_match_stats(stat_type=s),
        )

    # 5) Lineups + events
    for name, fn in [
        ('lineups', fb_per_country.read_lineup),
        ('events',  fb_per_country.read_events),
    ]:
        fetch_one(name, folder / f'FB_{name}.csv', fn)


# ── Point d'entrée ─────────────────────────────────────────────────────────
def main():
    # Vérification version soccerdata
    assert sd.__version__.startswith('1.8'), (
        f"soccerdata {sd.__version__} détecté — installer 1.8.8 : "
        'pip install "soccerdata==1.8.8"'
    )

    parser = argparse.ArgumentParser(description="Extraction FBref Big 5")
    parser.add_argument(
        '--phase',
        choices=['1', '2', 'all'],
        default='all',
        help="1=saison seulement, 2=match seulement, all=tout (défaut: all)",
    )
    args = parser.parse_args()

    BASE_DIR.mkdir(parents=True, exist_ok=True)
    log.info(f"Démarrage extraction — phase={args.phase} — saisons={SEASONS}")

    if args.phase in ('1', 'all'):
        log.info("── Phase 1 : stats saison ──")
        for season in SEASONS:
            fetch_for_season(season, include_match_level=False)
        log.info("✅ Phase 1 terminée.")

    if args.phase in ('2', 'all'):
        log.info("── Phase 2 : stats par match ──")
        for season in SEASONS:
            fetch_for_season(season, include_match_level=True)
        log.info("✅ Extraction complète terminée.")


if __name__ == "__main__":
    main()
