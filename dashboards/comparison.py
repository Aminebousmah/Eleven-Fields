"""
Dashboard Comparaison.
Tabs : Équipes (scatter xG/xGA) | Joueurs (radar 2 joueurs) | SHAP | Prédiction PPM
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from config import COLORS, PLAYER_METRICS_BY_POS, LEAGUE_LABELS, LEAGUES
from components.charts import make_scatter, make_radar, make_percentile_bars
from components.filters import select_two_players
from components.glossary import (
    render_metric_glossary, render_disclaimer,
)
from components.kpi_cards import render_section_header, render_kpi_row
from data.loader import (
    load_team_season_stats, load_player_season_stats, load_all_team_season_stats,
)
from data.processor import percentile_score, build_radar_data

try:
    from transfermarkt.matcher import (
        match_player, get_club_logo, format_value,
        enrich_with_logos, enrich_with_photos,
    )
    TM_AVAILABLE = True
except Exception:
    TM_AVAILABLE = False
    def match_player(*a, **kw): return None
    def get_club_logo(*a, **kw): return None
    def format_value(v): return "—"
    def enrich_with_logos(df, *a, **kw): return df
    def enrich_with_photos(df, *a, **kw): return df


def _player_card(player: str, team: str, league_filter: str | None,
                 season: str | None = None, accent: str | None = None) -> None:
    """
    Carte joueur enrichie : photo, club + logo, valeur marché, infos clés.
    `accent` = couleur d'accent (utilisée pour la barre verticale gauche).
    """
    tm = match_player(player, fbref_league=league_filter)
    photo = tm.get("image_url") if tm else None
    logo = get_club_logo(team, league_filter)
    mv = tm.get("market_value_in_eur") if tm else None

    accent_color = accent or COLORS["accent_green"]

    # Bandeau coloré + ligne header
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:14px;"
        f"padding:12px 16px;background:{COLORS['card']};"
        f"border-radius:12px;border:1px solid {COLORS['border']};"
        f"border-left:4px solid {accent_color}'>",
        unsafe_allow_html=True,
    )

    cols = st.columns([1.4, 1, 5])
    with cols[0]:
        if photo:
            st.image(photo, width=110)
        else:
            st.markdown(
                f"<div style='width:110px;height:110px;border-radius:8px;"
                f"background:{COLORS['border']};display:flex;align-items:center;"
                f"justify-content:center;font-size:48px'>👤</div>",
                unsafe_allow_html=True,
            )
    with cols[1]:
        if logo: st.image(logo, width=70)
    with cols[2]:
        st.markdown(
            f"<div style='font-size:1.25rem;font-weight:900;color:{COLORS['text']};"
            f"margin-bottom:4px'>{player}</div>"
            f"<div style='font-size:0.88rem;color:{COLORS['text_muted']};"
            f"margin-bottom:8px'>🏟️ {team}</div>"
            f"<div style='display:flex;gap:12px;flex-wrap:wrap'>"
            + (
                f"<span style='background:{COLORS['accent_gold']}20;"
                f"color:{COLORS['accent_gold']};padding:3px 10px;border-radius:10px;"
                f"font-size:0.78rem;font-weight:700'>💰 {format_value(mv)}</span>"
                if mv and pd.notna(mv) else ""
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pos_group(pos_str: str) -> str:
    if pd.isna(pos_str):
        return "MF"
    pos = str(pos_str).upper()
    if "GK" in pos:
        return "GK"
    if "FW" in pos:
        return "FW"
    if "DF" in pos:
        return "DF"
    return "MF"


def _player_percentiles(
    player: str, team: str,
    metrics: list[tuple[str, str]],
    season: str, league: str | None,
    pos_group: str,
    min_minutes: int = 500,
) -> tuple[list[str], list[float], list[float]]:
    """
    Renvoie (labels, percentiles 0-100, valeurs brutes) pour un joueur,
    en comparant aux joueurs de même position (≥ min_minutes).
    """
    from data.processor import percentile_score

    labels, percentiles, raw = [], [], []
    std = load_player_season_stats("standard", [season])
    if league:
        std = std[std["league"] == league]

    for stat_type, col in metrics:
        df = load_player_season_stats(stat_type, [season])
        if league:
            df = df[df["league"] == league]
        if col not in df.columns:
            continue

        # Filtrer même position + minutes minimum via merge sur (player, team)
        if "Min" in std.columns and "pos" in std.columns:
            ref = std[["player", "team", "pos", "Min"]].copy()
            ref["Min"] = pd.to_numeric(ref["Min"], errors="coerce")
            ref = ref[ref["Min"] >= min_minutes]
            ref = ref[ref["pos"].apply(_pos_group) == pos_group]
            df = df.merge(ref[["player", "team"]], on=["player", "team"], how="inner")

        series = pd.to_numeric(df[col], errors="coerce")
        row = df[(df["player"] == player) & (df["team"] == team)]
        if row.empty:
            continue
        val = pd.to_numeric(row[col].values[0], errors="coerce")
        if pd.isna(val):
            continue
        pct = percentile_score(series, float(val))
        labels.append(col)
        percentiles.append(pct)
        raw.append(float(val))
    return labels, percentiles, raw


# ── Render — Comparaison Clubs (page dédiée) ─────────────────────────────────

def _club_card(team: str, league_filter: str | None, accent: str) -> None:
    """Carte équipe enrichie : logo + nom + ligue."""
    logo = get_club_logo(team, league_filter)

    st.markdown(
        f"<div style='display:flex;align-items:center;gap:14px;"
        f"padding:12px 16px;background:{COLORS['card']};"
        f"border-radius:12px;border:1px solid {COLORS['border']};"
        f"border-left:4px solid {accent}'>",
        unsafe_allow_html=True,
    )

    cols = st.columns([1.2, 5])
    with cols[0]:
        if logo:
            st.image(logo, width=90)
        else:
            st.markdown(
                f"<div style='width:90px;height:90px;border-radius:8px;"
                f"background:{COLORS['border']};display:flex;align-items:center;"
                f"justify-content:center;font-size:40px'>🏟️</div>",
                unsafe_allow_html=True,
            )
    with cols[1]:
        league_lbl = LEAGUE_LABELS.get(league_filter, league_filter or "Big 5")
        st.markdown(
            f"<div style='font-size:1.35rem;font-weight:900;color:{COLORS['text']};"
            f"margin-bottom:4px'>{team}</div>"
            f"<div style='font-size:0.88rem;color:{COLORS['text_muted']}'>"
            f"🇪🇺 {league_lbl}</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def _club_percentiles(team: str, metrics: list[tuple[str, str]],
                      season: str, league_filter: str | None,
                     ) -> tuple[list[str], list[float], list[float]]:
    """Retourne (labels, percentiles 0-100, valeurs brutes) pour un club."""
    from data.processor import percentile_score

    labels, pcts, raws = [], [], []
    for stat_type, col in metrics:
        df = load_team_season_stats(stat_type, [season])
        if league_filter:
            df = df[df["league"] == league_filter]
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        row = df[df["team"] == team]
        if row.empty:
            continue
        val = pd.to_numeric(row[col].values[0], errors="coerce")
        if pd.isna(val):
            continue
        labels.append(col)
        pcts.append(percentile_score(series, float(val)))
        raws.append(float(val))
    return labels, pcts, raws


_CLUB_PRESETS: dict[str, list[tuple[str, str, str]]] = {
    "Offensif": [
        ("Buts",                "standard", "Gls"),
        ("xG",                  "shooting", "xG"),
        ("Tirs",                "shooting", "Sh"),
        ("Tirs cadrés (%)",     "shooting", "SoT%"),
        ("Passes vers surface", "passing",  "PPA"),
        ("Courses progressives","standard", "PrgC"),
    ],
    "Défensif": [
        ("Buts encaissés",      "keeper",   "GA"),
        ("Tacles",              "defense",  "Tkl"),
        ("Interceptions",       "defense",  "Int"),
        ("Blocs",               "defense",  "Blocks"),
        ("Dégagements",         "misc",     "Clr"),
        ("Duels aériens (%)",   "misc",     "Won%"),
    ],
    "Construction": [
        ("Possession",          "standard", "Poss"),
        ("Précision passes",    "passing",  "Cmp%"),
        ("Passes progressives", "standard", "PrgP"),
        ("Passes dernier tiers","passing",  "1/3"),
        ("Touches",             "possession","Touches"),
        ("Distance progr.",     "passing",  "PrgDist"),
    ],
    "Discipline": [
        ("Fautes",              "misc",     "Fls"),
        ("Cartons jaunes",      "standard", "CrdY"),
        ("Cartons rouges",      "standard", "CrdR"),
        ("Hors-jeux",           "misc",     "Off"),
    ],
}


def render_clubs(season: str, league: str) -> None:
    """Comparaison de 2 clubs : cartes + radar percentile + tableau coloré."""
    from components.filters import select_two_teams

    league_filter = None if league == "Toutes les ligues" else league

    render_section_header(
        "Comparaison radar — 2 clubs",
        "Choisis un type de comparaison puis sélectionne les 2 clubs.",
    )

    # Type de comparaison
    comp_type = st.selectbox(
        "Type de comparaison",
        options=list(_CLUB_PRESETS.keys()),
        key="cmp_club_type",
        help="Set de métriques thématique adapté à l'analyse.",
    )

    # Sélecteur 2 clubs
    (team_a, team_b) = select_two_teams(season, league)
    if not (team_a and team_b):
        st.info("Sélectionnez deux clubs.")
        render_disclaimer()
        return

    # Gate "Afficher"
    from components.filters import render_show_gate
    if not render_show_gate(
        "compare_clubs",
        label="⚖️  Lancer la comparaison",
        hint="Tu as choisi tes 2 clubs et le type de comparaison. Clique pour générer.",
    ):
        render_disclaimer()
        return

    # Cartes clubs enrichies
    cardA, cardB = st.columns(2)
    with cardA:
        _club_card(team_a, league_filter, accent=COLORS["accent_green"])
    with cardB:
        _club_card(team_b, league_filter, accent=COLORS["accent_blue"])

    preset = _CLUB_PRESETS[comp_type]
    metrics_raw = [(stat_type, col) for _, stat_type, col in preset]
    metric_labels_fr = {col: label for label, _, col in preset}

    la, pa, ra = _club_percentiles(team_a, metrics_raw, season, league_filter)
    lb, pb, rb = _club_percentiles(team_b, metrics_raw, season, league_filter)
    common = [l for l in la if l in lb]
    if not common:
        st.warning("Pas de métriques communes pour ces clubs.")
        render_disclaimer()
        return

    idx_a = {l: i for i, l in enumerate(la)}
    idx_b = {l: i for i, l in enumerate(lb)}
    display_labels = [metric_labels_fr.get(c, c) for c in common]

    # Radar
    fig = make_radar(
        {
            team_a: [pa[idx_a[l]] / 100 for l in common],
            team_b: [pb[idx_b[l]] / 100 for l in common],
        },
        display_labels,
        title=f"Comparaison percentile — {comp_type} ({LEAGUE_LABELS.get(league_filter, league_filter or 'Big 5')})",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tableau épuré coloré (3 cols : métrique + 2 percentiles)
    comp_df = pd.DataFrame({
        "Métrique": display_labels,
        team_a: [int(round(pa[idx_a[l]])) for l in common],
        team_b: [int(round(pb[idx_b[l]])) for l in common],
    })

    def _color_better(row):
        v1, v2 = row[team_a], row[team_b]
        GREEN_BG = "background-color:#0f6b3f;color:#ffffff;font-weight:700"
        RED_BG   = "background-color:#7a1f29;color:#ffffff;font-weight:700"
        if v1 > v2:
            return ["", GREEN_BG, RED_BG]
        if v2 > v1:
            return ["", RED_BG, GREEN_BG]
        return ["", "", ""]

    styled = (
        comp_df.style
        .apply(_color_better, axis=1)
        .format({team_a: "{:d}", team_b: "{:d}"})
    )
    st.dataframe(
        styled, use_container_width=True, hide_index=True,
        height=min(38 * len(comp_df) + 80, 600),
        column_config={
            "Métrique": st.column_config.TextColumn(width="medium"),
            team_a:     st.column_config.NumberColumn(width="small"),
            team_b:     st.column_config.NumberColumn(width="small"),
        },
    )

    render_disclaimer()


# ── Render — Comparaison Joueurs (page dédiée) ────────────────────────────────

def render_players(season: str, league: str) -> None:
    """Comparaison de 2 joueurs (radar percentile + tableau épuré)."""
    league_filter = None if league == "Toutes les ligues" else league

    if True:
        from config import COMPARISON_PRESETS
        from components.filters import render_show_gate

        render_section_header(
            "Comparaison radar — 2 joueurs",
            "Choisis un type de comparaison puis sélectionne les 2 joueurs.",
        )

        # ── Sélection du type de comparaison ─────────────────────────────────
        comp_options = ["Auto (par poste)"] + list(COMPARISON_PRESETS.keys())
        comp_type = st.selectbox(
            "Type de comparaison",
            options=comp_options,
            key="cmp_type",
            help=(
                "Auto = métriques choisies selon le poste du joueur 1. "
                "Sinon, set de métriques pré-câblé thématique."
            ),
        )

        pdf = load_player_season_stats("standard", [season])
        if league_filter:
            pdf = pdf[pdf["league"] == league_filter]

        (p1, t1), (p2, t2) = select_two_players(season, league)
        if not (p1 and p2):
            st.info("Sélectionnez deux joueurs.")
            render_disclaimer()
            return

        # Gate "Afficher" — après sélection des joueurs
        if not render_show_gate(
            "compare_players",
            label="⚔️  Lancer la comparaison",
            hint="Tu as choisi tes 2 joueurs et le type de comparaison. Clique pour générer.",
        ):
            render_disclaimer()
            return

        if True:
            # Cartes joueurs enrichies
            cardA, cardB = st.columns(2)
            with cardA:
                _player_card(p1, t1, league_filter, season=season,
                             accent=COLORS["accent_green"])
            with cardB:
                _player_card(p2, t2, league_filter, season=season,
                             accent=COLORS["accent_blue"])

            row1 = pdf[(pdf["player"] == p1) & (pdf["team"] == t1)]
            pos1 = _pos_group(row1["pos"].values[0] if not row1.empty else "MF")
            row2 = pdf[(pdf["player"] == p2) & (pdf["team"] == t2)]
            pos2 = _pos_group(row2["pos"].values[0] if not row2.empty else "MF")

            # ── Détermine les métriques selon le type de comparaison ────────
            if comp_type == "Auto (par poste)":
                if pos1 != pos2:
                    st.warning(
                        f"⚠️ Positions différentes : {p1} ({pos1}) vs {p2} ({pos2}). "
                        f"La comparaison utilise les métriques du poste de **{p1}**."
                    )
                metrics_raw = PLAYER_METRICS_BY_POS.get(pos1, PLAYER_METRICS_BY_POS["MF"])
                # Format (stat_type, col) sans label FR
                metric_labels_fr = None
            else:
                preset = COMPARISON_PRESETS[comp_type]
                # Format (label_fr, stat_type, col)
                metrics_raw = [(stat_type, col) for _, stat_type, col in preset]
                metric_labels_fr = {col: label for label, _, col in preset}

            ref_pos = pos1  # pool de référence percentile
            l1, p_pct1, r1 = _player_percentiles(p1, t1, metrics_raw, season, league_filter, ref_pos)
            l2, p_pct2, r2 = _player_percentiles(p2, t2, metrics_raw, season, league_filter, ref_pos)

            common = [l for l in l1 if l in l2]
            if not common:
                st.warning("Pas de métriques communes pour ces joueurs.")
            else:
                # Si on a un preset FR, on utilise les labels FR sur le radar
                display_labels = (
                    [metric_labels_fr.get(c, c) for c in common]
                    if metric_labels_fr else common
                )

                idx1 = {l: i for i, l in enumerate(l1)}
                idx2 = {l: i for i, l in enumerate(l2)}
                fig = make_radar(
                    {
                        p1: [p_pct1[idx1[l]] / 100 for l in common],
                        p2: [p_pct2[idx2[l]] / 100 for l in common],
                    },
                    display_labels,
                    title=(
                        f"Comparaison percentile — {comp_type}"
                        if comp_type != "Auto (par poste)"
                        else f"Comparaison percentile — joueurs {ref_pos} (≥ 500 min)"
                    ),
                )
                st.plotly_chart(fig, use_container_width=True)

                # ── Tableau épuré : 3 colonnes seulement, vert = meilleur, rouge = pire
                comp_df = pd.DataFrame({
                    "Métrique": display_labels,
                    p1: [int(round(p_pct1[idx1[l]])) for l in common],
                    p2: [int(round(p_pct2[idx2[l]])) for l in common],
                })

                def _color_better(row):
                    """Vert/rouge contrastés (fond sombre, texte clair)."""
                    v1, v2 = row[p1], row[p2]
                    GREEN_BG = "background-color:#0f6b3f;color:#ffffff;font-weight:700"
                    RED_BG   = "background-color:#7a1f29;color:#ffffff;font-weight:700"
                    if v1 > v2:
                        return ["", GREEN_BG, RED_BG]
                    if v2 > v1:
                        return ["", RED_BG, GREEN_BG]
                    return ["", "", ""]

                styled = (
                    comp_df.style
                    .apply(_color_better, axis=1)
                    .format({p1: "{:d}", p2: "{:d}"})
                )
                st.dataframe(
                    styled, use_container_width=True, hide_index=True,
                    height=min(38 * len(comp_df) + 80, 600),
                    column_config={
                        "Métrique": st.column_config.TextColumn(width="medium"),
                        p1: st.column_config.NumberColumn(width="small"),
                        p2: st.column_config.NumberColumn(width="small"),
                    },
                )

                # Glossaire uniquement si métriques FBref (pas FR)
                if metric_labels_fr is None:
                    render_metric_glossary(metrics=common)

    render_disclaimer()


# ── Back-compat : render() = ancien comportement (les 2 modes en tabs) ───────

def render(season: str, league: str) -> None:
    """Rétro-compatibilité : appelle les deux modes dans des onglets."""
    league_filter = None if league == "Toutes les ligues" else league
    tab1, tab2 = st.tabs(["🏟️ Équipes", "👥 Joueurs"])
    with tab1:
        render_clubs(season, league)
    with tab2:
        render_players(season, league)


# ── Watchlist ────────────────────────────────────────────────────────────────

# Fonctionnalité watchlist supprimée sur demande utilisateur.
