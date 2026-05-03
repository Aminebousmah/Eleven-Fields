"""
Filtres réutilisables.

Architecture :
  - Sidebar : uniquement les filtres GLOBAUX (saison, ligue).
  - Chaque dashboard utilise des sélecteurs CONTEXTUELS (select_team,
    select_player, select_two_teams, select_two_players) placés EN HAUT du
    contenu de la page, pas dans la sidebar.
  - Les filtres globaux vivent dans st.session_state (season_idx, league).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import SEASONS, LEAGUES, LEAGUE_LABELS, COLORS
from data.loader import load_team_season_stats, load_player_season_stats


# ── Helpers ───────────────────────────────────────────────────────────────────

def _init_state(key: str, default) -> None:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Filtres globaux (sidebar) ─────────────────────────────────────────────────

def render_global_filters() -> tuple[str, str]:
    """
    Sidebar : Saison + Ligue uniquement.
    Retourne (season_key, league).
    """
    st.sidebar.markdown(
        f"<div style='font-size:0.72rem;color:{COLORS['text_muted']};"
        f"text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px'>"
        f"Filtres globaux</div>",
        unsafe_allow_html=True,
    )

    season_labels = list(SEASONS.values())
    season_keys = list(SEASONS.keys())
    _init_state("season_idx", len(season_keys) - 1)

    season_label = st.sidebar.selectbox(
        "Saison",
        options=season_labels,
        index=st.session_state["season_idx"],
        key="season_select",
    )
    st.session_state["season_idx"] = season_labels.index(season_label)
    season_key = season_keys[st.session_state["season_idx"]]

    league_options = ["Toutes les ligues"] + LEAGUES
    league = st.sidebar.selectbox(
        "Ligue",
        options=league_options,
        format_func=lambda x: LEAGUE_LABELS.get(x, x),
        key="league_select",
        index=league_options.index(st.session_state.get("league", "Toutes les ligues"))
        if st.session_state.get("league", "Toutes les ligues") in league_options else 0,
    )
    st.session_state["league"] = league
    return season_key, league


# ── Sélecteurs contextuels (en haut du contenu) ───────────────────────────────

def _teams_for(season_key: str, league: str) -> list[str]:
    df = load_team_season_stats("standard", [season_key])
    if league != "Toutes les ligues":
        df = df[df["league"] == league]
    return sorted(df["team"].dropna().unique().tolist())


def select_team(
    season_key: str,
    league: str,
    label: str = "Équipe",
    key: str = "team_ctx",
    default: str | None = None,
) -> str:
    """Sélecteur d'équipe unique (contextuel, affiché dans le contenu)."""
    teams = _teams_for(season_key, league)
    if not teams:
        st.warning("Aucune équipe disponible pour ces filtres.")
        return ""

    # Session state partagé : si on a sélectionné via Database, on récupère la valeur
    persistent_key = f"_selected_{key}"
    _init_state(persistent_key, default or teams[0])
    current = st.session_state[persistent_key]
    if current not in teams:
        current = teams[0]

    selected = st.selectbox(
        label,
        teams,
        index=teams.index(current),
        key=f"{key}_select",
    )
    st.session_state[persistent_key] = selected
    return selected


def select_two_teams(
    season_key: str,
    league: str,
    key_prefix: str = "cmp",
) -> tuple[str, str]:
    """Sélecteur de deux équipes côte-à-côte pour comparaison."""
    teams = _teams_for(season_key, league)
    if len(teams) < 2:
        st.warning("Moins de 2 équipes disponibles.")
        return teams[0] if teams else "", ""

    k1, k2 = f"_{key_prefix}_t1", f"_{key_prefix}_t2"
    _init_state(k1, teams[0])
    _init_state(k2, teams[1])

    c1, c2 = st.columns(2)
    with c1:
        t1 = st.selectbox(
            "🟢 Club A",
            teams,
            index=teams.index(st.session_state[k1]) if st.session_state[k1] in teams else 0,
            key=f"{key_prefix}_t1_select",
        )
    with c2:
        t2 = st.selectbox(
            "🔴 Club B",
            teams,
            index=teams.index(st.session_state[k2]) if st.session_state[k2] in teams else 1,
            key=f"{key_prefix}_t2_select",
        )
    st.session_state[k1] = t1
    st.session_state[k2] = t2
    return t1, t2


