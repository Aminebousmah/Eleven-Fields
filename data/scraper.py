"""
ElevenField — Extracteur FBref multi-saisons (mode robuste).

Bonnes pratiques scraping :
  - Pause longue par défaut (15 s ± 40 % jitter)
  - Pauses additionnelles entre catégories (30 s) et saisons (60 s)
  - Cooldown 90 s après chaque erreur
  - Slow-down adaptatif : sleep × 1.5 par erreur (max 60 s)
  - Pre-flight check FBref (détecte un ban avant de lancer)
  - Abort propre après 3 erreurs consécutives (= ban probable)
  - Logging dual : console + fichier horodaté
  - Sauvegarde .bak avant overwrite (--force)
  - Validation post-save (sanity check du CSV)
  - Ctrl+C → résumé partiel sauvegardé, fichiers protégés
  - JSON de session à la fin (traçabilité)

Stratégie de requêtes :
  - Stats saison équipe/joueur : vue Big 5 Combined (1 req au lieu de 5)
  - Stats match équipe/joueur  : 5 ligues séparées
  - Fichiers plats             : schedule, shot_events, lineups, events

Usage :
  python -m data.scraper                                # 3 dernières saisons
  python -m data.scraper --seasons 2526 --force         # refresh saison en cours
  python -m data.scraper --dry-run                      # liste les manquants
  python -m data.scraper --seasons 2425 --sleep 20      # encore plus prudent
  python -m data.scraper --proxy socks5h://127.0.0.1:9150
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    _ALL_SEASONS, DATA_DIR, LEAGUES,
    TEAM_SEASON_STATS, PLAYER_SEASON_STATS,
    TEAM_MATCH_STATS, PLAYER_MATCH_STATS,
)

# ── Constantes mode robuste ───────────────────────────────────────────────────

DEFAULT_SLEEP            = 15.0
SLEEP_BETWEEN_CATEGORIES = 30.0
SLEEP_BETWEEN_SEASONS    = 60.0
SLEEP_AFTER_ERROR        = 90.0
MAX_CONSECUTIVE_ERRORS   = 3
SLOWDOWN_FACTOR          = 1.5     # base_sleep × 1.5 par erreur
MAX_SLEEP                = 60.0    # plafond du slow-down adaptatif
MIN_CSV_BYTES            = 200     # un CSV plus petit que ça est suspect

# Fichiers plats
_FLAT_FILES: list[tuple[str, str]] = [
    ("FB_schedule",    "read_schedule"),
    ("FB_shot_events", "read_shot_events"),
    ("FB_lineups",     "read_lineups"),
    ("FB_events",      "read_events"),
]

_LAST3: list[str] = list(_ALL_SEASONS.keys())[-3:]
_LOG_DIR = Path(__file__).parent.parent / "logs"


# ── Exceptions ────────────────────────────────────────────────────────────────

class FBrefBannedError(RuntimeError):
    """Levée quand FBref nous bannit (403/429 répétés)."""


# ── Logging ───────────────────────────────────────────────────────────────────

def _setup_logging() -> tuple[logging.Logger, Path]:
    """Init logger avec sortie console + fichier horodaté dans logs/."""
    _LOG_DIR.mkdir(exist_ok=True)
    log_path = _LOG_DIR / f"scraper_{datetime.now():%Y%m%d_%H%M%S}.log"

    logger = logging.getLogger("scraper")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s",
                            datefmt="%H:%M:%S")

    # Console : niveau INFO, format compact
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(message)s"))
    console.setLevel(logging.INFO)
    logger.addHandler(console)

    # Fichier : tout, format détaillé
    fhandler = logging.FileHandler(log_path, encoding="utf-8")
    fhandler.setFormatter(fmt)
    fhandler.setLevel(logging.DEBUG)
    logger.addHandler(fhandler)

    # Silence les libs verbeuses
    for noisy in ("soccerdata", "urllib3", "requests", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logger, log_path


# ── État partagé (mutation in-place pour propager dans les fonctions) ─────────

class State:
    """État de la session, mis à jour au fil des extractions."""
    def __init__(self, base_sleep: float):
        self.base_sleep         = base_sleep
        self.original_sleep     = base_sleep
        self.consecutive_errors = 0
        self.total_errors       = 0
        self.start_time         = time.monotonic()
        self.interrupted        = False
        self.per_season: dict[str, dict[str, int]] = {}


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _jitter_sleep(base: float, label: str = "") -> None:
    """Pause base ± 40 % avec affichage si > 10 s."""
    duration = base + random.uniform(-base * 0.2, base * 0.4)
    if base >= 10:
        log.info(f"      ⏸  pause {duration:.0f}s{(' — ' + label) if label else ''}")
    time.sleep(duration)


def _retry(fn, *args, retries: int = 3, base_sleep: float = 10.0, **kwargs):
    """Exécute fn avec backoff exponentiel."""
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if attempt == retries - 1:
                raise
            wait = base_sleep * (2 ** attempt) + random.uniform(0, 5)
            log.warning(f"      ↻ retry {attempt + 1}/{retries} dans {wait:.0f}s — {str(exc)[:80]}")
            time.sleep(wait)


def _backup_existing(path: Path) -> Path | None:
    """Renomme un fichier existant en .bak avant overwrite (safety net)."""
    if not path.exists():
        return None
    bak = path.with_suffix(path.suffix + ".bak")
    # Si un .bak existe déjà, ajouter un timestamp
    if bak.exists():
        bak = path.with_suffix(
            path.suffix + f".bak.{datetime.now():%Y%m%d_%H%M%S}"
        )
    path.rename(bak)
    log.debug(f"      📦 backup → {bak.name}")
    return bak


def _save(df, path: Path, flat: bool) -> None:
    """Sauvegarde le DataFrame puis valide le CSV."""
    if flat:
        df.to_csv(path, index=False)
    else:
        df.to_csv(path)
    _validate_csv(path, expected_min_rows=1)


def _validate_csv(path: Path, expected_min_rows: int = 1) -> None:
    """Sanity check : le CSV existe, n'est pas vide, a au moins 2 lignes."""
    if not path.exists():
        raise IOError(f"validation : fichier absent après save : {path.name}")
    size = path.stat().st_size
    if size < MIN_CSV_BYTES:
        raise IOError(f"validation : CSV suspect (taille {size} B) : {path.name}")
    # Compte rapide des lignes
    with open(path, "rb") as f:
        n_lines = sum(1 for _ in f)
    if n_lines < expected_min_rows + 1:  # +1 pour l'en-tête
        raise IOError(f"validation : seulement {n_lines} ligne(s) : {path.name}")


