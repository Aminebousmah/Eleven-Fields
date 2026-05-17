"""
ElevenField — Shell Streamlit (v4 — mode-aware).

Architecture : 6 onglets, dont 4 mode-aware (Joueur ↔ Club).
  Sidebar : toggle Joueur / Club + navigation
  Topbar  : filtres saison + ligue (au-dessus de chaque dashboard)

  👤/🏟️ Analyse        (mode-aware)
  ⚔️ Comparaison        (mode-aware)
  🎯 Nuage de points    (mode-aware)
  🏆 Classement         (mode-aware)
  🔥 Tendances          (commun)
  🧩 Composition        (commun)

Admin (caché en bas) : couverture, vider le cache.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from config import COLORS

st.set_page_config(
    page_title="ElevenField",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── CSS ───────────────────────────────────────────────────────────────────────

def _inject_css() -> None:
    css_path = Path(__file__).parent / "assets" / "style.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    st.markdown(
        f"""
<style>
  section[data-testid="stSidebar"] {{
    background: {COLORS["surface"]};
    border-right: 1px solid {COLORS["border"]};
  }}
  /* Mode toggle stylisé */
  .mode-label {{
    font-size: 0.7rem;
    color: {COLORS["text_muted"]};
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 4px;
  }}
  /* Admin section discrète en bas */
  .admin-section {{
    margin-top: 24px;
    padding-top: 12px;
    border-top: 1px solid {COLORS["border"]};
  }}
  /* Topbar filtres : marge respirante */
  .topbar-spacer {{ height: 8px; }}
</style>
        """,
        unsafe_allow_html=True,
    )


_inject_css()


# ── Navigation ────────────────────────────────────────────────────────────────

# (icône, label, route_key, mode_aware)
NAV_ITEMS: list[tuple[str, str, str, bool]] = [
    ("👤",  "Analyse",          "analysis",    True),
    ("⚔️",  "Comparaison",      "comparison",  True),
    ("🎯",  "Nuage de points",  "scatter",     True),
    ("🏆",  "Classement",       "ranking",     True),
    ("🔥",  "Tendances",        "trends",      False),
    ("🧩",  "Composition",      "lineup",      False),
]


def _label_for(item: tuple[str, str, str, bool], mode: str) -> str:
    icon, label, _, mode_aware = item
    if mode_aware:
        mode_suffix = " Joueurs" if mode == "player" else " Clubs"
    else:
        mode_suffix = ""
    return f"{icon}  {label}{mode_suffix}"


def _init_state() -> None:
    st.session_state.setdefault("mode", "player")   # "player" | "club"
    st.session_state.setdefault("ctx_player", None)
    st.session_state.setdefault("ctx_team",   None)


def _reset_gates_on_route_change(current_route: str) -> None:
    """
    À chaque changement de route/mode, réinitialise les gates 'Afficher' pour
    forcer l'utilisateur à recliquer (filtres → bouton).
    """
    current_mode = st.session_state.get("mode", "player")
    key = f"{current_route}::{current_mode}"
    prev = st.session_state.get("_prev_route_key")
    if prev != key:
        # Reset toutes les clés qui finissent par _shown
        for k in list(st.session_state.keys()):
            if k.endswith("_shown"):
                st.session_state.pop(k, None)
        st.session_state["_prev_route_key"] = key


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _render_sidebar() -> str:
    """Sidebar : header + toggle mode + navigation + admin."""
    st.sidebar.markdown(
        f"""
