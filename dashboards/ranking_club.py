"""
Classement Clubs — style DataScout (carte par équipe).

Indices composites (Créativité, Danger, Progression, Pressing, Récupération,
Possession, Discipline) → classement par score 0-100.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from scipy.stats import percentileofscore

from config import COLORS, LEAGUE_LABELS, PERFORMANCE_INDICES
from data.loader import load_team_season_stats

try:
    from transfermarkt.matcher import get_club_logo
    _TM = True
except Exception:
    _TM = False
    def get_club_logo(*a, **kw): return None


# ── Helpers UI partagés (mêmes que ranking_player) ────────────────────────────

def _score_color(score: float) -> str:
    if score >= 90: return "#00ff99"
    if score >= 75: return "#7cd86b"
    if score >= 60: return "#ffd700"
    if score >= 45: return "#ff9f43"
    return "#ff4655"


def _rank_box_html(rank: int) -> str:
    if rank == 1:   bg, color = COLORS["accent_gold"], "#1a1a2e"
    elif rank == 2: bg, color = "#c5cce0", "#1a1a2e"
    elif rank == 3: bg, color = "#cd853f", "#fff"
    else:           bg, color = COLORS["card"], COLORS["text_muted"]
    return (
        f"<div style='background:{bg};color:{color};border-radius:8px;"
        f"width:46px;height:46px;display:flex;align-items:center;"
        f"justify-content:center;font-weight:900;font-size:0.95rem'>"
        f"#{rank}</div>"
    )


def _score_circle_html(score: float) -> str:
    color = _score_color(score)
    pct = max(0, min(100, int(round(score))))
    bg = COLORS["card"]
    return (
        f"<div style='width:62px;height:62px;border-radius:50%;"
        f"background:conic-gradient({color} 0% {pct}%, {bg} {pct}% 100%);"
        f"display:flex;align-items:center;justify-content:center'>"
        f"<div style='width:48px;height:48px;border-radius:50%;"
        f"background:{COLORS['surface']};display:flex;align-items:center;"
        f"justify-content:center;font-weight:900;font-size:1.1rem;"
        f"color:{color}'>{int(round(score))}</div></div>"
    )


def _badge_html(text: str, accent: str | None = None) -> str:
    bg = accent or COLORS["border"]
    c = COLORS["text"]
    return (
        f"<span style='background:{bg};color:{c};padding:2px 8px;"
        f"border-radius:10px;font-size:0.72rem;font-weight:600;"
        f"margin-right:5px;display:inline-block'>{text}</span>"
    )


def _meta_tag_html(text: str) -> str:
    return (
        f"<span style='color:{COLORS['text_muted']};font-size:0.78rem;"
        f"margin-right:14px'>{text}</span>"
    )


# ── Calcul de l'indice ────────────────────────────────────────────────────────

def _compute_index_score(
    season: str, league_filter: str | None, index_name: str,
) -> pd.DataFrame:
    """Score 0–100 par équipe = moyenne des percentiles des métriques de l'indice."""
    if index_name not in PERFORMANCE_INDICES:
        return pd.DataFrame()

    metrics = PERFORMANCE_INDICES[index_name]
    cache: dict[str, pd.DataFrame] = {}
    base = None
    pct_cols: list[str] = []

    for stat_type, col in metrics:
        if stat_type not in cache:
            df = load_team_season_stats(stat_type, [season])
            if league_filter:
                df = df[df["league"] == league_filter]
            cache[stat_type] = df
        df = cache[stat_type]
        if col not in df.columns:
            continue

        sub = df[["team", "league", col]].copy()
        sub[col] = pd.to_numeric(sub[col], errors="coerce")
        sub = sub.dropna(subset=[col])
        if sub.empty:
            continue

        clean = sub[col]
        sub[f"__pct__{col}"] = sub[col].apply(
            lambda v: percentileofscore(clean, v, kind="rank")
        )
        keep_col = f"__pct__{col}"
        if base is None:
            base = sub[["team", "league", keep_col]].copy()
        else:
            base = base.merge(
                sub[["team", "league", keep_col]],
                on=["team", "league"], how="outer",
            )
        pct_cols.append(keep_col)

    if base is None or not pct_cols:
        return pd.DataFrame()

    base["score"] = base[pct_cols].mean(axis=1).round(1)
    base = base.drop(columns=pct_cols)
    return base.sort_values("score", ascending=False).reset_index(drop=True)


