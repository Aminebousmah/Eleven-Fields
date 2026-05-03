"""
ElevenField — Point d'entrée Streamlit.
Lancement : streamlit run app.py
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


def _inject_css() -> None:
    css_path = Path(__file__).parent / "assets" / "style.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

_inject_css()


# ── Navigation ────────────────────────────────────────────────────────────────
NAV_ITEMS = [
    ("🏠", "Accueil"),
    ("📊", "Base de données"),
    ("🔥", "Tendances"),
    ("🏟️", "Vue Équipe"),
    ("👤", "Profil Joueur"),
    ("📅", "Analyse Match"),
    ("⚖️", "Comparaison"),
    ("🧩", "Composition"),
    ("🗂️", "Couverture"),
]

NAV_LABELS = [f"{icon} {label}" for icon, label in NAV_ITEMS]

# Cibles des redirections (_goto)
GOTO_TO_NAV = {
    "database": NAV_LABELS[1],
    "trends":   NAV_LABELS[2],
    "team":     NAV_LABELS[3],
    "player":   NAV_LABELS[4],
    "match":    NAV_LABELS[5],
    "compare":  NAV_LABELS[6],
    "lineup":   NAV_LABELS[7],
}


# ── Sidebar ───────────────────────────────────────────────────────────────────
def _render_sidebar() -> tuple[str, str, str]:
    from components.filters import render_global_filters

    st.sidebar.markdown(
        f"""
<div style="padding:10px 0 18px 0;border-bottom:1px solid {COLORS['border']};margin-bottom:12px">
  <div style="font-size:1.3rem;font-weight:900;
              background:linear-gradient(90deg,{COLORS['accent_green']},{COLORS['accent_blue']});
              -webkit-background-clip:text;-webkit-text-fill-color:transparent">
    ⚽ ElevenField
  </div>
  <div style="font-size:0.7rem;color:{COLORS['text_muted']}">Data Football Dashboard</div>
</div>
""",
        unsafe_allow_html=True,
    )

    # Traitement des redirections depuis Database / Trends / autres
    goto = st.session_state.pop("_goto", None)
    if goto in GOTO_TO_NAV:
        st.session_state["nav_radio"] = GOTO_TO_NAV[goto]

    page = st.sidebar.radio(
        "Navigation",
        NAV_LABELS,
        key="nav_radio",
        label_visibility="collapsed",
    )
    st.sidebar.divider()

    season, league = render_global_filters()

    return page, season, league


# ── Router ────────────────────────────────────────────────────────────────────
def router(page: str, season: str, league: str) -> None:
    if page == NAV_LABELS[0]:
        from dashboards.home import render
        render()

    elif page == NAV_LABELS[1]:
        from dashboards.database import render
        render(season=season, league=league)

    elif page == NAV_LABELS[2]:
        from dashboards.trends import render
        render(season=season, league=league)

    elif page == NAV_LABELS[3]:
        from dashboards.team_overview import render
        render(season=season, league=league)

    elif page == NAV_LABELS[4]:
        from dashboards.player_profile import render
        render(season=season, league=league)

    elif page == NAV_LABELS[5]:
        from dashboards.match_analysis import render
        render(season=season, league=league)

    elif page == NAV_LABELS[6]:
        from dashboards.comparison import render
        render(season=season, league=league)

    elif page == NAV_LABELS[7]:
        from dashboards.lineup_builder import render
        render(season=season, league=league)

    elif page == NAV_LABELS[8]:
        from dashboards.coverage import render
        render()


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    page, season, league = _render_sidebar()
    router(page, season, league)


main()
