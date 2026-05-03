"""
Glossaire UI : expander réutilisable affichant la définition des indicateurs.
"""
from __future__ import annotations

import streamlit as st

from config import COLORS, METRIC_DEFINITIONS, INDEX_DEFINITIONS


def render_metric_glossary(
    metrics: list[str] | None = None,
    title: str = "ℹ️ Définition des indicateurs",
    include_indices: bool = False,
) -> None:
    """
    Affiche un expander avec les définitions des sigles.
    Si `metrics` est None → affiche tous les sigles connus.
    """
    keys = metrics if metrics else list(METRIC_DEFINITIONS.keys())
    pairs = [(k, METRIC_DEFINITIONS[k]) for k in keys if k in METRIC_DEFINITIONS]
    if not pairs and not include_indices:
        return

    with st.expander(title, expanded=False):
        if pairs:
            cols = st.columns(2)
            half = (len(pairs) + 1) // 2
            for i, (sigle, defn) in enumerate(pairs):
                target = cols[0] if i < half else cols[1]
                target.markdown(
                    f"<div style='margin-bottom:6px'>"
                    f"<code style='color:{COLORS['accent_green']};font-weight:700'>{sigle}</code> "
                    f"<span style='color:{COLORS['text']}'>· {defn}</span></div>",
                    unsafe_allow_html=True,
                )
        if include_indices:
            st.markdown("---")
            st.markdown(f"**Indices composites**")
            for name, defn in INDEX_DEFINITIONS.items():
                st.markdown(
                    f"<div style='margin-bottom:4px'>"
                    f"<b style='color:{COLORS['accent_gold']}'>{name}</b> · "
                    f"<span style='color:{COLORS['text']}'>{defn}</span></div>",
                    unsafe_allow_html=True,
                )


def metric_help(sigle: str) -> str:
    """Tooltip text pour st.metric(help=...) — vide si inconnu."""
    return METRIC_DEFINITIONS.get(sigle, "")


def render_disclaimer() -> None:
    """Affiche le disclaimer Data'Scout-style au bas d'un dashboard."""
    from config import COLORS, DISCLAIMER
    st.markdown(
        f"<div style='margin-top:24px;padding:12px 14px;border-radius:8px;"
        f"background:{COLORS['surface']};border-left:3px solid {COLORS['accent_gold']};"
        f"font-size:0.78rem;color:{COLORS['text_muted']};line-height:1.5'>"
        f"<b style='color:{COLORS['accent_gold']}'>⚠️ Disclaimer.</b> "
        f"{DISCLAIMER}"
        f"</div>",
        unsafe_allow_html=True,
    )


# ── Watchlist (shortlist personnelle) ─────────────────────────────────────────

WATCHLIST_KEY = "_watchlist"


def watchlist_get() -> list[dict]:
    """Retourne la watchlist courante : liste de {player, team, season, league, pos}."""
    return st.session_state.get(WATCHLIST_KEY, [])


def watchlist_has(player: str, team: str) -> bool:
    return any(w["player"] == player and w["team"] == team for w in watchlist_get())


def watchlist_add(player: str, team: str, season: str, league: str, pos: str = "") -> None:
    wl = watchlist_get()
    if not watchlist_has(player, team):
        wl.append({
            "player": player, "team": team, "season": season,
            "league": league, "pos": pos,
        })
        st.session_state[WATCHLIST_KEY] = wl


def watchlist_remove(player: str, team: str) -> None:
    st.session_state[WATCHLIST_KEY] = [
        w for w in watchlist_get()
        if not (w["player"] == player and w["team"] == team)
    ]


def watchlist_clear() -> None:
    st.session_state[WATCHLIST_KEY] = []


def render_watchlist_button(player: str, team: str, season: str, league: str, pos: str = "") -> None:
    """Bouton toggle ⭐ pour ajouter/retirer un joueur de la watchlist."""
    in_wl = watchlist_has(player, team)
    label = "⭐ Retirer de ma shortlist" if in_wl else "☆ Ajouter à ma shortlist"
    if st.button(label, key=f"wl_btn_{player}_{team}", use_container_width=True):
        if in_wl:
            watchlist_remove(player, team)
        else:
            watchlist_add(player, team, season, league, pos)
        st.rerun()
