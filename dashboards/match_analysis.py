"""
Dashboard Analyse Match.
Calendrier, forme récente, évolution des métriques match par match.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import COLORS, LEAGUE_LABELS, PLOTLY_LAYOUT
from components.charts import make_form_strip, make_line, make_scatter
from components.filters import select_team
from components.glossary import render_disclaimer
from components.kpi_cards import render_kpi_row, render_section_header
from data.loader import load_team_match_stats, load_player_season_stats
from data.processor import (
    compute_form, compute_match_ratings, top_bottom_matches,
    split_team_by_venue, split_player_by_venue,
)

try:
    from transfermarkt.matcher import get_club_logo, enrich_with_logos
    TM_AVAILABLE = True
except Exception:
    TM_AVAILABLE = False
    def get_club_logo(*a, **kw): return None
    def enrich_with_logos(df, *a, **kw): return df


# ── Helpers ───────────────────────────────────────────────────────────────────

RESULT_EMOJI = {"W": "✅", "D": "🟡", "L": "❌"}


def _schedule_for_team(season: str, league: str | None, team: str) -> pd.DataFrame:
    df = load_team_match_stats("schedule", [season])
    if league:
        df = df[df["league"] == league]
    df = df[df["team"] == team].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)
    return df


def _season_summary(df: pd.DataFrame) -> dict:
    played = df[df["result"].notna()]
    W = (played["result"] == "W").sum()
    D = (played["result"] == "D").sum()
    L = (played["result"] == "L").sum()
    gf = pd.to_numeric(played["GF"], errors="coerce").sum()
    ga = pd.to_numeric(played["GA"], errors="coerce").sum()
    pts = W * 3 + D
    return {"W": int(W), "D": int(D), "L": int(L),
            "GF": int(gf), "GA": int(ga), "Pts": int(pts)}


# ── Render ────────────────────────────────────────────────────────────────────

def render(season: str, league: str) -> None:
    league_filter = None if league == "Toutes les ligues" else league

    st.markdown(
        f"<h2 style='color:{COLORS['text']};margin-bottom:0'>📅 Analyse Match</h2>"
        f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;margin-bottom:14px'>"
        f"Calendrier, forme et évolution match par match · "
        f"{LEAGUE_LABELS.get(league_filter, league_filter or 'Big 5')} · {season}</div>",
        unsafe_allow_html=True,
    )

    team = select_team(season, league, label="Équipe", key="team_ctx")
    if not team:
        return

    df = _schedule_for_team(season, league_filter, team)

    if df.empty:
        st.warning(f"Aucun match trouvé pour **{team}** ({season}).")
        return

    logo_url = get_club_logo(team, league_filter)
    if logo_url:
        c1, c2 = st.columns([1, 11])
        with c1:
            st.image(logo_url, width=56)
        with c2:
            st.markdown(
                f"<div style='padding:10px 0 0 0'>"
                f"<span style='font-size:1.4rem;font-weight:800;color:{COLORS['text']}'>{team}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            f"<div style='padding:6px 0'>"
            f"<span style='font-size:1.35rem;font-weight:800;color:{COLORS['text']}'>🏟️ {team}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Bilan saison ──────────────────────────────────────────────────────────
    summary = _season_summary(df)
    render_kpi_row([
        {"label": "Points",          "value": str(summary["Pts"]),  "color": COLORS["accent_green"]},
        {"label": "V / N / D",       "value": f"{summary['W']} / {summary['D']} / {summary['L']}",
         "color": COLORS["accent_blue"]},
        {"label": "Buts marqués",    "value": str(summary["GF"]),   "color": COLORS["accent_gold"]},
        {"label": "Buts encaissés",  "value": str(summary["GA"]),   "color": COLORS["accent_red"]},
    ])

    st.divider()

    # ── Forme récente ─────────────────────────────────────────────────────────
    n_form = st.slider("Matchs récents (forme)", 3, 10, 5, key="form_n")
    results = df[df["result"].notna()]["result"].tolist()[-n_form:]
    render_section_header("Forme récente", f"{n_form} derniers matchs")
    fig_form = make_form_strip(results, team)
    st.plotly_chart(fig_form, use_container_width=True)

    st.divider()

    tab1, tab2, tab3, tab_home, tab_player = st.tabs([
        "📋 Calendrier",
        "📈 Évolution métriques",
        "⚽ xG vs xGA",
        "🏠 Domicile / Extérieur",
        "📊 Rapports de match (joueur)",
    ])

    # ── Tab 1 : Calendrier ────────────────────────────────────────────────────
    with tab1:
        render_section_header("Matchs joués")

        show_cols = ["date", "opponent", "venue", "result", "GF", "GA", "xG", "xGA", "Poss", "Formation"]
        available = [c for c in show_cols if c in df.columns]
        disp = df[available].copy()

        # Logo de l'adversaire
        if "opponent" in disp.columns:
            disp = enrich_with_logos(
                disp.rename(columns={"opponent": "team"}),
                team_col="team", league=league_filter, out_col="opp_logo",
            ).rename(columns={"team": "opponent"})

        # Formatage
        if "date" in disp.columns:
            disp["date"] = disp["date"].dt.strftime("%d/%m/%Y")
        if "result" in disp.columns:
            disp["result"] = disp["result"].map(lambda r: RESULT_EMOJI.get(str(r), r))

        # Réordonner : logo juste avant le nom adversaire
        if "opp_logo" in disp.columns:
            cols = list(disp.columns)
            cols.remove("opp_logo")
            opp_idx = cols.index("opponent")
            cols.insert(opp_idx, "opp_logo")
            disp = disp[cols]

        column_config = {}
        if "opp_logo" in disp.columns:
            column_config["opp_logo"] = st.column_config.ImageColumn("", width="small")

        st.dataframe(
            disp, use_container_width=True, hide_index=True, column_config=column_config,
        )

    # ── Tab 2 : Évolution métriques ───────────────────────────────────────────
    with tab2:
        render_section_header("Évolution match par match")

        numeric_cols = [c for c in ["xG", "xGA", "Poss", "GF", "GA"]
                        if c in df.columns and df[c].notna().any()]

        if not numeric_cols:
            st.info("Métriques insuffisantes dans les données de schedule.")
        else:
            chosen = st.multiselect(
                "Métriques à afficher",
                numeric_cols,
                default=numeric_cols[:2],
                key="match_metrics",
            )
            if chosen:
                plot_df = df[["date"] + chosen].dropna(subset=["date"])
                plot_df = plot_df.sort_values("date")
                for c in chosen:
                    plot_df[c] = pd.to_numeric(plot_df[c], errors="coerce")

                fig = make_line(
                    plot_df, "date", chosen,
                    title=f"Évolution — {team}",
                    smooth=True,
                )
                st.plotly_chart(fig, use_container_width=True)

    # ── Tab 3 : xG rolling ───────────────────────────────────────────────────
    with tab3:
        render_section_header(
            "xG vs xGA",
            "Chaque point = 1 match. Au-dessus de la diagonale = performance offensive > défensive.",
        )

        xg_df = df[["date", "opponent", "venue", "result", "xG", "xGA"]].copy()
        for c in ["xG", "xGA"]:
            xg_df[c] = pd.to_numeric(xg_df[c], errors="coerce")
        xg_df = xg_df.dropna(subset=["xG", "xGA"])

        if xg_df.empty:
            st.info("Pas de données xG/xGA disponibles.")
        else:
            fig = make_scatter(
                xg_df, "xG", "xGA",
                text="opponent",
                title=f"{team} — xG vs xGA par match",
                xlab="xG (créé)", ylab="xGA (concédé)",
                highlight=xg_df["opponent"].tolist(),
            )
            # Ligne de parité
            import plotly.graph_objects as go
            lim = max(xg_df["xG"].max(), xg_df["xGA"].max()) + 0.3
            fig.add_shape(
                type="line", x0=0, y0=0, x1=lim, y1=lim,
                line=dict(color=COLORS["text_muted"], width=1, dash="dash"),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Tab : Isolation Domicile/Extérieur ───────────────────────────────────
    with tab_home:
        _render_home_away(team, season, league_filter)

    # ── Tab : Rapports de match (joueur) ─────────────────────────────────────
    with tab_player:
        _render_player_match_reports(team, season, league_filter)

    render_disclaimer()


# ── Isolation Domicile / Extérieur ────────────────────────────────────────────

def _render_home_away(team: str, season: str, league_f: str | None) -> None:
    render_section_header(
        "Isolation des performances par lieu",
        "Compare la production de l'équipe à domicile et à l'extérieur.",
    )

    split = split_team_by_venue(team, season, league_f)
    if split.empty:
        st.info("Pas de données de calendrier disponibles pour ce split.")
        return

    cols_show = [c for c in ["venue", "J", "V", "N", "D", "BP", "BC",
                              "xG", "xGA", "±xG", "Pts"] if c in split.columns]
    disp = split[cols_show].rename(columns={"venue": "Lieu"})

    column_config = {}
    for c in ["xG", "xGA", "±xG"]:
        if c in disp.columns:
            column_config[c] = st.column_config.NumberColumn(c, format="%.1f")

    st.dataframe(disp, hide_index=True, use_container_width=True,
                 column_config=column_config)

    # Visuel : barres comparées
    if {"venue", "Pts", "BP", "BC"}.issubset(split.columns):
        import plotly.graph_objects as go
        fig = go.Figure()
        for col, color in [("Pts", COLORS["accent_green"]),
                           ("BP",  COLORS["accent_gold"]),
                           ("BC",  COLORS["accent_red"])]:
            if col in split.columns:
                fig.add_trace(go.Bar(
                    name=col, x=split["venue"], y=split[col],
                    marker_color=color,
                    text=split[col], textposition="outside",
                    textfont=dict(color=COLORS["text"]),
                ))
        layout = {**PLOTLY_LAYOUT}
        layout["margin"] = dict(l=20, r=20, t=30, b=20)
        fig.update_layout(
            **layout,
            barmode="group",
            xaxis=dict(tickfont=dict(size=12)),
            yaxis=dict(gridcolor=COLORS["grid"]),
            height=320,
        )
        st.plotly_chart(fig, use_container_width=True)


# ── Rapports de match joueur (note /10) ──────────────────────────────────────

def _render_player_match_reports(team: str, season: str, league_f: str | None) -> None:
    render_section_header(
        "Notes par match — joueur de l'équipe",
        "Note sur 10 calculée à partir des actions positives (Gls, Ast, KP, Tkl, Int…) "
        "et négatives (cartons, fautes, erreurs). Standardisée sur la saison du joueur.",
    )

    pdf = load_player_season_stats("standard", [season])
    if league_f:
        pdf = pdf[pdf["league"] == league_f]
    pdf = pdf[pdf["team"] == team]
    if pdf.empty:
        st.info("Pas de joueurs trouvés pour cette équipe.")
        return

    players = sorted(pdf["player"].dropna().unique().tolist())
    chosen = st.selectbox("Joueur", players, key="ma_player")

    if not chosen:
        return

    ratings = compute_match_ratings(chosen, team, season, league_f)
    if ratings.empty:
        st.warning(
            "Pas de données match-level pour ce joueur sur cette saison "
            "(vérifier `FB_player_match_stats_summary.csv`)."
        )
        return

    # KPIs : moyenne, écart-type, meilleur match, pire match
    avg = float(ratings["note"].mean())
    best = float(ratings["note"].max())
    worst = float(ratings["note"].min())
    n_matchs = len(ratings)

    render_kpi_row([
        {"label": "Note moyenne", "value": f"{avg:.2f}/10",
         "color": COLORS["accent_green"]},
        {"label": "Meilleur match", "value": f"{best:.1f}",
         "color": COLORS["accent_blue"]},
        {"label": "Pire match", "value": f"{worst:.1f}",
         "color": COLORS["accent_red"]},
        {"label": "Matchs notés", "value": str(n_matchs),
         "color": COLORS["text_muted"]},
    ])

    # ── Top 3 / Bottom 3 ────────────────────────────────────────────────────
    tb = top_bottom_matches(ratings, n=3)
    cA, cB = st.columns(2)

    def _disp_short(df_in: pd.DataFrame) -> pd.DataFrame:
        d = df_in.copy()
        if "date" in d.columns:
            d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.strftime("%d/%m/%Y")
        d = d.rename(columns={
            "date": "Date", "opponent": "Adversaire", "venue": "Lieu",
            "result": "R", "note": "Note",
            "pos_actions": "Actions +", "neg_actions": "Actions -",
        })
        d = enrich_with_logos(d.rename(columns={"Adversaire": "team"}),
                              team_col="team", league=league_f,
                              out_col="opp_logo").rename(columns={"team": "Adversaire"})
        keep = [c for c in ["Date", "opp_logo", "Adversaire", "Lieu", "R",
                            "Note", "Actions +", "Actions -"] if c in d.columns]
        return d[keep]

    with cA:
        st.markdown(f"<div style='color:{COLORS['accent_green']};font-weight:700'>"
                    f"⭐ 3 meilleures performances</div>", unsafe_allow_html=True)
        top = _disp_short(tb["top"])
        cfg = {}
        if "opp_logo" in top.columns:
            cfg["opp_logo"] = st.column_config.ImageColumn("", width="small")
        if "Note" in top.columns:
            cfg["Note"] = st.column_config.NumberColumn("Note", format="%.1f")
        st.dataframe(top, hide_index=True, use_container_width=True, column_config=cfg)
    with cB:
        st.markdown(f"<div style='color:{COLORS['accent_red']};font-weight:700'>"
                    f"❌ 3 moins bonnes performances</div>", unsafe_allow_html=True)
        bot = _disp_short(tb["bottom"])
        cfg = {}
        if "opp_logo" in bot.columns:
            cfg["opp_logo"] = st.column_config.ImageColumn("", width="small")
        if "Note" in bot.columns:
            cfg["Note"] = st.column_config.NumberColumn("Note", format="%.1f")
        st.dataframe(bot, hide_index=True, use_container_width=True, column_config=cfg)

    # ── Évolution chronologique des notes ────────────────────────────────────
    st.divider()
    render_section_header("Courbe des notes", "Match par match dans l'ordre chronologique.")
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ratings["date"], y=ratings["note"],
        mode="lines+markers",
        marker=dict(
            size=10,
            color=[
                COLORS["accent_green"] if n >= 7 else
                COLORS["accent_gold"]  if n >= 5 else
                COLORS["accent_red"]
                for n in ratings["note"]
            ],
            line=dict(color="#fff", width=1),
        ),
        line=dict(color=COLORS["accent_blue"], width=2),
        text=ratings.get("opponent", ""),
        hovertemplate="%{x|%d/%m/%Y}<br>vs %{text}<br>Note : %{y:.1f}/10<extra></extra>",
    ))
    # Bandes seuils
    fig.add_shape(type="line", x0=ratings["date"].min(), x1=ratings["date"].max(),
                  y0=5, y1=5, line=dict(color=COLORS["text_muted"], dash="dash", width=1))
    layout = {**PLOTLY_LAYOUT}
    layout["margin"] = dict(l=20, r=20, t=20, b=30)
    fig.update_layout(
        **layout,
        yaxis=dict(range=[0, 10], gridcolor=COLORS["grid"], title="Note /10"),
        xaxis=dict(gridcolor=COLORS["grid"], title=""),
        height=340, showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Split domicile/extérieur du joueur ───────────────────────────────────
    split = split_player_by_venue(chosen, team, season, league_f)
    if not split.empty:
        st.divider()
        render_section_header(
            "Domicile vs Extérieur",
            "Production statistique du joueur selon le lieu du match.",
        )
        cols = [c for c in ["venue", "Matchs", "Gls", "Ast", "xG", "xAG", "Sh", "SoT", "note"]
                if c in split.columns]
        disp = split[cols].rename(columns={"venue": "Lieu", "note": "Note moy."})
        cfg = {}
        for c in ["xG", "xAG", "Note moy."]:
            if c in disp.columns:
                cfg[c] = st.column_config.NumberColumn(c, format="%.2f")
        st.dataframe(disp, hide_index=True, use_container_width=True,
                     column_config=cfg)
