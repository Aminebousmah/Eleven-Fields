"""
Extraction FBref saison 2025-26 (cle : 2526).
Script autonome -- peut tourner en arriere-plan.

Lancement :
    .venv/Scripts/python.exe scrape_2526.py

Reprendre apres une coupure : relancer simplement le script.
Les fichiers deja telecharges sont ignores (SKIP).
"""
from __future__ import annotations

import io
import sys
import time
import random
import logging
import traceback
from datetime import datetime
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────

SEASON    = "2526"
OUT_DIR   = Path(__file__).parent / SEASON
LOG_FILE  = Path(__file__).parent / "scrape_2526.log"

# Stats saison : 1 requete par stat_type via vue Combined -> peu de trafic
SLEEP_OK_MIN   = 5.0
SLEEP_OK_MAX   = 10.0

# Match stats : ligue par ligue -> beaucoup plus de requetes -> pauses longues
SLEEP_MATCH_MIN = 15.0
SLEEP_MATCH_MAX = 30.0

# Entre deux stat_types complets (toutes ligues finies) : pause supplementaire
SLEEP_BETWEEN_STATS = 20.0

SLEEP_ERR      = 30.0   # apres une erreur
MAX_RETRIES    = 3

TEAM_SEASON_STATS = [
    "standard", "keeper", "keeper_adv", "shooting", "passing",
    "passing_types", "goal_shot_creation", "defense", "possession",
    "playing_time", "misc",
]
PLAYER_SEASON_STATS = [
    "standard", "shooting", "passing", "passing_types", "goal_shot_creation",
    "defense", "possession", "playing_time", "misc", "keeper", "keeper_adv",
]
TEAM_MATCH_STATS = [
    "schedule", "keeper", "shooting", "passing", "passing_types",
    "goal_shot_creation", "defense", "possession", "misc",
]
PLAYER_MATCH_STATS = [
    "summary", "keepers", "passing", "passing_types", "defense", "possession", "misc",
]
BIG5_LEAGUES = [
    "ENG-Premier League",
    "ESP-La Liga",
    "GER-Bundesliga",
    "ITA-Serie A",
    "FRA-Ligue 1",
]

# ── Logging ────────────────────────────────────────────────────────────────────
# stdout force en UTF-8 pour eviter les erreurs cp1252 sur Windows

