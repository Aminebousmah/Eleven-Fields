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
from components.design import (
    card_open, card_close, pct_color_css, pos_class, badge,
)
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
    """Comparaison de 2 joueurs : filter rail horizontal + duel."""
    league_filter = None if league == "Toutes les ligues" else league

    if True:
        from config import COMPARISON_PRESETS
        from components.filters import (
            render_show_gate, select_two_players_compact,
        )

        comp_options = ["Auto"] + list(COMPARISON_PRESETS.keys())

        # ── Filter rail horizontal compact (style design) ────────────────────
        # 3 zones : Joueur A | Joueur B | Type de comparaison
        st.markdown(
            '<div style="display:flex;align-items:center;gap:6px;'
            'padding:10px 12px;margin-bottom:10px;border-radius:10px;'
            'background:var(--bg-1);border:1px solid var(--line-faint)">'
            '<span style="font-size:9.5px;letter-spacing:.14em;'
            'text-transform:uppercase;color:var(--ink-3);margin-right:8px">'
            'Joueurs à comparer</span></div>',
            unsafe_allow_html=True,
        )

        (p1, t1), (p2, t2) = select_two_players_compact(season, league)

        if not (p1 and p2):
            st.info("Sélectionnez deux joueurs.")
            render_disclaimer()
            return

        # Sélecteur Type — sur sa propre ligne, plus visible
        comp_type = st.selectbox(
            "Type de comparaison",
            options=comp_options,
            key="cmp_type",
            help="Auto = métriques selon le poste du joueur 1. Sinon, set pré-câblé.",
        )

        # Gate avec empty state animée
        if not render_show_gate(
            "compare_players",
            label="⚔️  Lancer la comparaison",
            primary_text="Configure ton duel",
            hint=(f"{p1} vs {p2} · type : {comp_type}. "
                  f"Le duel produit un radar overlay et un tableau coloré "
                  f"(vert = meilleur, rouge = pire)."),
            icon="⚔",
        ):
            render_disclaimer()
            return

        # Re-map "Auto" → "Auto (par poste)" pour compat avec le code existant
        if comp_type == "Auto":
            comp_type = "Auto (par poste)"

        # Charger pdf seulement maintenant qu'on va générer
        pdf = load_player_season_stats("standard", [season])
        if league_filter:
            pdf = pdf[pdf["league"] == league_filter]

        if True:
            # ── Calcul positions + métriques ─────────────────────────────────
            row1 = pdf[(pdf["player"] == p1) & (pdf["team"] == t1)]
            pos1 = _pos_group(row1["pos"].values[0] if not row1.empty else "MF")
            row2 = pdf[(pdf["player"] == p2) & (pdf["team"] == t2)]
            pos2 = _pos_group(row2["pos"].values[0] if not row2.empty else "MF")

            if comp_type == "Auto (par poste)":
                if pos1 != pos2:
                    st.warning(
                        f"⚠️ Positions différentes : {p1} ({pos1}) vs {p2} ({pos2}). "
                        f"La comparaison utilise les métriques du poste de **{p1}**."
                    )
                metrics_raw = PLAYER_METRICS_BY_POS.get(pos1, PLAYER_METRICS_BY_POS["MF"])
                metric_labels_fr = None
            else:
                preset = COMPARISON_PRESETS[comp_type]
                metrics_raw = [(stat_type, col) for _, stat_type, col in preset]
                metric_labels_fr = {col: label for label, _, col in preset}

            ref_pos = pos1
            l1, p_pct1, r1 = _player_percentiles(p1, t1, metrics_raw, season, league_filter, ref_pos)
            l2, p_pct2, r2 = _player_percentiles(p2, t2, metrics_raw, season, league_filter, ref_pos)

            common = [l for l in l1 if l in l2]
            if not common:
                st.warning("Pas de métriques communes pour ces joueurs.")
                return

            display_labels = (
                [metric_labels_fr.get(c, c) for c in common]
                if metric_labels_fr else common
            )
            idx1 = {l: i for i, l in enumerate(l1)}
            idx2 = {l: i for i, l in enumerate(l2)}

            # Calcul des victoires (qui a le meilleur percentile sur chaque métrique)
            wins_a = sum(1 for l in common if p_pct1[idx1[l]] > p_pct2[idx2[l]])
            wins_b = sum(1 for l in common if p_pct2[idx2[l]] > p_pct1[idx1[l]])

            # ── Versus row : 2 cartes miroir + score central ─────────────────
            _render_versus_row(p1, t1, p2, t2, league_filter, season,
                                comp_type, wins_a, wins_b, len(common))

            # ── Layout 2 cols : Radar overlay | Lecture rapide ───────────────
            cols_main = st.columns([3, 2], gap="medium")
            with cols_main[0]:
                st.markdown(card_open("Radar overlay · percentiles",
                            actions_html=(
                                f'<span style="color:var(--good);font-size:11px;'
                                f'margin-right:8px">● {p1}</span>'
                                f'<span style="color:var(--bad);font-size:11px">● {p2}</span>'
                            )),
                            unsafe_allow_html=True)
                fig = make_radar(
                    {
                        p1: [p_pct1[idx1[l]] / 100 for l in common],
                        p2: [p_pct2[idx2[l]] / 100 for l in common],
                    },
                    display_labels,
                    title="",
                )
                fig.update_layout(height=460, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                st.markdown(card_close(), unsafe_allow_html=True)

            with cols_main[1]:
                _render_quick_read(
                    p1, p2, common, display_labels,
                    p_pct1, p_pct2, idx1, idx2, r1, r2,
                )

            # ── Tableau pleine largeur : 5 colonnes avec barre de répartition
            _render_compare_table_html(
                p1, p2, common, display_labels,
                p_pct1, p_pct2, idx1, idx2, r1, r2,
            )

            # Glossaire uniquement si métriques FBref (pas FR)
            if metric_labels_fr is None:
                with st.expander("ℹ  Définition des indicateurs", expanded=False):
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


# ════════════════════════════════════════════════════════════════════════════
# REFONTE v2 — Versus Row + Lecture rapide auto (Phase 2.3)
# ════════════════════════════════════════════════════════════════════════════

def _render_versus_row(
    p1: str, t1: str, p2: str, t2: str,
    league_filter: str | None, season: str,
    comp_type: str, wins_a: int, wins_b: int, n_metrics: int,
) -> None:
    """
    Versus row : 2 cartes joueur miroir (A vert / B rouge) + bandeau central
    avec score wins:losses, nombre de métriques, badge type de comparaison.
    Style mockup 2 du design Claude.
    """
    # Récupération info TM pour les 2 joueurs
    tm1 = match_player(p1, fbref_league=league_filter)
    tm2 = match_player(p2, fbref_league=league_filter)

    photo1 = tm1.get("image_url") if tm1 else None
    photo2 = tm2.get("image_url") if tm2 else None

    mv1 = tm1.get("market_value_in_eur") if tm1 else None
    mv2 = tm2.get("market_value_in_eur") if tm2 else None
    mv1_str = format_value(mv1) if mv1 and pd.notna(mv1) else "—"
    mv2_str = format_value(mv2) if mv2 and pd.notna(mv2) else "—"

    # Récupération âge depuis player stats standard
    pdf = load_player_season_stats("standard", [season])
    if league_filter:
        pdf = pdf[pdf["league"] == league_filter]
    age1 = ""
    age2 = ""
    try:
        r1 = pdf[(pdf["player"] == p1) & (pdf["team"] == t1)]
        if not r1.empty:
            age1 = f"{int(float(r1.iloc[0].get('age', 0)))} ans" if pd.notna(r1.iloc[0].get("age")) else ""
        r2 = pdf[(pdf["player"] == p2) & (pdf["team"] == t2)]
        if not r2.empty:
            age2 = f"{int(float(r2.iloc[0].get('age', 0)))} ans" if pd.notna(r2.iloc[0].get("age")) else ""
    except Exception:
        pass

    # 3 colonnes : card A (5) | score central (2) | card B (5)
    cA, cMid, cB = st.columns([5, 2, 5], gap="small")

    # ── Card A (vert) ───────────────────────────────────────────────────────
    with cA:
        photo_html_a = (
            f'<img src="{photo1}" style="width:60px;height:60px;border-radius:50%;'
            f'object-fit:cover;flex:none"/>'
            if photo1
            else '<div style="width:60px;height:60px;border-radius:50%;'
                 'background:var(--bg-3);display:flex;align-items:center;'
                 'justify-content:center;font-size:24px;flex:none">👤</div>'
        )
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:12px;'
            f'padding:14px 16px;border-radius:12px;min-height:90px;'
            f'background:linear-gradient(90deg, color-mix(in oklch, var(--good) 18%, var(--bg-1)) 0%, var(--bg-1) 100%);'
            f'border:1px solid color-mix(in oklch, var(--good) 30%, var(--line-faint))">'
            f'  <div style="font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;'
            f'color:var(--good);writing-mode:vertical-rl;transform:rotate(180deg);'
            f'font-weight:700">Joueur A</div>'
            f'  {photo_html_a}'
            f'  <div style="min-width:0;flex:1">'
            f'    <div style="font-size:17px;font-weight:700;color:var(--ink-0);'
            f'letter-spacing:-.01em">{p1}</div>'
            f'    <div style="font-size:11.5px;color:var(--ink-2);margin-top:3px">'
            f'{t1}{(" · " + age1) if age1 else ""}{(" · " + mv1_str) if mv1_str != "—" else ""}</div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Score central ───────────────────────────────────────────────────────
    with cMid:
        st.markdown(
            f'<div style="display:flex;flex-direction:column;align-items:center;'
            f'justify-content:center;min-height:90px;padding:12px 6px;'
            f'background:var(--bg-0);border-radius:10px;'
            f'border:1px solid var(--line-faint)">'
            f'  <div style="font-size:9.5px;letter-spacing:.18em;'
            f'color:var(--ink-3);text-transform:uppercase;font-weight:600">vs</div>'
            f'  <div style="display:flex;align-items:center;gap:6px;'
            f'margin-top:4px;font-family:ui-monospace,monospace;font-size:24px;'
            f'font-weight:700">'
            f'    <span style="color:var(--good)">{wins_a}</span>'
            f'    <span style="color:var(--ink-4)">:</span>'
            f'    <span style="color:var(--bad)">{wins_b}</span>'
            f'  </div>'
            f'  <div style="font-size:9.5px;color:var(--ink-3);margin-top:2px">'
            f'{n_metrics} métriques</div>'
            f'  <div style="margin-top:6px">'
            f'    <span class="ef-badge solid" style="font-family:ui-monospace,monospace;'
            f'font-size:9px">{comp_type if comp_type != "Auto (par poste)" else "AUTO"}</span>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Card B (rouge) ──────────────────────────────────────────────────────
    with cB:
        photo_html_b = (
            f'<img src="{photo2}" style="width:60px;height:60px;border-radius:50%;'
            f'object-fit:cover;flex:none"/>'
            if photo2
            else '<div style="width:60px;height:60px;border-radius:50%;'
                 'background:var(--bg-3);display:flex;align-items:center;'
                 'justify-content:center;font-size:24px;flex:none">👤</div>'
        )
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:12px;'
            f'padding:14px 16px;border-radius:12px;min-height:90px;'
            f'background:linear-gradient(270deg, color-mix(in oklch, var(--bad) 18%, var(--bg-1)) 0%, var(--bg-1) 100%);'
            f'border:1px solid color-mix(in oklch, var(--bad) 30%, var(--line-faint));'
            f'text-align:right">'
            f'  <div style="min-width:0;flex:1">'
            f'    <div style="font-size:17px;font-weight:700;color:var(--ink-0);'
            f'letter-spacing:-.01em">{p2}</div>'
            f'    <div style="font-size:11.5px;color:var(--ink-2);margin-top:3px">'
            f'{t2}{(" · " + age2) if age2 else ""}{(" · " + mv2_str) if mv2_str != "—" else ""}</div>'
            f'  </div>'
            f'  {photo_html_b}'
            f'  <div style="font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;'
            f'color:var(--bad);writing-mode:vertical-rl;font-weight:700">Joueur B</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)


# ─── Lecture rapide auto-générée (4 insights) ────────────────────────────────

def _render_quick_read(
    p1: str, p2: str,
    common: list[str], display_labels: list[str],
    p_pct1: list[float], p_pct2: list[float],
    idx1: dict[str, int], idx2: dict[str, int],
    r1: list[float], r2: list[float],
) -> None:
    """
    Carte "Lecture rapide" : 4 insights auto extraits des écarts de percentile.
    Chaque insight = (icône, label, texte avec stats en gras, camp gagnant).
    """
    # Calcule l'écart de percentile pour chaque métrique
    diffs = []
    for c, lbl in zip(common, display_labels):
        pa = p_pct1[idx1[c]]
        pb = p_pct2[idx2[c]]
        va = r1[idx1[c]]
        vb = r2[idx2[c]]
        diffs.append({
            "label": lbl, "col": c,
            "pa": pa, "pb": pb,
            "va": va, "vb": vb,
            "abs_diff": abs(pa - pb),
            "winner": p1 if pa > pb else p2,
            "winner_color": "var(--good)" if pa > pb else "var(--bad)",
        })

    # Trier par écart absolu décroissant
    diffs_sorted = sorted(diffs, key=lambda d: d["abs_diff"], reverse=True)
    top_insights = diffs_sorted[:4]

    insights_html = ""
    for d in top_insights:
        # Icône selon le type de métrique
        col_lc = (d["col"] or "").lower()
        if any(k in col_lc for k in ("gls", "g/sh", "sot")):
            icon = "⚽"
            verb = "MEILLEUR FINISSEUR"
        elif any(k in col_lc for k in ("ast", "xag", "kp", "sca", "gca", "ppa", "crspa")):
            icon = "🎯"
            verb = "MEILLEUR CRÉATEUR"
        elif any(k in col_lc for k in ("prgc", "prgr", "succ", "touch")):
            icon = "⚡"
            verb = "DOMINE EN CONDUITE"
        elif any(k in col_lc for k in ("won", "tkl", "int", "blocks", "clr", "recov")):
            icon = "🛡"
            verb = "DOMINE DÉFENSIVEMENT"
        else:
            icon = "📊"
            verb = "DOMINE SUR"

        winner = d["winner"]
        loser = p2 if winner == p1 else p1
        v_win = d["va"] if winner == p1 else d["vb"]
        v_lose = d["vb"] if winner == p1 else d["va"]
        delta = abs(v_win - v_lose)
        win_color = d["winner_color"]

        # Format valeurs : entier si proche d'entier, sinon 2 décimales
        def _fmt(v):
            try:
                vf = float(v)
                if abs(vf - round(vf)) < 0.05 and abs(vf) >= 10:
                    return f"{int(round(vf))}"
                return f"{vf:.2f}"
            except Exception:
                return "—"

        insights_html += (
            f'<div style="display:flex;gap:10px;padding:10px 12px;'
            f'border-left:3px solid {win_color};margin-bottom:8px;'
            f'background:color-mix(in oklch, {win_color} 8%, var(--bg-2));'
            f'border-radius:0 7px 7px 0">'
            f'  <div style="font-size:18px;flex:none">{icon}</div>'
            f'  <div style="min-width:0">'
            f'    <div style="font-size:10px;letter-spacing:.14em;text-transform:uppercase;'
            f'color:{win_color};font-weight:700;margin-bottom:3px">{verb}</div>'
            f'    <div style="font-size:12px;color:var(--ink-1);line-height:1.45">'
            f'{winner} affiche <b style="color:var(--ink-0)">{_fmt(v_win)}</b> sur '
            f'<i>{d["label"]}</i> contre <b>{_fmt(v_lose)}</b> pour {loser} '
            f'(écart percentile : <b style="color:{win_color}">+{int(d["abs_diff"])}</b>).'
            f'    </div>'
            f'  </div>'
            f'</div>'
        )

    st.markdown(
        card_open("Lecture rapide",
                  actions_html='<span style="font-size:10px;color:var(--ink-3)">'
                               'auto-extrait</span>'),
        unsafe_allow_html=True,
    )
    st.markdown(insights_html, unsafe_allow_html=True)
    # Boutons d'action
    st.markdown(
        '<div style="display:flex;gap:8px;margin-top:10px">'
        '<button class="ef-badge" style="cursor:pointer;height:28px;padding:0 12px;'
        'background:var(--bg-2);border:1px solid var(--line)">📸 Snapshot duel</button>'
        '<button class="ef-badge solid" style="cursor:pointer;height:28px;padding:0 12px">'
        '✦ Thread duel (Haiku)</button>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(card_close(), unsafe_allow_html=True)


def _render_compare_table_html(
    p1: str, p2: str,
    common: list[str], display_labels: list[str],
    p_pct1: list[float], p_pct2: list[float],
    idx1: dict[str, int], idx2: dict[str, int],
    r1: list[float], r2: list[float],
) -> None:
    """
    Tableau de comparaison HTML pleine largeur, 5 colonnes :
      MÉTRIQUE · p1 · DIFF · p2 · RÉPARTITION (barre split)
    Cellule du gagnant teintée vert pâle, valeurs colorées vert/rouge,
    bar de répartition proportionnelle aux valeurs absolues.
    """
    def _fmt(v):
        try:
            vf = float(v)
            if abs(vf) >= 100:
                return f"{vf:.0f}"
            if abs(vf - round(vf)) < 0.05 and abs(vf) >= 10:
                return f"{int(round(vf))}"
            return f"{vf:.2f}"
        except Exception:
            return "—"

    rows_html = ""
    for c, lbl in zip(common, display_labels):
        va = r1[idx1[c]]
        vb = r2[idx2[c]]
        try:
            diff = float(va) - float(vb)
        except Exception:
            diff = 0.0

        a_better = va > vb
        equal = (va == vb)

        a_color = "var(--ink-3)" if equal else ("var(--good)" if a_better else "var(--bad)")
        b_color = "var(--ink-3)" if equal else ("var(--bad)" if a_better else "var(--good)")
        a_bg = (
            "color-mix(in oklch, var(--good) 15%, transparent)"
            if a_better and not equal else "transparent"
        )
        b_bg = (
            "color-mix(in oklch, var(--good) 15%, transparent)"
            if not a_better and not equal else "transparent"
        )

        # Couleur du DIFF (vert si A gagne, rouge si B gagne)
        if equal:
            diff_color = "var(--ink-3)"
            diff_str = "0"
        else:
            diff_color = "var(--good)" if a_better else "var(--bad)"
            diff_sign = "+" if diff > 0 else ""
            diff_str = f"{diff_sign}{_fmt(diff)}"

        # Barre de répartition : split au centre, A à gauche / B à droite,
        # tailles proportionnelles aux valeurs absolues.
        try:
            total = abs(float(va)) + abs(float(vb))
        except Exception:
            total = 0
        if total > 0:
            ratio_a = abs(float(va)) / total
            ratio_b = abs(float(vb)) / total
        else:
            ratio_a = ratio_b = 0.5
        bar_html = (
            f'<div style="display:flex;height:8px;width:140px;align-items:stretch">'
            f'  <div style="flex:1;display:flex;justify-content:flex-end;'
            f'background:var(--bg-3);border-radius:3px 0 0 3px;overflow:hidden">'
            f'    <div style="width:{ratio_a*100:.0f}%;background:var(--good)"></div>'
            f'  </div>'
            f'  <div style="flex:1;display:flex;justify-content:flex-start;'
            f'background:var(--bg-3);border-radius:0 3px 3px 0;overflow:hidden">'
            f'    <div style="width:{ratio_b*100:.0f}%;background:var(--bad)"></div>'
            f'  </div>'
            f'</div>'
        )

        rows_html += (
            f'<tr style="border-bottom:1px solid var(--line-faint)">'
            f'  <td style="padding:11px 16px;color:var(--ink-1);font-size:12.5px">'
            f'{lbl}</td>'
            f'  <td style="padding:11px 16px;text-align:right;background:{a_bg};'
            f'color:{a_color};font-family:ui-monospace,monospace;'
            f'font-size:13px;font-weight:600">{_fmt(va)}</td>'
            f'  <td style="padding:11px 16px;text-align:center;color:{diff_color};'
            f'font-family:ui-monospace,monospace;font-size:11px;font-weight:500">'
            f'{diff_str}</td>'
            f'  <td style="padding:11px 16px;text-align:right;background:{b_bg};'
            f'color:{b_color};font-family:ui-monospace,monospace;'
            f'font-size:13px;font-weight:600">{_fmt(vb)}</td>'
            f'  <td style="padding:11px 16px;width:160px">{bar_html}</td>'
            f'</tr>'
        )

    table_html = (
        f'<div style="margin-top:18px">'
        f'<table style="width:100%;border-collapse:collapse;background:var(--bg-1);'
        f'border:1px solid var(--line-faint);border-radius:10px;overflow:hidden">'
        f'  <thead>'
        f'    <tr style="background:var(--bg-2);border-bottom:1px solid var(--line)">'
        f'      <th style="padding:10px 16px;text-align:left;font-size:9.5px;'
        f'letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);'
        f'font-weight:600">Métrique</th>'
        f'      <th style="padding:10px 16px;text-align:right;font-size:9.5px;'
        f'letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);'
        f'font-weight:600">{p1}</th>'
        f'      <th style="padding:10px 16px;text-align:center;font-size:9.5px;'
        f'letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);'
        f'font-weight:600">Diff.</th>'
        f'      <th style="padding:10px 16px;text-align:right;font-size:9.5px;'
        f'letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);'
        f'font-weight:600">{p2}</th>'
        f'      <th style="padding:10px 16px;text-align:center;font-size:9.5px;'
        f'letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);'
        f'font-weight:600">Répartition</th>'
        f'    </tr>'
        f'  </thead>'
        f'  <tbody>{rows_html}</tbody>'
        f'</table>'
        f'</div>'
    )

    st.markdown(table_html, unsafe_allow_html=True)