<div style="padding:14px 4px 18px 4px;border-bottom:1px solid {COLORS['border']};
            margin-bottom:14px">
  <div style="font-size:1.4rem;font-weight:900;
              background:linear-gradient(90deg,{COLORS['accent_green']},{COLORS['accent_blue']});
              -webkit-background-clip:text;-webkit-text-fill-color:transparent">
    ⚽ ElevenField
  </div>
  <div style="font-size:0.7rem;color:{COLORS['text_muted']};margin-top:2px">
    Plateforme d'analyse football
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    # ── Toggle Joueur / Club ─────────────────────────────────────────────────
    st.sidebar.markdown('<div class="mode-label">Mode d\'analyse</div>',
                        unsafe_allow_html=True)
    mode_labels = {"player": "👤  Joueurs", "club": "🏟️  Clubs"}
    current_mode = st.session_state["mode"]
    mode_choice = st.sidebar.radio(
        "Mode",
        options=list(mode_labels.values()),
        index=list(mode_labels.keys()).index(current_mode),
        key="mode_radio",
        label_visibility="collapsed",
        horizontal=True,
    )
    # Map back to internal key
    new_mode = "player" if mode_choice.startswith("👤") else "club"
    if new_mode != current_mode:
        st.session_state["mode"] = new_mode
        st.rerun()

    st.sidebar.divider()

    # ── Navigation ───────────────────────────────────────────────────────────
    mode = st.session_state["mode"]
    nav_labels = [_label_for(item, mode) for item in NAV_ITEMS]
    label_to_route = {_label_for(item, mode): item[2] for item in NAV_ITEMS}

    nav_label = st.sidebar.radio(
        "Navigation",
        nav_labels,
        key="nav_radio",
        label_visibility="collapsed",
    )
    route = label_to_route[nav_label]

    # ── Admin ────────────────────────────────────────────────────────────────
    st.sidebar.markdown('<div class="admin-section"></div>', unsafe_allow_html=True)
    with st.sidebar.expander("⚙️  Admin", expanded=False):
        if st.button("🗂️  Couverture des données",
                     key="admin_coverage_btn", use_container_width=True):
            st.session_state["admin_route"] = "coverage"
            st.rerun()
        if st.button("🔄  Vider le cache",
                     key="admin_cache_btn", use_container_width=True):
            st.cache_data.clear()
            st.toast("Cache vidé", icon="✅")
            st.rerun()

    return route


# ── Topbar (filtres saison/ligue dans le contenu) ─────────────────────────────

def _render_topbar() -> tuple[str, str]:
    """Filtres saison + ligue en haut du contenu principal."""
    from components.filters import render_inline_filters
    season, league = render_inline_filters()
    st.markdown('<div class="topbar-spacer"></div>', unsafe_allow_html=True)
    return season, league


# ── Router ────────────────────────────────────────────────────────────────────

def _route(route: str, season: str, league: str) -> None:
    mode = st.session_state["mode"]

    # Admin overrides la route principale si activé
    if st.session_state.get("admin_route") == "coverage":
        if st.button("← Retour à la navigation"):
            st.session_state["admin_route"] = None
            st.rerun()
        from dashboards.coverage import render
        render()
        return

    # ── Routes mode-aware ────────────────────────────────────────────────────
    if route == "analysis":
        if mode == "player":
            if st.session_state.get("ctx_player"):
                st.session_state["_selected_player"] = st.session_state["ctx_player"]
                st.session_state["ctx_player"] = None
            from dashboards.player_profile import render
            render(season=season, league=league)
        else:
            if st.session_state.get("ctx_team"):
                st.session_state["_selected_team"] = st.session_state["ctx_team"]
                st.session_state["ctx_team"] = None
            from dashboards.team_overview import render
            render(season=season, league=league)

    elif route == "comparison":
        if mode == "player":
            from dashboards.comparison import render_players
            render_players(season=season, league=league)
        else:
            from dashboards.comparison import render_clubs
            render_clubs(season=season, league=league)

    elif route == "scatter":
        if mode == "player":
            from dashboards.scatter_player import render
            render(season=season, league=league)
        else:
            from dashboards.scatter_club import render
            render(season=season, league=league)

    elif route == "ranking":
        if mode == "player":
            from dashboards.ranking_player import render
            render(season=season, league=league)
        else:
            from dashboards.ranking_club import render
            render(season=season, league=league)

    # ── Routes communes (mode-indépendantes) ─────────────────────────────────
    elif route == "trends":
        tab1, tab2 = st.tabs(["📊  Tendances stats", "📰  Tendances médias"])
        with tab1:
            from dashboards.trends import render as render_trends
            render_trends(season=season, league=league)
        with tab2:
            from dashboards.media_intel import render as render_media
            render_media(season=season, league=league)

    elif route == "lineup":
        from dashboards.lineup_builder import render
        render(season=season, league=league)

    else:
        st.error(f"Route inconnue : {route}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    _init_state()
    route = _render_sidebar()
    _reset_gates_on_route_change(route)
    season, league = _render_topbar()
    _route(route, season, league)


main()
