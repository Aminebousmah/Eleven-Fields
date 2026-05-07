"""
Dashboard Tendances.
Auto-surface les patterns intéressants : sur/sous-performeurs xG,
jeunes à fort impact, styles atypiques, comparaison inter-saisons.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from config import COLORS, LEAGUE_LABELS, CLUSTER_NAMES, SEASONS
from components.flags import get_flag_url
from components.kpi_cards import render_section_header, render_kpi_row
from components.charts import make_peer_scatter, make_bar_comparison
from data.loader import load_team_season_stats, load_player_season_stats
from data.processor import (
    find_xg_outliers, find_defensive_outliers, find_young_stars,
    find_style_outliers,
)

try:
    from transfermarkt.matcher import enrich_with_logos, enrich_with_photos, format_value
    TM_AVAILABLE = True
except Exception:
    TM_AVAILABLE = False
    def enrich_with_logos(df, *a, **kw): return df
    def enrich_with_photos(df, *a, **kw): return df
    def format_value(v): return "—"


def _logo_cfg(): return st.column_config.ImageColumn("Logo", width="small")
def _photo_cfg(): return st.column_config.ImageColumn("Photo", width="small")


def _show_team_table(df, league, cols_after_logo, **fmt) -> None:
    """Helper : injecte logo_url + affiche en dataframe avec ImageColumn."""
    if df is None or df.empty:
        return
    df = enrich_with_logos(df, team_col="team", league=league)
    show = ["logo_url", "team"] + [c for c in cols_after_logo if c in df.columns]
    show = [c for c in show if c in df.columns]
    rename = {"logo_url": "Logo", "team": "Équipe"}
    column_config = {"Logo": _logo_cfg()} if "logo_url" in df.columns else {}
    st.dataframe(
        df[show].rename(columns=rename),
        hide_index=True, use_container_width=True, column_config=column_config,
    )


def render(season: str, league: str) -> None:
    league_f = None if league == "Toutes les ligues" else league

    st.markdown(
        f"<h2 style='color:{COLORS['text']};margin-bottom:0'>🔥 Tendances</h2>"
        f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;margin-bottom:16px'>"
        f"Patterns & insights auto-détectés · {LEAGUE_LABELS.get(league, league)} · {season}</div>",
        unsafe_allow_html=True,
    )

    t1, t2, t3, t4 = st.tabs([
        "🎯 xG over/underperformers",
        "🌟 Jeunes talents",
        "🧠 Styles atypiques",
        "📈 Évolution inter-saisons",
    ])

    # ── Tab 1 : xG Over/Under ─────────────────────────────────────────────────
    with t1:
        render_section_header(
            "Qui sur-performe ou sous-performe sur ses xG ?",
            "Écart entre buts marqués et xG attendu — indicateur de clinique ou de finition manquée.",
        )

        outliers = find_xg_outliers(season, league_f, top_n=5)
        c1, c2 = st.columns(2)

        with c1:
            st.markdown(f"<div style='color:{COLORS['accent_green']};font-weight:700'>✅ Surperformeurs</div>",
                        unsafe_allow_html=True)
            if not outliers["over"].empty:
                _small_bar(outliers["over"], "team", "Gls-xG", COLORS["accent_green"])
                _show_team_table(outliers["over"], league_f, ["Gls", "xG", "Gls-xG"])
            else:
                st.info("Données indisponibles.")

        with c2:
            st.markdown(f"<div style='color:{COLORS['accent_red']};font-weight:700'>❌ Sous-performeurs</div>",
                        unsafe_allow_html=True)
            if not outliers["under"].empty:
                _small_bar(outliers["under"], "team", "Gls-xG", COLORS["accent_red"])
                _show_team_table(outliers["under"], league_f, ["Gls", "xG", "Gls-xG"])
            else:
                st.info("Données indisponibles.")

        # Scatter global
        st.divider()
        render_section_header(
            "xG vs Buts — toutes les équipes",
            "Points au-dessus de la diagonale = surperformance, en-dessous = sous-performance.",
        )
        _xg_vs_goals_scatter(season, league_f)

        # Défense : over/under
        st.divider()
        render_section_header(
            "Meilleures / pires défenses",
            "Classement direct par buts encaissés.",
        )
        def_out = find_defensive_outliers(season, league_f, top_n=5)
        c3, c4 = st.columns(2)
        with c3:
            st.markdown(f"<div style='color:{COLORS['accent_green']};font-weight:700'>🛡️ Meilleures défenses</div>",
                        unsafe_allow_html=True)
            _show_team_table(def_out["best"], league_f, ["league", "GA"])
        with c4:
            st.markdown(f"<div style='color:{COLORS['accent_red']};font-weight:700'>🔓 Pires défenses</div>",
                        unsafe_allow_html=True)
            _show_team_table(def_out["worst"], league_f, ["league", "GA"])

    # ── Tab 2 : Jeunes talents ────────────────────────────────────────────────
    with t2:
        render_section_header(
            "Jeunes à fort impact",
            "Joueurs U21 avec le plus de buts + passes décisives + xAG/2 (min. 900 minutes).",
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            max_age = st.slider("Âge max.", 17, 25, 21, key="trends_age")
        with c2:
            min_min = st.slider("Minutes min.", 300, 3000, 900, 100, key="trends_min")
        with c3:
            top_n = st.slider("Top N", 5, 30, 15, key="trends_topn")

        young = find_young_stars(season, league_f, max_age=max_age,
                                  min_minutes=min_min, top_n=top_n)
        if young.empty:
            st.info("Pas de données suffisantes.")
        else:
            young = enrich_with_photos(young, player_col="player", league=league_f)
            young = enrich_with_logos(young, team_col="team", league=league_f)

            # Colonne drapeau : URL image via flagcdn.com
            if "nation" in young.columns:
                young["flag_url"] = young["nation"].apply(
                    lambda x: get_flag_url(str(x).split()[-1], size=20) if pd.notna(x) and str(x).strip() else None
                )

            order = []
            if "image_url" in young.columns: order.append("image_url")
            order += ["player"]
            if "flag_url" in young.columns: order.append("flag_url")
            if "logo_url" in young.columns: order.append("logo_url")
            order += ["team", "league", "age", "pos", "Gls", "Ast", "xG", "xAG", "impact"]
            cols = [c for c in order if c in young.columns]

            disp = young[cols].rename(columns={
                "image_url": "Photo", "logo_url": "Logo",
                "flag_url": "Pays",
                "player": "Joueur", "team": "Équipe", "league": "Ligue",
                "age": "Âge", "pos": "Position",
                "Gls": "Buts", "Ast": "Passes D.",
                "impact": "Score impact",
            })
            column_config = {}
            if "Photo" in disp.columns: column_config["Photo"] = _photo_cfg()
            if "Logo" in disp.columns: column_config["Logo"] = _logo_cfg()
            if "Pays" in disp.columns:
                column_config["Pays"] = st.column_config.ImageColumn("Pays", width="small")
            if "Score impact" in disp.columns:
                column_config["Score impact"] = st.column_config.NumberColumn(
                    "Score impact", format="%.2f",
                )
            st.dataframe(
                disp, hide_index=True, use_container_width=True,
                column_config=column_config,
                height=min(60 * len(disp) + 50, 720),
            )

    # ── Tab 3 : Styles atypiques ──────────────────────────────────────────────
    with t3:
        render_section_header(
            "Équipes au style le plus atypique",
            "Distance euclidienne au centre de leur cluster de style — une équipe "
            "atypique est à la fois caractéristique ET distincte.",
        )

        style = find_style_outliers(season, league_f, top_n=10)
        if style.empty:
            st.info("Pas assez de données pour cette analyse.")
        else:
            style["Style"] = style["cluster"].map(lambda c: CLUSTER_NAMES.get(c, f"Cluster {c}"))
            style = enrich_with_logos(style, team_col="team", league=league_f)
            order = []
            if "logo_url" in style.columns: order.append("logo_url")
            order += ["team", "league", "Style", "distance"]
            disp = style[[c for c in order if c in style.columns]].rename(columns={
                "logo_url": "Logo", "team": "Équipe", "league": "Ligue",
                "distance": "Distance au centre",
            })
            column_config = {}
            if "Logo" in disp.columns: column_config["Logo"] = _logo_cfg()
            column_config["Distance au centre"] = st.column_config.NumberColumn(
                "Distance au centre", format="%.2f",
            )
            st.dataframe(
                disp, hide_index=True, use_container_width=True,
                column_config=column_config,
                height=min(48 * len(disp) + 50, 600),
            )

            st.caption("💡 Plus la distance est grande, plus le style de jeu est unique dans la ligue.")

    # ── Tab 4 : Évolution inter-saisons ───────────────────────────────────────
    with t4:
        render_section_header(
            "Comparaison inter-saisons",
            "Qui progresse le plus d'une saison à l'autre ?",
        )

        if len(SEASONS) < 2:
            st.info("Il faut au moins 2 saisons pour comparer.")
        else:
            c1, c2 = st.columns(2)
            season_keys = list(SEASONS.keys())
            with c1:
                s_prev = st.selectbox("Saison précédente", season_keys,
                                       index=0, key="trends_prev")
            with c2:
                s_curr = st.selectbox("Saison courante", season_keys,
                                       index=len(season_keys) - 1, key="trends_curr")

            if s_prev == s_curr:
                st.warning("Choisissez deux saisons différentes.")
            else:
                _season_evolution(s_prev, s_curr, league_f)


# ── Helpers internes ──────────────────────────────────────────────────────────

def _small_bar(df: pd.DataFrame, x: str, y: str, color: str) -> None:
    """Mini bar chart horizontal."""
    import plotly.graph_objects as go
    from config import PLOTLY_LAYOUT
    fig = go.Figure(go.Bar(
        x=df[y], y=df[x],
        orientation="h",
        marker_color=color,
        text=[f"{v:+.2f}" for v in df[y]],
        textposition="outside",
    ))
    layout = {**PLOTLY_LAYOUT}
    layout["margin"] = dict(l=10, r=40, t=10, b=20)
    fig.update_layout(
        **layout,
        yaxis=dict(autorange="reversed"),
        height=220,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _xg_vs_goals_scatter(season: str, league: str | None) -> None:
    """Scatter xG vs Buts."""
    import plotly.graph_objects as go
    from config import PLOTLY_LAYOUT

    std = load_team_season_stats("standard", [season])
    sht = load_team_season_stats("shooting", [season])
    if league and league != "Toutes les ligues":
        std = std[std["league"] == league]
        sht = sht[sht["league"] == league]

    m = std[["team", "Gls"]].merge(sht[["team", "xG"]], on="team", how="inner")
    m["Gls"] = pd.to_numeric(m["Gls"], errors="coerce")
    m["xG"] = pd.to_numeric(m["xG"], errors="coerce")
    m = m.dropna()

    if m.empty:
        st.info("Données indisponibles.")
        return

    m["diff"] = m["Gls"] - m["xG"]
    colors = [COLORS["accent_green"] if d > 0 else COLORS["accent_red"] for d in m["diff"]]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=m["xG"], y=m["Gls"],
        mode="markers+text",
        text=m["team"],
        textposition="top center",
        textfont=dict(color=COLORS["text"], size=10),
        marker=dict(color=colors, size=10, line=dict(color=COLORS["border"], width=1)),
        hovertemplate="<b>%{text}</b><br>xG: %{x:.1f}<br>Buts: %{y}<extra></extra>",
    ))
    # Diagonale
    lim = max(m["xG"].max(), m["Gls"].max()) + 2
    fig.add_shape(type="line", x0=0, y0=0, x1=lim, y1=lim,
                  line=dict(color=COLORS["text_muted"], width=1, dash="dash"))

    fig.update_layout(
        **PLOTLY_LAYOUT,
        xaxis=dict(title="xG", gridcolor=COLORS["grid"]),
        yaxis=dict(title="Buts", gridcolor=COLORS["grid"]),
        height=500,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _season_evolution(s_prev: str, s_curr: str, league: str | None) -> None:
    """Comparaison xG, Pts (proxy), possession entre deux saisons."""
    metrics = [
        ("shooting", "xG", "xG"),
        ("standard", "Poss", "Possession"),
        ("goal_shot_creation", "SCA", "SCA"),
        ("defense", "Tkl", "Tacles"),
    ]

    # Récupère Gls depuis standard
    std_prev = load_team_season_stats("standard", [s_prev])
    std_curr = load_team_season_stats("standard", [s_curr])
    if league and league != "Toutes les ligues":
        std_prev = std_prev[std_prev["league"] == league]
        std_curr = std_curr[std_curr["league"] == league]

    # Teams communes
    common = sorted(set(std_prev["team"]).intersection(set(std_curr["team"])))
    if not common:
        st.info("Aucune équipe commune aux deux saisons (changements de ligue ?).")
        return

    metric_choice = st.selectbox(
        "Métrique à comparer",
        [m[2] for m in metrics],
        key="trends_metric",
    )
    st_type, col, label = next(m for m in metrics if m[2] == metric_choice)

    df_prev = load_team_season_stats(st_type, [s_prev])
    df_curr = load_team_season_stats(st_type, [s_curr])
    if league and league != "Toutes les ligues":
        df_prev = df_prev[df_prev["league"] == league]
        df_curr = df_curr[df_curr["league"] == league]

    if col not in df_prev.columns or col not in df_curr.columns:
        st.warning(f"Colonne {col} manquante.")
        return

    dp = df_prev[df_prev["team"].isin(common)][["team", col]].rename(columns={col: s_prev})
    dc = df_curr[df_curr["team"].isin(common)][["team", col]].rename(columns={col: s_curr})
    m = dp.merge(dc, on="team", how="inner")
    for c in [s_prev, s_curr]:
        m[c] = pd.to_numeric(m[c], errors="coerce")
    m["Δ"] = m[s_curr] - m[s_prev]
    m = m.dropna().sort_values("Δ", ascending=False)

    # Top/Bottom progresseurs
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"<div style='color:{COLORS['accent_green']};font-weight:700'>📈 Plus grosses progressions</div>",
                    unsafe_allow_html=True)
        top = m.head(5)
        _small_bar(top, "team", "Δ", COLORS["accent_green"])
    with c2:
        st.markdown(f"<div style='color:{COLORS['accent_red']};font-weight:700'>📉 Plus grosses régressions</div>",
                    unsafe_allow_html=True)
        bot = m.tail(5).sort_values("Δ")
        _small_bar(bot, "team", "Δ", COLORS["accent_red"])

    st.divider()
    render_section_header(f"Tableau complet — {label}")
    disp = m.rename(columns={"team": "Équipe"})
    styled = disp.style.format(precision=2, na_rep="—").background_gradient(
        subset=["Δ"], cmap="RdYlGn", vmin=-m["Δ"].abs().max(), vmax=m["Δ"].abs().max()
    )
    st.dataframe(styled, hide_index=True, use_container_width=True)