fmt = logging.Formatter(
    fmt="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

_stdout_utf8 = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
console_handler = logging.StreamHandler(_stdout_utf8)
console_handler.setFormatter(fmt)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(fmt)

logging.root.setLevel(logging.INFO)
logging.root.handlers = [console_handler, file_handler]
log = logging.getLogger("scrape_2526")

# Reduire le bruit des loggers externes
for noisy in ("soccerdata", "urllib3", "requests", "httpx"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sep(title: str) -> None:
    log.info("")
    log.info("--- %s %s", title, "-" * max(0, 50 - len(title)))


def _sleep(seconds: float, reason: str = "") -> None:
    if reason:
        log.info("    pause %.0fs (%s)", seconds, reason)
    time.sleep(seconds)


def _sleep_rand(min_s: float, max_s: float, reason: str = "") -> None:
    """Pause aleatoire pour eviter la detection bot."""
    s = random.uniform(min_s, max_s)
    if reason:
        log.info("    pause %.1fs (%s)", s, reason)
    time.sleep(s)


def _save(df, path: Path, index: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=index)


def _fetch(fn, path: Path, label: str, index: bool = True) -> str:
    """
    Appelle fn(), sauvegarde dans path.
    Retourne 'skip', 'ok' ou 'err'.
    """
    if path.exists():
        log.info("  SKIP  %s", path.name)
        return "skip"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = fn()
            if df is None or df.empty:
                log.warning("  VIDE  %s (tentative %d/%d)", label, attempt, MAX_RETRIES)
                _sleep(SLEEP_ERR)
                continue
            _save(df, path, index=index)
            log.info("  OK    %s  (%d lignes)", path.name, len(df))
            return "ok"
        except Exception as exc:
            log.warning("  ERR   %s — tentative %d/%d : %s", label, attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                _sleep(SLEEP_ERR * attempt, "retry")
            else:
                log.error("  ECHEC %s apres %d tentatives", label, MAX_RETRIES)
                log.debug(traceback.format_exc())
    return "err"


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        import soccerdata as sd
        import pandas as pd
    except ImportError as e:
        print(f"Dependance manquante : {e}")
        sys.exit(1)

    log.info("=" * 60)
    log.info("Extraction FBref — saison %s", SEASON)
    log.info("Dossier : %s", OUT_DIR)
    log.info("=" * 60)

    start = datetime.now()
    counts = {"ok": 0, "skip": 0, "err": 0}

    def _count(result: str) -> None:
        counts[result] = counts.get(result, 0) + 1

    # ── 1. Stats saison equipe ────────────────────────────────────────────────
    _sep("Stats saison EQUIPE (Big5 Combined)")
    fbref = sd.FBref(leagues="Big 5 European Leagues Combined", seasons=SEASON)

    for stat in TEAM_SEASON_STATS:
        path = OUT_DIR / f"FB_team_season_stats_{stat}.csv"
        _count(_fetch(
            lambda s=stat: fbref.read_team_season_stats(stat_type=s),
            path, f"team_season/{stat}",
        ))
        _sleep_rand(SLEEP_OK_MIN, SLEEP_OK_MAX)

    # ── 2. Stats saison joueur ────────────────────────────────────────────────
    _sep("Stats saison JOUEUR (Big5 Combined)")
    for stat in PLAYER_SEASON_STATS:
        path = OUT_DIR / f"FB_player_season_stats_{stat}.csv"
        _count(_fetch(
            lambda s=stat: fbref.read_player_season_stats(stat_type=s),
            path, f"player_season/{stat}",
        ))
        _sleep_rand(SLEEP_OK_MIN, SLEEP_OK_MAX)

    # ── 3. Schedule ───────────────────────────────────────────────────────────
    _sep("Schedule (Big5 Combined)")
    _count(_fetch(
        lambda: fbref.read_schedule(),
        OUT_DIR / "FB_schedule.csv",
        "schedule", index=False,
    ))
    _sleep_rand(SLEEP_OK_MIN, SLEEP_OK_MAX)

    # ── 4. Stats match equipe (ligue par ligue) ───────────────────────────────
    _sep("Stats match EQUIPE (ligue par ligue)")
    _first_match_stat = True
    for stat in TEAM_MATCH_STATS:
        path = OUT_DIR / f"FB_team_match_stats_{stat}.csv"
        if path.exists():
            log.info("  SKIP  %s", path.name)
            counts["skip"] += 1
            continue
        if _first_match_stat:
            log.info("  Premiere requete match stats -- pause initiale 60s")
            time.sleep(60)
            _first_match_stat = False
        frames = []
        for league in BIG5_LEAGUES:
            try:
                df = sd.FBref(leagues=league, seasons=SEASON).read_team_match_stats(stat_type=stat)
                if df is not None and not df.empty:
                    frames.append(df)
                    log.info("  OK    %s / %s  (%d lignes)", stat, league, len(df))
                else:
                    log.warning("  VIDE  %s / %s", stat, league)
            except Exception as exc:
                log.warning("  ERR   %s / %s : %s", stat, league, exc)
                _sleep(SLEEP_ERR, "backoff apres erreur")
            _sleep_rand(SLEEP_MATCH_MIN, SLEEP_MATCH_MAX)
        if frames:
            combined = pd.concat(frames, ignore_index=True)
            _save(combined, path)
            log.info("  SAVED %s  (%d lignes)", path.name, len(combined))
            counts["ok"] += 1
        else:
            log.error("  ECHEC %s", path.name)
            counts["err"] += 1
        # pause entre deux stat_types
        _sleep(SLEEP_BETWEEN_STATS, "pause inter-stats")

    # ── 5. Stats match joueur (ligue par ligue) ───────────────────────────────
    _sep("Stats match JOUEUR (ligue par ligue)")
    for stat in PLAYER_MATCH_STATS:
        path = OUT_DIR / f"FB_player_match_stats_{stat}.csv"
        if path.exists():
            log.info("  SKIP  %s", path.name)
            counts["skip"] += 1
            continue
        frames = []
        for league in BIG5_LEAGUES:
            try:
                df = sd.FBref(leagues=league, seasons=SEASON).read_player_match_stats(stat_type=stat)
                if df is not None and not df.empty:
                    frames.append(df)
                    log.info("  OK    %s / %s  (%d lignes)", stat, league, len(df))
                else:
                    log.warning("  VIDE  %s / %s", stat, league)
            except Exception as exc:
                log.warning("  ERR   %s / %s : %s", stat, league, exc)
                _sleep(SLEEP_ERR, "backoff apres erreur")
            _sleep_rand(SLEEP_MATCH_MIN, SLEEP_MATCH_MAX)
        if frames:
            combined = pd.concat(frames, ignore_index=True)
            _save(combined, path)
            log.info("  SAVED %s  (%d lignes)", path.name, len(combined))
            counts["ok"] += 1
        else:
            log.error("  ECHEC %s", path.name)
            counts["err"] += 1
        # pause entre deux stat_types
        _sleep(SLEEP_BETWEEN_STATS, "pause inter-stats")

    # ── 6. Lineups / Events / Shot events (ligue par ligue) ───────────────────
    _sep("Lineups / Events / Shot events (ligue par ligue)")
    flat_tasks = [
        ("FB_lineups.csv",     "read_lineups"),
        ("FB_events.csv",      "read_events"),
        ("FB_shot_events.csv", "read_shot_events"),
    ]
    for fname, method in flat_tasks:
        path = OUT_DIR / fname
        if path.exists():
            log.info("  SKIP  %s", fname)
            counts["skip"] += 1
            continue
        frames = []
        for league in BIG5_LEAGUES:
            try:
                df = getattr(sd.FBref(leagues=league, seasons=SEASON), method)()
                if df is not None and not df.empty:
                    frames.append(df)
                    log.info("  OK    %s / %s  (%d lignes)", fname, league, len(df))
                else:
                    log.warning("  VIDE  %s / %s", fname, league)
            except Exception as exc:
                log.warning("  ERR   %s / %s : %s", fname, league, exc)
                _sleep(SLEEP_ERR, "backoff apres erreur")
            _sleep_rand(SLEEP_MATCH_MIN, SLEEP_MATCH_MAX)
        if frames:
            combined = pd.concat(frames, ignore_index=True)
            _save(combined, path, index=False)
            log.info("  SAVED %s  (%d lignes)", path.name, len(combined))
            counts["ok"] += 1
        else:
            log.error("  ECHEC %s", path.name)
            counts["err"] += 1
        _sleep(SLEEP_BETWEEN_STATS, "pause inter-stats")

    # ── Resume ────────────────────────────────────────────────────────────────
    elapsed = str(datetime.now() - start).split(".")[0]
    log.info("")
    log.info("=" * 60)
    log.info("Termine en %s", elapsed)
    log.info("  OK      : %d", counts["ok"])
    log.info("  SKIP    : %d  (deja presents)", counts["skip"])
    log.info("  ECHECS  : %d", counts["err"])
    log.info("Log : %s", LOG_FILE)
    log.info("=" * 60)

    if counts["err"]:
        log.warning("%d echec(s) — relancez le script pour reessayer.", counts["err"])
        sys.exit(1)


if __name__ == "__main__":
    main()
