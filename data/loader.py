"""
Chargement et cache de toutes les sources de données.
Règle : aucun pd.read_csv hors de ce fichier.
Pour ajouter une source : créer une nouvelle fonction load_* ici.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from config import DATA_DIR, CHART_CLUB_DIR, SEASONS


# ── Parsers internes ──────────────────────────────────────────────────────────

def _parse_multiheader_csv(path: Path) -> pd.DataFrame:
    """
    Parse les CSVs FBref exportés par soccerdata.
    Format : 2 lignes d'en-tête (groupe / métrique), première ligne de données
    contenant les noms des colonnes d'index (league, season, team, player…).
    Les colonnes 'Per 90 Minutes' reçoivent le suffixe _p90.
    """
    df = pd.read_csv(path, header=[0, 1], low_memory=False)

    meta = df.iloc[0]  # noms des colonnes d'index stockés dans la 1ère ligne

    new_cols: list[str] = []
    for i, (l0, l1) in enumerate(df.columns):
        l0, l1 = str(l0), str(l1)
        if "Unnamed" in l0 and "Unnamed" in l1:
            val = str(meta.iloc[i])
            new_cols.append(val if val != "nan" else f"col_{i}")
        elif "Per 90" in l0:
            new_cols.append(f"{l1}_p90")
        elif "Unnamed" in l1:
            new_cols.append(l0)
        else:
            new_cols.append(l1)

    df.columns = new_cols
    df = df.iloc[1:].reset_index(drop=True)

    # Dé-dupliquer les noms de colonnes
    seen: dict[str, int] = {}
    unique: list[str] = []
    for col in df.columns:
        if col in seen:
            seen[col] += 1
            unique.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            unique.append(col)
    df.columns = unique

    return df


def _parse_flat_csv(path: Path) -> pd.DataFrame:
    """Parse un CSV à en-tête simple (schedule, events, lineups…)."""
    for enc in ("utf-8", "latin1"):
        try:
            return pd.read_csv(path, low_memory=False, encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, low_memory=False, encoding="utf-8", errors="replace")


def _numeric(df: pd.DataFrame, exclude: tuple[str, ...] = ()) -> pd.DataFrame:
    """Convertit toutes les colonnes sauf exclude en numérique."""
    skip = {"league", "season", "team", "player", "game", "date", "url",
            "nation", "pos", "match_report", "Notes",
            "Captain", "Formation", "Opp Formation", "Referee",
            "result", "opponent", "time", "round", "day", "venue",
            "home_team", "away_team", "score", "comp", "stage",
            *exclude}
    for col in df.columns:
        if col not in skip:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ── Loaders team saison ───────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_team_season_stats(
    stat_type: str,
    seasons: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    Charge FB_team_season_stats_{stat_type}.csv pour chaque saison.
    Pour ajouter une saison : déposer le dossier XXYY/ → la fonction le détecte
    automatiquement via SEASONS dans config.py.
    """
    if seasons is None:
        seasons = list(SEASONS.keys())

    frames: list[pd.DataFrame] = []
    for s in seasons:
        path = DATA_DIR / s / f"FB_team_season_stats_{stat_type}.csv"
        if path.exists():
            frames.append(_parse_multiheader_csv(path))

    if not frames:
        return pd.DataFrame()
    return _numeric(pd.concat(frames, ignore_index=True))


@st.cache_data(show_spinner=False)
def load_all_team_season_stats(
    stat_types: list[str],
    seasons: Optional[list[str]] = None,
) -> dict[str, pd.DataFrame]:
    """Charge plusieurs types de stats équipe en une passe."""
    return {st_type: load_team_season_stats(st_type, seasons) for st_type in stat_types}


