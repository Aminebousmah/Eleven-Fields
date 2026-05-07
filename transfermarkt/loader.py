"""
Loaders Transfermarkt — filtre auto sur 1ère division des Big 5.

Mapping FBref → Transfermarkt competition_id :
  ENG-Premier League    → GB1
  ESP-La Liga           → ES1
  GER-Bundesliga        → L1
  ITA-Serie A           → IT1
  FRA-Ligue 1           → FR1
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent.parent / "transfermarkt_data"

# 1ère division Big 5 uniquement
BIG5_COMPETITION_IDS: list[str] = ["GB1", "ES1", "L1", "IT1", "FR1"]

FBREF_TO_TM = {
    "ENG-Premier League": "GB1",
    "ESP-La Liga":        "ES1",
    "GER-Bundesliga":     "L1",
    "ITA-Serie A":        "IT1",
    "FRA-Ligue 1":        "FR1",
}


def _csv_exists(name: str) -> bool:
    return (DATA_DIR / name).exists()


@st.cache_data(show_spinner=False)
def load_competitions() -> pd.DataFrame:
    """Big 5 first divisions only."""
    if not _csv_exists("competitions.csv"):
        return pd.DataFrame()
    df = pd.read_csv(DATA_DIR / "competitions.csv")
    return df[df["competition_id"].isin(BIG5_COMPETITION_IDS)].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_clubs() -> pd.DataFrame:
    """Clubs des Big 5 first division avec logo + value."""
    if not _csv_exists("clubs.csv"):
        return pd.DataFrame()
    df = pd.read_csv(DATA_DIR / "clubs.csv")
    df = df[df["domestic_competition_id"].isin(BIG5_COMPETITION_IDS)].copy()

    # URL du logo (CDN Transfermarkt) — pattern public
    df["logo_url"] = df["club_id"].apply(
        lambda cid: f"https://tmssl.akamaized.net/images/wappen/head/{cid}.png"
    )
    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_players() -> pd.DataFrame:
    """
    Joueurs actifs des Big 5 first division.
    Contient : player_id, name, image_url, market_value_in_eur, current_club_id, etc.
    """
    if not _csv_exists("players.csv"):
        return pd.DataFrame()
    df = pd.read_csv(DATA_DIR / "players.csv")
    df = df[df["current_club_domestic_competition_id"].isin(BIG5_COMPETITION_IDS)].copy()

    # Normalisation des colonnes utiles
    if "image_url" not in df.columns and "player_id" in df.columns:
        df["image_url"] = df["player_id"].apply(
            lambda pid: f"https://img.a.transfermarkt.technology/portrait/header/{pid}-1.jpg"
        )

    if "market_value_in_eur" in df.columns:
        df["market_value_in_eur"] = pd.to_numeric(df["market_value_in_eur"], errors="coerce")

    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_player_valuations(latest_only: bool = True) -> pd.DataFrame:
    """
    Historique des valeurs marchandes. latest_only=True → dernière valeur par joueur.
    """
    if not _csv_exists("player_valuations.csv"):
        return pd.DataFrame()
    df = pd.read_csv(DATA_DIR / "player_valuations.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if latest_only:
        df = df.sort_values("date").groupby("player_id", as_index=False).tail(1)
    return df.reset_index(drop=True)


# Date de fin de chaque saison Big 5 (fin mai = dernier snapshot avant mercato estival)
SEASON_END_DATES: dict[str, str] = {
    "2122": "2022-05-31",
    "2223": "2023-05-31",
    "2324": "2024-05-31",
    "2425": "2025-05-31",
    "2526": "2026-05-31",
}


@st.cache_data(show_spinner=False)
def load_player_valuations_for_season(season: str) -> pd.DataFrame:
    """
    Snapshot des valeurs marchandes à la fin de la saison `season`.
    Pour chaque joueur, retourne le snapshot dont la date est la plus récente
    ≤ fin de saison (SEASON_END_DATES). Filtre sur les Big 5.

    Colonnes retournées : player_id, date, market_value_in_eur, current_club_id,
                          player_club_domestic_competition_id.
    """
    if not _csv_exists("player_valuations.csv"):
        return pd.DataFrame()

    end_date_str = SEASON_END_DATES.get(season)
    if not end_date_str:
        # Saison inconnue → snapshot le plus récent disponible
        return load_player_valuations(latest_only=True)

    end_date = pd.Timestamp(end_date_str)

    df = pd.read_csv(DATA_DIR / "player_valuations.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    # Filtre Big 5
    df = df[df["player_club_domestic_competition_id"].isin(BIG5_COMPETITION_IDS)]

    # Snapshots <= fin de saison
    df_before = df[df["date"] <= end_date]

    if df_before.empty:
        return pd.DataFrame()

    # Pour chaque joueur : snapshot le plus récent ≤ fin de saison
    snapshot = (
        df_before.sort_values("date")
        .groupby("player_id", as_index=False)
        .last()
    )
    return snapshot.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_appearances() -> pd.DataFrame:
    """
    Historique des apparitions des joueurs (appearances.csv).
    ~1.86M lignes : player_id, player_club_id, date, goals, assists, minutes_played, ...
    """
    if not _csv_exists("appearances.csv"):
        return pd.DataFrame()
    df = pd.read_csv(DATA_DIR / "appearances.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


@st.cache_data(show_spinner=False)
def load_games() -> pd.DataFrame:
    """Calendrier TM des matchs (games.csv)."""
    if not _csv_exists("games.csv"):
        return pd.DataFrame()
    df = pd.read_csv(DATA_DIR / "games.csv")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def fbref_league_to_tm(league: Optional[str]) -> Optional[str]:
    """ENG-Premier League → GB1."""
    if not league or league == "Toutes les ligues":
        return None
    return FBREF_TO_TM.get(league)