def _record_error_adaptive(state: State) -> None:
    """Augmente progressivement le sleep après chaque erreur."""
    state.total_errors += 1
    state.consecutive_errors += 1
    new_sleep = min(state.base_sleep * SLOWDOWN_FACTOR, MAX_SLEEP)
    if new_sleep != state.base_sleep:
        log.warning(f"      📉 slow-down : sleep {state.base_sleep:.0f}s → {new_sleep:.0f}s")
        state.base_sleep = new_sleep


def _record_success(state: State) -> None:
    state.consecutive_errors = 0


def _is_ban_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(c in msg for c in ("403", "429", "forbidden", "too many requests"))


# ── Pre-flight ────────────────────────────────────────────────────────────────

def _check_fbref_accessible(proxy: str | None = None) -> bool:
    try:
        import requests
    except ImportError:
        return True
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }
    proxies = {"http": proxy, "https": proxy} if proxy else None
    try:
        resp = requests.get(
            "https://fbref.com/en/", headers=headers,
            proxies=proxies, timeout=15,
        )
        return resp.status_code < 400
    except requests.RequestException:
        return False


# ── Extraction primitive ──────────────────────────────────────────────────────

def _extract(
    path: Path,
    reader_fn,
    *reader_args,
    force: bool,
    state: State,
    flat: bool = False,
    **reader_kwargs,
) -> str:
    """Retourne 'ok' / 'skip' / 'err:<msg>'."""
    if path.exists() and not force:
        return "skip"
    backup = _backup_existing(path) if force else None
    try:
        df = _retry(reader_fn, *reader_args, base_sleep=state.base_sleep, **reader_kwargs)
        if df is None or (hasattr(df, "empty") and df.empty):
            raise ValueError("dataframe vide")
        path.parent.mkdir(parents=True, exist_ok=True)
        _save(df, path, flat=flat)
        _jitter_sleep(state.base_sleep)
        # Succès → on peut supprimer le backup
        if backup and backup.exists():
            backup.unlink()
        return "ok"
    except Exception as exc:
        # Restore le backup si l'extraction a échoué
        if backup and backup.exists() and not path.exists():
            backup.rename(path)
            log.info(f"      ♻️  backup restauré → {path.name}")
        return f"err:{exc}"