# ── Loaders player saison ─────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_player_season_stats(
    stat_type: str,
    seasons: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Charge FB_player_season_stats_{stat_type}.csv pour chaque saison."""
    if seasons is None:
        seasons = list(SEASONS.keys())

    frames: list[pd.DataFrame] = []
    for s in seasons:
        path = DATA_DIR / s / f"FB_player_season_stats_{stat_type}.csv"
        if path.exists():
            frames.append(_parse_multiheader_csv(path))

    if not frames:
        return pd.DataFrame()
    return _numeric(pd.concat(frames, ignore_index=True))


@st.cache_data(show_spinner=False)
def load_all_player_season_stats(
    stat_types: list[str],
    seasons: Optional[list[str]] = None,
) -> dict[str, pd.DataFrame]:
    return {st: load_player_season_stats(st, seasons) for st in stat_types}


# ── Loaders match ─────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_team_match_stats(
    stat_type: str,
    seasons: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    Charge FB_team_match_stats_{stat_type}.csv.
    Le fichier 'schedule' a un en-tête plat ; les autres ont un double en-tête.
    """
    if seasons is None:
        seasons = list(SEASONS.keys())

    flat = stat_type == "schedule"
    frames: list[pd.DataFrame] = []
    for s in seasons:
        path = DATA_DIR / s / f"FB_team_match_stats_{stat_type}.csv"
        if path.exists():
            df = _parse_flat_csv(path) if flat else _parse_multiheader_csv(path)
            frames.append(df)

    if not frames:
        return pd.DataFrame()
    return _numeric(pd.concat(frames, ignore_index=True))


@st.cache_data(show_spinner=False)
def load_player_match_stats(
    stat_type: str,
    seasons: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Charge FB_player_match_stats_{stat_type}.csv."""
    if seasons is None:
        seasons = list(SEASONS.keys())

    frames: list[pd.DataFrame] = []
    for s in seasons:
        path = DATA_DIR / s / f"FB_player_match_stats_{stat_type}.csv"
        if path.exists():
            frames.append(_parse_multiheader_csv(path))

    if not frames:
        return pd.DataFrame()
    return _numeric(pd.concat(frames, ignore_index=True))


@st.cache_data(show_spinner=False)
def load_schedule(seasons: Optional[list[str]] = None) -> pd.DataFrame:
    """Charge le calendrier FBref (FB_schedule.csv) — en-tête plat."""
    if seasons is None:
        seasons = list(SEASONS.keys())

    frames: list[pd.DataFrame] = []
    for s in seasons:
        path = DATA_DIR / s / "FB_schedule.csv"
        if path.exists():
            df = _parse_flat_csv(path)
            frames.append(df)

    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


@st.cache_data(show_spinner=False)
def load_shot_events(seasons: Optional[list[str]] = None) -> pd.DataFrame:
    if seasons is None:
        seasons = list(SEASONS.keys())

    frames = []
    for s in seasons:
        path = DATA_DIR / s / "FB_shot_events.csv"
        if path.exists():
            frames.append(_parse_flat_csv(path))

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ── Sources complémentaires (Chart Club) ──────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_espn_matchsheet() -> pd.DataFrame:
    path = CHART_CLUB_DIR / "ESPN_matchsheet.csv"
    if not path.exists():
        return pd.DataFrame()
    return _numeric(_parse_flat_csv(path))


@st.cache_data(show_spinner=False)
def load_us_player_stats() -> pd.DataFrame:
    path = CHART_CLUB_DIR / "US_player_season_stats.csv"
    if not path.exists():
        return pd.DataFrame()
    return _numeric(_parse_flat_csv(path))


@st.cache_data(show_spinner=False)
def load_fm_match_stats() -> pd.DataFrame:
    path = CHART_CLUB_DIR / "FM_team_match_stats.csv"
    if not path.exists():
        return pd.DataFrame()
    return _numeric(_parse_flat_csv(path))


@st.cache_data(show_spinner=False)
def load_lineups(seasons: Optional[list[str]] = None) -> pd.DataFrame:
    """Charge les compositions match (FB_lineups.csv) — en-tête plat."""
    if seasons is None:
        seasons = list(SEASONS.keys())
    frames: list[pd.DataFrame] = []
    for s in seasons:
        path = DATA_DIR / s / "FB_lineups.csv"
        if path.exists():
            df = _parse_flat_csv(path)
            df["season_key"] = s
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