# ── Navigation programmatique vers la fiche équipe ────────────────────────────

def _goto_team_overview(team: str) -> None:
    """Route vers Analyse Club avec l'équipe pré-remplie."""
    st.session_state["mode"] = "club"
    st.session_state["mode_radio"] = "🏟️  Clubs"
    st.session_state["nav_radio"] = "🏟️  Analyse Clubs"
    st.session_state["ctx_team"] = team
    st.session_state["_selected_team"] = team
    st.rerun()


# ── Carte équipe ──────────────────────────────────────────────────────────────

def _render_ranking_card(
    rank: int, row: pd.Series, index_name: str,
    season: str, league_filter: str | None,
) -> None:
    score = float(row.get("score", 0))
    team = row.get("team", "")
    league = row.get("league", "")

    logo_url = get_club_logo(team, league_filter) if _TM else None

    with st.container(border=True):
        c_rank, c_logo, c_info, c_score, c_actions = st.columns([0.6, 0.9, 4.4, 0.8, 1.6])

        with c_rank:
            st.markdown(_rank_box_html(rank), unsafe_allow_html=True)

        with c_logo:
            if logo_url:
                st.image(logo_url, width=60)
            else:
                st.markdown(
                    f"<div style='width:60px;height:60px;border-radius:8px;"
                    f"background:{COLORS['border']};display:flex;align-items:center;"
                    f"justify-content:center;font-size:24px'>🏟️</div>",
                    unsafe_allow_html=True,
                )

        with c_info:
            badges = _badge_html(index_name, COLORS["accent_blue"])
            meta = (
                _meta_tag_html(f"🇪🇺 {LEAGUE_LABELS.get(league, league)}")
            )
            st.markdown(
                f"<div style='display:flex;flex-direction:column;gap:4px'>"
                f"  <div style='font-size:1.05rem;font-weight:700;color:{COLORS['text']}'>"
                f"    {team}"
                f"  </div>"
                f"  <div>{badges}</div>"
                f"  <div style='margin-top:4px'>{meta}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        with c_score:
            st.markdown(_score_circle_html(score), unsafe_allow_html=True)

        with c_actions:
            uid = f"{rank}_{team}".replace(" ", "_")
            radar_key = f"_radar_open_club_{uid}"
            if st.button("📊  Radar",
                         key=f"btn_radar_club_{uid}", use_container_width=True):
                st.session_state[radar_key] = not st.session_state.get(radar_key, False)
            if st.button("→  Voir la fiche",
                         key=f"btn_fiche_club_{uid}", use_container_width=True):
                _goto_team_overview(team)

        # Radar inline (mini : barres des métriques de l'indice)
        if st.session_state.get(f"_radar_open_club_{rank}_{team}".replace(" ", "_")):
            st.divider()
            _render_team_index_breakdown(team, league_filter, index_name, season)


def _render_team_index_breakdown(
    team: str, league_filter: str | None, index_name: str, season: str,
) -> None:
    """Affiche la décomposition de l'indice : valeur + percentile par métrique."""
    metrics = PERFORMANCE_INDICES.get(index_name, [])
    if not metrics:
        return

    rows = []
    for stat_type, col in metrics:
        df = load_team_season_stats(stat_type, [season])
        if league_filter:
            df = df[df["league"] == league_filter]
        if col not in df.columns:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")
        row = df[df["team"] == team]
        if row.empty or pd.isna(row[col].values[0]):
            continue
        val = float(row[col].values[0])
        clean = df[col].dropna()
        if clean.empty:
            continue
        pct = float(percentileofscore(clean, val, kind="rank"))
        rows.append({"Métrique": col, "Valeur": round(val, 2), "Percentile": int(round(pct))})

    if not rows:
        st.info("Pas de décomposition disponible.")
        return

    breakdown = pd.DataFrame(rows)
    st.dataframe(
        breakdown, use_container_width=True, hide_index=True,
        column_config={
            "Percentile": st.column_config.ProgressColumn(
                "Percentile vs ligue", format="%d", min_value=0, max_value=100,
            ),
        },
        height=min(38 * len(breakdown) + 50, 400),
    )


# ── Render principal ──────────────────────────────────────────────────────────

def render(season: str, league: str) -> None:
    league_filter = None if league == "Toutes les ligues" else league

    st.markdown(
        f"<h2 style='color:{COLORS['text']};margin:6px 0 0 0'>🏆 Classement Clubs</h2>"
        f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;margin-bottom:10px'>"
        f"Classement des équipes par indice composite. Score 0–100 = moyenne "
        f"des percentiles vs les autres clubs de la sélection.</div>",
        unsafe_allow_html=True,
    )

    with st.expander("ℹ️  Comment fonctionnent les indices ?", expanded=False):
        st.markdown(
            f"""
- Chaque indice est composé de **plusieurs métriques pondérées équitablement**.
- Le score d'un club = **moyenne des percentiles** de ses métriques par rapport
  à toutes les équipes de la ligue sélectionnée.
- Un score > 75 = équipe dans le top du critère ; < 25 = parmi les plus faibles.
- Le bouton **Radar** déplie la décomposition métrique par métrique avec leur
  percentile individuel.
            """
        )

    st.divider()

    col_filters, col_results = st.columns([1.2, 4], gap="medium")

    with col_filters:
        st.markdown(
            f"<div style='font-weight:700;color:{COLORS['text']};font-size:1rem;"
            f"margin-bottom:8px'>🎚️  Filtres</div>",
            unsafe_allow_html=True,
        )
        index_name = st.selectbox(
            "Indice composite",
            options=list(PERFORMANCE_INDICES.keys()),
            key="rkc_index",
        )
        top_n = st.select_slider(
            "Top N", options=[10, 20, 50, 100, 200], value=20,
            key="rkc_topn",
        )

        # Description
        metrics_list = ", ".join([col for _, col in PERFORMANCE_INDICES[index_name]])
        st.markdown(
            f"<div style='background:{COLORS['card']};border-radius:8px;padding:10px 12px;"
            f"border:1px solid {COLORS['border']};margin-top:12px;font-size:0.78rem'>"
            f"<div style='font-weight:700;color:{COLORS['accent_blue']}'>{index_name}</div>"
            f"<div style='color:{COLORS['text_muted']};margin-top:4px'>"
            f"Métriques : <i>{metrics_list}</i></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col_results:
        # Gate "Afficher"
        from components.filters import render_show_gate
        if not render_show_gate(
            "ranking_club",
            label="🏆  Générer le classement",
            hint="Choisis l'indice composite et la limite, puis clique pour générer.",
        ):
            return

        df = _compute_index_score(season, league_filter, index_name)
        if df.empty:
            st.info("Aucune donnée disponible pour cet indice.")
            return

        top = df.head(top_n).reset_index(drop=True)

        # En-tête résultats
        st.markdown(
            f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;"
            f"margin-bottom:8px'>"
            f"<b style='color:{COLORS['text']}'>{len(top)} équipe(s)</b> "
            f"· Indice : <b>{index_name}</b> "
            f"· Ligue : {LEAGUE_LABELS.get(league_filter, league_filter or 'Big 5')}"
            f"</div>",
            unsafe_allow_html=True,
        )

        for idx, row in top.iterrows():
            _render_ranking_card(idx + 1, row, index_name, season, league_filter)