def _log_and_track(
    name: str,
    status: str,
    counters: dict[str, int],
    state: State,
) -> None:
    """Log + maj compteurs. Lève FBrefBannedError si ban probable."""
    if status == "ok":
        counters["ok"] += 1
        _record_success(state)
        log.info(f"    [ok]   {name}")
    elif status == "skip":
        counters["skip"] += 1
        _record_success(state)
        log.info(f"    [skip] {name}")
    else:
        counters["err"] += 1
        _record_error_adaptive(state)
        msg = status[4:] if status.startswith("err:") else status
        log.error(f"    [ERR]  {name}: {msg[:140]}")

        if state.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            raise FBrefBannedError(
                f"{MAX_CONSECUTIVE_ERRORS} erreurs consécutives — "
                "FBref a probablement bloqué votre IP. "
                "Attendez 1 à 24 h avant de relancer."
            )

        log.warning(f"      ⏸  cooldown {SLEEP_AFTER_ERROR:.0f}s après erreur")
        time.sleep(SLEEP_AFTER_ERROR)


def _dry_run_line(path: Path, label: str) -> None:
    log.info(f"    {label:<32} {'✓ présent' if path.exists() else '— manquant'}")


# ── Extraction d'une saison ───────────────────────────────────────────────────

def scrape_season(
    season_key: str,
    force: bool,
    state: State,
    dry_run: bool,
    no_cache: bool,
) -> dict[str, int]:
    if not dry_run:
        try:
            import soccerdata as sd
        except ImportError:
            log.error("soccerdata non installé. Lancer : pip install soccerdata==1.8.8")
            sys.exit(1)

    season_label = _ALL_SEASONS.get(season_key, season_key)
    out_dir = DATA_DIR / season_key
    counters: dict[str, int] = {"ok": 0, "skip": 0, "err": 0}

    log.info(f"\n{'═' * 62}")
    log.info(f"  Saison {season_label}  ({season_key})")
    if no_cache:
        log.info("  ⓘ no_cache=True — refresh complet depuis FBref")
    log.info(f"{'═' * 62}")

    if not dry_run:
        fbref_season = sd.FBref(
            leagues="Big 5 European Leagues Combined",
            seasons=season_key, no_cache=no_cache,
        )
        fbref_match = sd.FBref(
            leagues=LEAGUES, seasons=season_key, no_cache=no_cache,
        )

    # ── 1. Stats équipe saison ───────────────────────────────────────────────
    log.info(f"\n  [1/5] Stats équipe saison  ({len(TEAM_SEASON_STATS)} types)")
    for stat_type in TEAM_SEASON_STATS:
        path = out_dir / f"FB_team_season_stats_{stat_type}.csv"
        if dry_run:
            _dry_run_line(path, f"team_season_{stat_type}"); continue
        status = _extract(
            path, fbref_season.read_team_season_stats,
            force=force, state=state, stat_type=stat_type,
        )
        _log_and_track(path.name, status, counters, state)

    if not dry_run:
        _jitter_sleep(SLEEP_BETWEEN_CATEGORIES, "inter-catégorie")

    # ── 2. Stats joueur saison ───────────────────────────────────────────────
    log.info(f"\n  [2/5] Stats joueur saison  ({len(PLAYER_SEASON_STATS)} types)")
    for stat_type in PLAYER_SEASON_STATS:
        path = out_dir / f"FB_player_season_stats_{stat_type}.csv"
        if dry_run:
            _dry_run_line(path, f"player_season_{stat_type}"); continue
        status = _extract(
            path, fbref_season.read_player_season_stats,
            force=force, state=state, stat_type=stat_type,
        )
        _log_and_track(path.name, status, counters, state)

    if not dry_run:
        _jitter_sleep(SLEEP_BETWEEN_CATEGORIES, "inter-catégorie")

    # ── 3. Stats équipe par match ────────────────────────────────────────────
    log.info(f"\n  [3/5] Stats équipe par match  ({len(TEAM_MATCH_STATS)} types)")
    for stat_type in TEAM_MATCH_STATS:
        path = out_dir / f"FB_team_match_stats_{stat_type}.csv"
        if dry_run:
            _dry_run_line(path, f"team_match_{stat_type}"); continue
        status = _extract(
            path, fbref_match.read_team_match_stats,
            force=force, state=state, stat_type=stat_type,
        )
        _log_and_track(path.name, status, counters, state)

    if not dry_run:
        _jitter_sleep(SLEEP_BETWEEN_CATEGORIES, "inter-catégorie")

    # ── 4. Stats joueur par match ────────────────────────────────────────────
    log.info(f"\n  [4/5] Stats joueur par match  ({len(PLAYER_MATCH_STATS)} types)")
    for stat_type in PLAYER_MATCH_STATS:
        path = out_dir / f"FB_player_match_stats_{stat_type}.csv"
        if dry_run:
            _dry_run_line(path, f"player_match_{stat_type}"); continue
        status = _extract(
            path, fbref_match.read_player_match_stats,
            force=force, state=state, stat_type=stat_type,
        )
        _log_and_track(path.name, status, counters, state)

    if not dry_run:
        _jitter_sleep(SLEEP_BETWEEN_CATEGORIES, "inter-catégorie")

    # ── 5. Fichiers plats ────────────────────────────────────────────────────
    log.info(f"\n  [5/5] Fichiers plats  ({len(_FLAT_FILES)} fichiers)")
    if not dry_run:
        flat_readers = {
            "read_schedule":    fbref_match.read_schedule,
            "read_shot_events": fbref_match.read_shot_events,
            "read_lineups":     fbref_match.read_lineups,
            "read_events":      fbref_match.read_events,
        }
    for name, method_name in _FLAT_FILES:
        path = out_dir / f"{name}.csv"
        if dry_run:
            _dry_run_line(path, name); continue
        status = _extract(
            path, flat_readers[method_name],
            force=force, state=state, flat=True,
        )
        _log_and_track(path.name, status, counters, state)

    return counters


