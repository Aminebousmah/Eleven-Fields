"""
Dashboard Base de données — Hub d'exploration.

Trois onglets :
  🏆 Classements        : tableau par ligue avec V/N/D, Pts, ±xG, forme
  🥇 Top Joueurs        : leaderboards par catégorie (buteurs, passeurs, …)
  🔎 Explorer           : recherche avancée joueurs/équipes avec filtres
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import COLORS, LEAGUE_LABELS, METRIC_DEFINITIONS
from components.flags import get_flag_url
from components.glossary import render_metric_glossary
from components.kpi_cards import render_section_header, render_kpi_row
from data.loader import (
    load_team_season_stats, load_player_season_stats, load_team_match_stats,
)

try:
    from transfermarkt.loader import (
        load_players as tm_load_players,
        load_clubs as tm_load_clubs,
        fbref_league_to_tm,
    )
    from transfermarkt.matcher import _normalize, format_value
    TM_AVAILABLE = True
except Exception:
    TM_AVAILABLE = False
    tm_load_players = lambda: pd.DataFrame()
    tm_load_clubs = lambda: pd.DataFrame()
    _normalize = lambda s: str(s).lower() if s else ""
    format_value = lambda v: "—"
    fbref_league_to_tm = lambda l: None


# ── Helpers : navigation et enrichissement ────────────────────────────────────

def _goto(page: str, entity_type: str, name: str, team: str = "") -> None:
    st.session_state["_goto"] = page
    st.session_state[f"_selected_{entity_type}"] = name
    if team:
        st.session_state["_selected_team_ctx"] = team
    st.rerun()


def _enrich_with_tm(df: pd.DataFrame, kind: str, league_filter: str | None) -> pd.DataFrame:
    if not TM_AVAILABLE or df.empty:
        return df
    tm_league = fbref_league_to_tm(league_filter)
    if kind == "player":
        tm = tm_load_players()
        if tm.empty: return df
        if tm_league: tm = tm[tm["current_club_domestic_competition_id"] == tm_league]
        tm = tm[["name", "image_url", "market_value_in_eur"]].copy()
        tm["_norm"] = tm["name"].apply(_normalize)
        df = df.copy()
        df["_norm"] = df["player"].apply(_normalize)
        return df.merge(tm.drop(columns=["name"]), on="_norm", how="left").drop(columns=["_norm"])
    if kind == "club":
        tm = tm_load_clubs()
        if tm.empty: return df
        if tm_league: tm = tm[tm["domestic_competition_id"] == tm_league]
        tm = tm[["name", "logo_url"]].copy()
        tm["_norm"] = tm["name"].apply(_normalize)
        df = df.copy()
        df["_norm"] = df["team"].apply(_normalize)
        return df.merge(tm.drop(columns=["name"]), on="_norm", how="left").drop(columns=["_norm"])
    return df


def _form_string(results: list[str], n: int = 5) -> str:
    """Convertit une suite de W/D/L en emojis."""
    icons = {"W": "🟢", "D": "⚪", "L": "🔴"}
    last = [r for r in results if r in ("W", "D", "L")][-n:]
    return "".join(icons.get(r, "·") for r in last) or "—"


# ── Render ────────────────────────────────────────────────────────────────────

def render(season: str, league: str) -> None:
    league_f = None if league == "Toutes les ligues" else league
    league_label = LEAGUE_LABELS.get(league_f, league_f or "Big 5")

    st.markdown(
        f"<h2 style='color:{COLORS['text']};margin-bottom:0'>📊 Base de données</h2>"
        f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;margin-bottom:14px'>"
        f"Hub d'exploration · {league_label} · {season}</div>",
        unsafe_allow_html=True,
    )

    _render_overview_kpis(season, league_f)

    tab_class, tab_top, tab_explore = st.tabs([
        "🏆 Classements",
        "🥇 Top Joueurs",
        "🔎 Explorer",
    ])

    with tab_class:
        _render_standings(season, league_f, league_label)
    with tab_top:
        _render_leaderboards(season, league_f)
    with tab_explore:
        _render_explorer(season, league_f)


# ── KPIs globaux ──────────────────────────────────────────────────────────────

def _render_overview_kpis(season: str, league_f: str | None) -> None:
    std = load_team_season_stats("standard", [season])
    pdf = load_player_season_stats("standard", [season])
    if league_f:
        std = std[std["league"] == league_f]
        pdf = pdf[pdf["league"] == league_f]

    n_teams = std["team"].nunique() if not std.empty else 0
    n_players = pdf["player"].nunique() if not pdf.empty else 0
    total_min = pd.to_numeric(pdf["Min"], errors="coerce").sum() if not pdf.empty else 0
    total_goals = pd.to_numeric(pdf["Gls"], errors="coerce").sum() if not pdf.empty else 0

    # Valeur totale via Transfermarkt
    total_value = "—"
    if TM_AVAILABLE:
        try:
            tm_players = tm_load_players()
            tm_league = fbref_league_to_tm(league_f)
            if tm_league:
                tm_players = tm_players[tm_players["current_club_domestic_competition_id"] == tm_league]
            v = pd.to_numeric(tm_players["market_value_in_eur"], errors="coerce").sum()
            total_value = format_value(float(v)) if v > 0 else "—"
        except Exception:
            pass

    render_kpi_row([
        {"label": "Équipes",    "value": str(n_teams),         "color": COLORS["accent_green"]},
        {"label": "Joueurs",    "value": str(n_players),       "color": COLORS["accent_blue"]},
        {"label": "Buts saison","value": f"{int(total_goals)}", "color": COLORS["accent_red"]},
        {"label": "Valeur marché", "value": total_value,        "color": COLORS["accent_gold"]},
    ])


# ── Onglet 1 : Classements ────────────────────────────────────────────────────

def _build_standings(season: str, league_f: str | None) -> pd.DataFrame:
    """Construit un classement V/N/D/Pts/Diff à partir de schedule."""
    sched = load_team_match_stats("schedule", [season])
    if sched.empty:
        return pd.DataFrame()

    # La colonne `league` du fichier schedule est souvent vide → on la reconstruit
    # à partir du mapping team→league issu de standard.
    std = load_team_season_stats("standard", [season])
    if not std.empty:
        team_to_league = dict(zip(std["team"], std["league"]))
        sched = sched.copy()
        sched["league"] = sched["team"].map(team_to_league).fillna(sched["league"])

    if league_f:
        sched = sched[sched["league"] == league_f]

    # Garder uniquement les matchs de championnat (round nommé "Matchweek N" etc.)
    if "round" in sched.columns:
        mask_round = sched["round"].astype(str).str.contains(
            "Matchweek|Jornada|Spielwoche|Giornata|Journée", na=False, case=False,
        )
        # Si la colonne round est vide, on garde tous les matchs avec result valide
        if mask_round.any():
            sched = sched[mask_round]
    sched = sched[sched["result"].isin(["W", "D", "L"])].copy()
    if sched.empty:
        return pd.DataFrame()

    sched["GF"] = pd.to_numeric(sched["GF"], errors="coerce")
    sched["GA"] = pd.to_numeric(sched["GA"], errors="coerce")
    sched["xG"] = pd.to_numeric(sched.get("xG"), errors="coerce")
    sched["xGA"] = pd.to_numeric(sched.get("xGA"), errors="coerce")
    sched["pts"] = sched["result"].map({"W": 3, "D": 1, "L": 0})

    # Aggrégation
    sched["date"] = pd.to_datetime(sched["date"], errors="coerce")
    grp = sched.groupby(["league", "team"], as_index=False).agg(
        J=("result", "count"),
        V=("result", lambda s: (s == "W").sum()),
        N=("result", lambda s: (s == "D").sum()),
        D=("result", lambda s: (s == "L").sum()),
        BP=("GF", "sum"),
        BC=("GA", "sum"),
        xG=("xG", "sum"),
        xGA=("xGA", "sum"),
        Pts=("pts", "sum"),
    )
    grp["Diff"] = grp["BP"] - grp["BC"]
    grp["±xG"] = (grp["xG"] - grp["xGA"]).round(1)

    # Forme récente : 5 derniers résultats par équipe
    sched_sorted = sched.sort_values("date")
    form = (
        sched_sorted.groupby(["league", "team"])["result"]
        .apply(lambda s: _form_string(s.tolist()))
        .reset_index(name="Forme")
    )
    grp = grp.merge(form, on=["league", "team"], how="left")
    grp = grp.sort_values(["league", "Pts", "Diff", "BP"], ascending=[True, False, False, False])
    return grp


def _render_standings(season: str, league_f: str | None, league_label: str) -> None:
    df = _build_standings(season, league_f)
    if df.empty:
        st.info("Pas de données de calendrier pour ces filtres.")
        return

    df = _enrich_with_tm(df, "club", league_f)

    leagues_to_show = [league_f] if league_f else df["league"].unique().tolist()

    for lg in leagues_to_show:
        sub = df[df["league"] == lg].copy()
        if sub.empty:
            continue
        sub = sub.reset_index(drop=True)
        sub.insert(0, "Rk", range(1, len(sub) + 1))

        render_section_header(LEAGUE_LABELS.get(lg, lg))

        cols = ["Rk"]
        if "logo_url" in sub.columns:
            cols.append("logo_url")
        cols += ["team", "J", "V", "N", "D", "BP", "BC", "Diff", "Pts", "xG", "xGA", "±xG", "Forme"]
        cols = [c for c in cols if c in sub.columns]
        disp = sub[cols].rename(columns={"logo_url": "Logo", "team": "Équipe"})

        column_config = {}
        if "Logo" in disp.columns:
            column_config["Logo"] = st.column_config.ImageColumn("Logo", width="small")
        column_config["Pts"] = st.column_config.NumberColumn("Pts", help="Points", format="%d")
        column_config["±xG"] = st.column_config.NumberColumn(
            "±xG", help="xG marqués − xG concédés", format="%.1f"
        )

        st.dataframe(
            disp, use_container_width=True, hide_index=True, height=min(36*len(sub)+50, 760),
            column_config=column_config,
        )

    render_metric_glossary(metrics=["xG", "xGA", "GF", "GA"], title="ℹ️ Glossaire classement")


# ── Onglet 2 : Top Joueurs (leaderboards) ─────────────────────────────────────

LEADERBOARDS = [
    ("⚽ Top buteurs",          "standard", "Gls",  "Buts"),
    ("🎯 Top passeurs",         "standard", "Ast",  "Passes décisives"),
    ("📈 Top xG",               "shooting", "xG",   "Buts attendus"),
    ("🧠 Top créateurs (xAG)",  "passing",  "xAG",  "Passes attendues"),
    ("🔑 Top passes-clés",      "passing",  "KP",   "Passes-clés"),
    ("🏃 Top conduites prog.",  "standard", "PrgC", "Conduites progressives"),
    ("🛡️ Top tacleurs",         "defense",  "Tkl",  "Tacles"),
    ("🚫 Top intercepteurs",    "defense",  "Int",  "Interceptions"),
]


def _render_leaderboards(season: str, league_f: str | None) -> None:
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        choice = st.selectbox(
            "Catégorie",
            [lb[0] for lb in LEADERBOARDS],
            key="db_lb_cat",
        )
    with c2:
        top_n = st.select_slider("Top N", options=[10, 20, 50, 100], value=20, key="db_lb_n")
    with c3:
        min_min = st.select_slider("Min. minutes", options=[0, 300, 500, 900, 1500], value=500, key="db_lb_min")

    label, st_type, col, descr = next(lb for lb in LEADERBOARDS if lb[0] == choice)

    df = load_player_season_stats(st_type, [season])
    if league_f:
        df = df[df["league"] == league_f]
    if df.empty or col not in df.columns:
        st.info("Pas de données.")
        return

    # Récupère minutes depuis standard pour filtrage
    std = load_player_season_stats("standard", [season])
    if league_f:
        std = std[std["league"] == league_f]
    df = df.merge(
        std[["player", "team", "Min", "pos", "age"]],
        on=["player", "team"], how="left", suffixes=("", "_std")
    )
    df["Min"] = pd.to_numeric(df["Min"], errors="coerce").fillna(0)
    df = df[df["Min"] >= min_min]
    df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=[col]).sort_values(col, ascending=False).head(top_n)

    if df.empty:
        st.info("Aucun joueur ne passe les filtres.")
        return

    df = _enrich_with_tm(df, "player", league_f)
    df = df.reset_index(drop=True)
    df.insert(0, "#", range(1, len(df) + 1))

    # Colonne drapeau
    if "nation" in df.columns:
        df["flag_url"] = df["nation"].apply(
            lambda x: get_flag_url(str(x).split()[-1], size=20) if pd.notna(x) and str(x).strip() else None
        )

    cols = ["#"]
    if "image_url" in df.columns:
        cols.append("image_url")
    if "flag_url" in df.columns:
        cols.append("flag_url")
    cols += ["player", "team", "league", "pos", "age", col]
    if "market_value_in_eur" in df.columns:
        df["Valeur"] = df["market_value_in_eur"].apply(format_value)
        cols.append("Valeur")
    cols = [c for c in cols if c in df.columns]

    disp = df[cols].rename(columns={
        "image_url": "Photo", "flag_url": "Pays",
        "player": "Joueur", "team": "Équipe",
        "league": "Ligue", "pos": "Position", "age": "Âge",
        "Min": "Minutes", col: descr,
    })
    if "Minutes" in disp.columns:
        disp = disp.drop(columns=["Minutes"])

    column_config = {}
    if "Photo" in disp.columns:
        column_config["Photo"] = st.column_config.ImageColumn("Photo", width="small")
    if "Pays" in disp.columns:
        column_config["Pays"] = st.column_config.ImageColumn("Pays", width="small")
    column_config[descr] = st.column_config.NumberColumn(descr, format="%.1f")

    render_section_header(label, descr)
    st.dataframe(
        disp, use_container_width=True, hide_index=True,
        height=min(38*len(disp)+50, 760), column_config=column_config,
    )

    render_metric_glossary(metrics=[col])


# ── Onglet 3 : Explorer (recherche avancée joueurs) ───────────────────────────

def _render_explorer(season: str, league_f: str | None) -> None:
    pdf = load_player_season_stats("standard", [season])
    if league_f:
        pdf = pdf[pdf["league"] == league_f]
    if pdf.empty:
        st.info("Aucun joueur pour ces filtres.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        position = st.selectbox("Position", ["Tous", "FW", "MF", "DF", "GK"], key="db_e_pos")
    with c2:
        teams = ["Tous"] + sorted(pdf["team"].dropna().unique().tolist())
        team_pick = st.selectbox("Équipe", teams, key="db_e_team")
    with c3:
        age_range = st.slider("Âge", 15, 45, (15, 45), key="db_e_age")
    with c4:
        min_minutes = st.select_slider(
            "Min. minutes", options=[0, 300, 500, 900, 1500, 2000, 3000],
            value=500, key="db_e_min",
        )

    c5, c6, c7 = st.columns([2, 1, 1])
    with c5:
        search = st.text_input("🔎 Rechercher un joueur", key="db_e_search",
                               placeholder="Commence à taper…")
    with c6:
        sort_options = [c for c in ["Min", "Gls", "Ast", "xG", "xAG", "PrgP", "PrgC"]
                        if c in pdf.columns]
        sort_by = st.selectbox("Trier par", sort_options, key="db_e_sort")
    with c7:
        sort_desc = st.toggle("↓ Décroissant", value=True, key="db_e_desc")

    df = pdf.copy()
    if position != "Tous":
        df = df[df["pos"].astype(str).str.contains(position, na=False)]
    if team_pick != "Tous":
        df = df[df["team"] == team_pick]
    df["age_num"] = pd.to_numeric(df["age"], errors="coerce")
    df["min_num"] = pd.to_numeric(df["Min"], errors="coerce")
    df = df[df["age_num"].between(age_range[0], age_range[1])]
    df = df[df["min_num"].fillna(0) >= min_minutes]
    if search:
        df = df[df["player"].astype(str).str.contains(search, case=False, na=False)]

    if sort_by in df.columns:
        df[sort_by] = pd.to_numeric(df[sort_by], errors="coerce")
        df = df.sort_values(sort_by, ascending=not sort_desc)

    render_section_header(f"{len(df)} joueur(s)")

    df_e = _enrich_with_tm(df, "player", league_f)
    # Colonne drapeau
    if "nation" in df_e.columns:
        df_e["flag_url"] = df_e["nation"].apply(
            lambda x: get_flag_url(str(x).split()[-1], size=20) if pd.notna(x) and str(x).strip() else None
        )
    base_cols = ["player", "team", "league", "pos", "age", "MP",
                 "Gls", "Ast", "xG", "xAG", "PrgP", "PrgC", "CrdY"]
    extras = []
    if "image_url" in df_e.columns: extras.append("image_url")
    if "flag_url"  in df_e.columns: extras.append("flag_url")
    if "market_value_in_eur" in df_e.columns:
        df_e["Valeur"] = df_e["market_value_in_eur"].apply(format_value)
        base_cols = base_cols + ["Valeur"]
    show_cols = extras + [c for c in base_cols if c in df_e.columns]
    disp = df_e[show_cols].rename(columns={
        "image_url": "Photo", "flag_url": "Pays",
        "player": "Joueur", "team": "Équipe", "league": "Ligue",
        "pos": "Position", "age": "Âge", "MP": "J",
        "Gls": "Buts", "Ast": "Passes D.", "CrdY": "Jaunes",
    })

    column_config = {}
    if "Photo" in disp.columns:
        column_config["Photo"] = st.column_config.ImageColumn("Photo", width="small")
    if "Pays" in disp.columns:
        column_config["Pays"] = st.column_config.ImageColumn("Pays", width="small")

    st.dataframe(
        disp, use_container_width=True, height=560, hide_index=True,
        column_config=column_config,
    )

    if not df.empty:
        st.divider()
        cs1, cs2, cs3 = st.columns([4, 1, 1])
        with cs1:
            sel = st.selectbox("Joueur à analyser", sorted(df["player"].dropna().unique()),
                               key="db_e_pick")
        with cs2:
            if st.button("👤 Profil →", use_container_width=True, key="db_e_go", type="primary"):
                team = df[df["player"] == sel]["team"].values[0] if sel else ""
                _goto("player", "player", sel, team)
        with cs3:
            if st.button("⚖️ Comparer", use_container_width=True, key="db_e_cmp"):
                team = df[df["player"] == sel]["team"].values[0] if sel else ""
                st.session_state["_cmp_p1"] = sel
                _goto("compare", "player", sel, team)

    render_metric_glossary(metrics=["Gls", "Ast", "xG", "xAG", "PrgP", "PrgC", "CrdY"])