def select_player(
    season_key: str,
    league: str,
    key_prefix: str = "player",
    allow_cross_team: bool = True,
    min_minutes_default: int = 500,
) -> tuple[str, str, str]:
    """
    Sélecteur de joueur multi-critères (Position / Minutes / Recherche / Joueur).
    Retourne (player, team, position_group).
    """
    pdf = load_player_season_stats("standard", [season_key])
    if league != "Toutes les ligues":
        pdf = pdf[pdf["league"] == league]

    if pdf.empty:
        st.warning("Aucun joueur disponible.")
        return "", "", ""

    # Filtres en ligne
    c1, c2, c3 = st.columns([1, 1, 2])

    with c1:
        position = st.selectbox(
            "Position",
            ["Tous", "FW", "MF", "DF", "GK"],
            key=f"{key_prefix}_pos",
        )

    with c2:
        min_minutes = st.select_slider(
            "Minutes min.",
            options=[0, 300, 500, 900, 1500, 2000, 3000],
            value=min_minutes_default,
            key=f"{key_prefix}_min",
        )

    with c3:
        search = st.text_input(
            "Rechercher un joueur",
            placeholder="Nom…",
            key=f"{key_prefix}_search",
        )

    # Application des filtres
    df = pdf.copy()
    if position != "Tous":
        df = df[df["pos"].astype(str).str.contains(position, na=False)]
    if "Min" in df.columns:
        df = df[pd.to_numeric(df["Min"], errors="coerce").fillna(0) >= min_minutes]
    if search:
        df = df[df["player"].astype(str).str.contains(search, case=False, na=False)]

    players = sorted(df["player"].dropna().unique().tolist())
    if not players:
        st.info("Aucun joueur ne correspond aux filtres.")
        return "", "", ""

    persistent_key = f"_selected_{key_prefix}"
    _init_state(persistent_key, players[0])
    current = st.session_state[persistent_key]
    if current not in players:
        current = players[0]

    player = st.selectbox(
        f"Joueur ({len(players)} disponibles)",
        players,
        index=players.index(current),
        key=f"{key_prefix}_select",
    )
    st.session_state[persistent_key] = player

    # Récupère l'équipe + la position du joueur
    row = df[df["player"] == player]
    if row.empty:
        return player, "", ""
    team = row["team"].values[0]
    pos_str = str(row["pos"].values[0]) if "pos" in row.columns else ""
    pos_group = _pos_to_group(pos_str)
    return player, team, pos_group


def select_two_players(
    season_key: str,
    league: str,
) -> tuple[tuple[str, str], tuple[str, str]]:
    """Deux sélecteurs joueur côte-à-côte. Retourne ((p1,t1), (p2,t2))."""
    pdf = load_player_season_stats("standard", [season_key])
    if league != "Toutes les ligues":
        pdf = pdf[pdf["league"] == league]

    if pdf.empty:
        return ("", ""), ("", "")

    cA, cB = st.columns(2)

    with cA:
        st.markdown(f"<div style='color:{COLORS['accent_green']};font-weight:700'>🟢 Joueur A</div>",
                    unsafe_allow_html=True)
        p1, t1, _ = select_player(season_key, league, key_prefix="pA")
    with cB:
        st.markdown(f"<div style='color:{COLORS['accent_red']};font-weight:700'>🔴 Joueur B</div>",
                    unsafe_allow_html=True)
        p2, t2, _ = select_player(season_key, league, key_prefix="pB")

    return (p1, t1), (p2, t2)


# ── Utilitaires ──────────────────────────────────────────────────────────────

def _pos_to_group(pos_str: str) -> str:
    """FBref pos → FW/MF/DF/GK."""
    if pd.isna(pos_str):
        return "MF"
    p = str(pos_str).upper()
    if "GK" in p:
        return "GK"
    if "FW" in p:
        return "FW"
    if "DF" in p:
        return "DF"
    return "MF"