# ── Ctrl+C ────────────────────────────────────────────────────────────────────

def _install_sigint_handler(state: State) -> None:
    def handler(signum, frame):
        if state.interrupted:
            log.warning("\nDeuxième Ctrl+C — abandon immédiat.")
            sys.exit(130)
        state.interrupted = True
        log.warning("\n\n⚠️  Ctrl+C reçu — fin propre après l'opération en cours…")
        log.warning("    (re-Ctrl+C pour abandonner immédiatement)")
    signal.signal(signal.SIGINT, handler)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    valid_keys = list(_ALL_SEASONS.keys())
    parser = argparse.ArgumentParser(
        prog="python -m data.scraper",
        description="Extracteur FBref multi-saisons (mode robuste) — ElevenField",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            "  python -m data.scraper\n"
            "  python -m data.scraper --seasons 2526 --force\n"
            "  python -m data.scraper --dry-run\n"
            "  python -m data.scraper --seasons 2425 --sleep 20\n"
            "  python -m data.scraper --proxy socks5h://127.0.0.1:9150\n"
        ),
    )
    parser.add_argument("--seasons", nargs="+", default=["last3"], metavar="SEASON",
                        help=f"Saisons {valid_keys}. Raccourcis : last3 (défaut), all.")
    parser.add_argument("--force", action="store_true",
                        help="Réextrait les fichiers existants (active --no-cache).")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP, metavar="SEC",
                        help=f"Pause de base entre requêtes (défaut : {DEFAULT_SLEEP:.0f} s).")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="Liste les fichiers manquants sans télécharger.")
    parser.add_argument("--proxy", default=None, metavar="URL",
                        help="Proxy : socks5h://127.0.0.1:9150 (Tor), http://...")
    parser.add_argument("--no-cache", action="store_true", dest="no_cache",
                        help="Bypasse le cache soccerdata (implicite avec --force).")
    parser.add_argument("--skip-ping", action="store_true", dest="skip_ping",
                        help="Ignore le pre-flight check FBref.")
    return parser.parse_args()


def _resolve_seasons(raw: list[str]) -> list[str]:
    valid = list(_ALL_SEASONS.keys())
    if raw == ["all"]:  return valid
    if raw == ["last3"]: return _LAST3
    resolved = []
    for s in raw:
        if s in valid:     resolved.append(s)
        elif s == "all":   resolved.extend(valid)
        elif s == "last3": resolved.extend(_LAST3)
        else: log.warning(f"[warn] Saison inconnue ignorée : {s}  (valides : {valid})")
    return list(dict.fromkeys(resolved))


def _print_estimate(seasons: list[str], base_sleep: float) -> None:
    n_per_season = (
        len(TEAM_SEASON_STATS) + len(PLAYER_SEASON_STATS)
        + len(TEAM_MATCH_STATS) + len(PLAYER_MATCH_STATS) + len(_FLAT_FILES)
    )
    per_season_s = n_per_season * base_sleep * 1.1 + 4 * SLEEP_BETWEEN_CATEGORIES
    total_s = per_season_s * len(seasons) + (len(seasons) - 1) * SLEEP_BETWEEN_SEASONS
    log.info(
        f"⏱  Estimation (pire cas, sans skip) : "
        f"~{total_s / 60:.0f} min pour {len(seasons)} saison(s) "
        f"({n_per_season} req × {base_sleep:.0f}s ± jitter)."
    )


def _write_summary(
    log_path: Path, args: argparse.Namespace, seasons: list[str],
    total: dict[str, int], state: State, status: str,
) -> Path:
    """Écrit un résumé JSON de la session pour traçabilité."""
    elapsed = time.monotonic() - state.start_time
    summary = {
        "timestamp":          datetime.now().isoformat(timespec="seconds"),
        "duration_seconds":   round(elapsed, 1),
        "duration_minutes":   round(elapsed / 60, 1),
        "status":             status,  # "completed" | "banned" | "interrupted"
        "seasons":            seasons,
        "args": {
            "force":    args.force,
            "sleep":    args.sleep,
            "dry_run":  args.dry_run,
            "proxy":    args.proxy,
            "no_cache": args.no_cache or args.force,
        },
        "totals":             total,
        "per_season":         state.per_season,
        "total_errors":       state.total_errors,
        "final_sleep":        state.base_sleep,
        "log_file":           str(log_path),
    }
    sum_path = _LOG_DIR / f"summary_{datetime.now():%Y%m%d_%H%M%S}.json"
    sum_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"📄 Résumé JSON : {sum_path.relative_to(Path.cwd()) if sum_path.is_relative_to(Path.cwd()) else sum_path}")
    return sum_path


# ── Main ──────────────────────────────────────────────────────────────────────

log: logging.Logger  # défini dans main()


def main() -> None:
    global log
    log, log_path = _setup_logging()

    args = _parse_args()
    seasons = _resolve_seasons(args.seasons)
    if not seasons:
        log.error("Aucune saison valide. Abandon."); sys.exit(1)

    state = State(base_sleep=args.sleep)
    _install_sigint_handler(state)

    # Proxy
    if args.proxy:
        os.environ["HTTP_PROXY"] = args.proxy
        os.environ["HTTPS_PROXY"] = args.proxy
        log.info(f"[proxy] {args.proxy}")

    if args.dry_run:
        log.info("Mode dry-run — aucun téléchargement.\n")
    else:
        _print_estimate(seasons, args.sleep)
        log.info(f"📝 Log : {log_path.relative_to(Path.cwd()) if log_path.is_relative_to(Path.cwd()) else log_path}")

        # Pre-flight
        if not args.skip_ping:
            log.info("\n→ Pre-flight check : ping FBref…")
            if not _check_fbref_accessible(args.proxy):
                log.error(
                    "\n❌  FBref retourne une erreur d'accès depuis votre IP.\n"
                    "    Vous êtes probablement banni. Attendez 1 à 24 h, ou :\n"
                    "      • Changez de réseau (4G, autre Wi-Fi)\n"
                    "      • Utilisez --proxy <URL>\n"
                    "      • Ignorez ce check avec --skip-ping (à vos risques)\n"
                )
                _write_summary(log_path, args, seasons, {"ok":0,"skip":0,"err":0},
                               state, status="ban_detected_preflight")
                sys.exit(2)
            log.info("✓  FBref accessible — démarrage.\n")

    no_cache = args.no_cache or args.force
    total: dict[str, int] = {"ok": 0, "skip": 0, "err": 0}
    final_status = "completed"

    try:
        for i, season_key in enumerate(seasons):
            counters = scrape_season(
                season_key,
                force=args.force, state=state,
                dry_run=args.dry_run, no_cache=no_cache,
            )
            state.per_season[season_key] = counters
            if not args.dry_run:
                for k in total:
                    total[k] += counters[k]
                if state.interrupted:
                    final_status = "interrupted"
                    log.warning("Ctrl+C → arrêt à la fin de cette saison.")
                    break
                if i < len(seasons) - 1:
                    _jitter_sleep(SLEEP_BETWEEN_SEASONS, "inter-saison")
    except FBrefBannedError as exc:
        log.error(f"\n{'═' * 62}")
        log.error(f"  🛑 ABANDON : {exc}")
        log.error(f"{'═' * 62}\n")
        final_status = "banned"
    except KeyboardInterrupt:
        log.warning("\n\nInterruption forcée.")
        final_status = "interrupted"

    if not args.dry_run:
        elapsed = (time.monotonic() - state.start_time) / 60
        log.info(f"\n{'═' * 62}")
        log.info(
            f"  RÉSUMÉ  {len(seasons)} saison(s) · "
            f"{total['ok']} ok · {total['skip']} ignorés · {total['err']} erreurs"
            f"  (durée : {elapsed:.1f} min)"
        )
        log.info(f"{'═' * 62}\n")
        _write_summary(log_path, args, seasons, total, state, status=final_status)

        if final_status == "banned":
            sys.exit(3)
        if total["err"] > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
