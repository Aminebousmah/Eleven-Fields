"""
ElevenField — Shell Streamlit (v5 — refonte design Claude Design).

Architecture portée depuis le bundle React de Claude Design :
  - Sidebar : brand mark + mode toggle (Joueurs/Clubs) + tab list (7 onglets)
              + side foot statistiques
  - Topbar  : breadcrumbs + chips ligues + champ saison
  - Onglets : mode-aware (Analyse, Comparaison, Nuage, Classement) + non
              mode-aware (Tendances, Composition, Story)
  - Empty state animée avant clic sur "Afficher"
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from config import COLORS, SEASONS
from components.design import inject_design_css, topbar_html

st.set_page_config(
    page_title="ElevenField",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_design_css()


# ── Définition des onglets (extrait du bundle.jsx) ────────────────────────────

TABS: list[dict] = [
    {"id": "analyse",     "ico": "◉", "label": "Analyse",     "hint": "Fiche complète",            "mode_aware": True,  "kbd": "1"},
    {"id": "compare",     "ico": "⚔",  "label": "Comparaison", "hint": "Duel 2 entités",            "mode_aware": True,  "kbd": "2"},
    {"id": "scatter",     "ico": "⊕", "label": "Nuage",        "hint": "Scatter + clusters",         "mode_aware": True,  "kbd": "3"},
    {"id": "ranking",     "ico": "☷", "label": "Classement",   "hint": "Par profil tactique",        "mode_aware": True,  "kbd": "4"},
    {"id": "trends",      "ico": "△", "label": "Tendances",    "hint": "xG diff + médias",           "mode_aware": False, "kbd": "5"},
    {"id": "composition", "ico": "▦", "label": "Composition",  "hint": "Constructeur XI",            "mode_aware": False, "kbd": "6"},
    {"id": "story",       "ico": "✦", "label": "Story",         "hint": "Composer · export · publier","mode_aware": False, "kbd": "7"},
]


def _tab_meta(tab_id: str) -> dict:
    return next((t for t in TABS if t["id"] == tab_id), TABS[0])


# ── Session state ─────────────────────────────────────────────────────────────

def _init_state() -> None:
    st.session_state.setdefault("ef_tab",  "analyse")
    st.session_state.setdefault("ef_mode", "player")
    st.session_state.setdefault("ctx_player", None)
    st.session_state.setdefault("ctx_team",   None)
    st.session_state.setdefault("ef_board",   [])  # pinned cards (Story tab)
    # Filtres saison/ligue : defaults
    st.session_state.setdefault("season_idx", len(SEASONS) - 1)
    st.session_state.setdefault("league",     "Toutes les ligues")


def _reset_gates_on_route_change(tab_id: str, mode: str) -> None:
    """Reset des gates "Afficher" à chaque changement d'onglet ou de mode."""
    key = f"{tab_id}::{mode}"
    prev = st.session_state.get("_prev_route_key")
    if prev != key:
        for k in list(st.session_state.keys()):
            if k.endswith("_shown"):
                st.session_state.pop(k, None)
        st.session_state["_prev_route_key"] = key


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _render_brand() -> None:
    """Brand mark + name + tag — en haut de la sidebar."""
    season_label = list(SEASONS.values())[-1] if SEASONS else "—"
    st.sidebar.markdown(
        f"""
<div class="ef-brand">
  <div class="ef-brand-mark"></div>
  <div>
    <div class="ef-brand-name">ELEVEN<span class="dot">·</span>FIELD</div>
    <div class="ef-brand-tag">Big 5 · {season_label}</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _render_mode_toggle() -> None:
    """Toggle segmenté Joueurs / Clubs."""
    current = st.session_state["ef_mode"]

    # On utilise 2 boutons Streamlit en columns avec type=primary pour l'actif
    col_a, col_b = st.sidebar.columns(2, gap="small")
    with col_a:
        if st.button(
            "👤  Joueurs",
            key="ef_mode_player",
            type="primary" if current == "player" else "secondary",
            use_container_width=True,
        ):
            if current != "player":
                st.session_state["ef_mode"] = "player"
                st.rerun()
    with col_b:
        if st.button(
            "🏟  Clubs",
            key="ef_mode_club",
            type="primary" if current == "club" else "secondary",
            use_container_width=True,
        ):
            if current != "club":
                st.session_state["ef_mode"] = "club"
                st.rerun()


def _render_tab_list() -> None:
    """Liste des onglets dans la sidebar."""
    current = st.session_state["ef_tab"]

    st.sidebar.markdown(
        '<div class="ef-side-title">Onglets</div>',
        unsafe_allow_html=True,
    )

    for tab in TABS:
        tab_id = tab["id"]
        label = f"{tab['ico']}   {tab['label']}"
        # Indicateur board (Story tab uniquement)
        if tab_id == "story":
            n = len(st.session_state.get("ef_board", []))
            if n > 0:
                label += f"   [{n}]"

        is_active = (tab_id == current)
        if st.sidebar.button(
            label,
            key=f"ef_tab_{tab_id}",
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            if not is_active:
                st.session_state["ef_tab"] = tab_id
                st.rerun()


def _render_side_foot() -> None:
    """Stats infos en bas de sidebar."""
    n_seasons = len(SEASONS)
    st.sidebar.markdown(
        f"""
<div class="ef-side-foot">
  <div class="row"><span>Saisons indexées</span><span class="num">{n_seasons}</span></div>
  <div class="row"><span>Source</span><span class="num">FBref</span></div>
  <div class="row"><span>Enrichi par</span><span class="num">TM</span></div>
</div>
        """,
        unsafe_allow_html=True,
    )


_ACCENT_PALETTES = {
    "pitch":     ("oklch(0.86 0.20 130)", "oklch(0.72 0.18 145)", "oklch(0.16 0.04 130)"),
    "signal":    ("oklch(0.80 0.18 200)", "oklch(0.72 0.20 330)", "oklch(0.14 0.04 200)"),
    "editorial": ("oklch(0.82 0.17 75)",  "oklch(0.66 0.20 250)", "oklch(0.16 0.05 70)"),
    "mono":      ("oklch(0.72 0.18 165)", "oklch(0.62 0.15 175)", "oklch(0.13 0.04 165)"),
}


@st.dialog("🎨  Réglages visuels", width="small")
def _show_tweaks_dialog() -> None:
    """Modal de réglages visuels (palette / cartes / animations)."""
    _render_tweaks_body()


def _render_tweaks_body() -> None:
    """Contenu du panneau Réglages (réutilisable dialog ou expander)."""
    # Palette accent
    st.markdown(
        '<div style="font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;'
        'color:var(--ink-3);margin-bottom:6px">Palette accent</div>',
        unsafe_allow_html=True,
    )
    palette_options = list(_ACCENT_PALETTES.keys())
    current_palette = st.session_state.get("tweak_palette", "pitch")
    palette = st.radio(
        "Palette", palette_options,
        index=palette_options.index(current_palette),
        key="tweak_palette_radio_dlg",
        label_visibility="collapsed",
        horizontal=True,
    )
    if palette != current_palette:
        st.session_state["tweak_palette"] = palette
        st.rerun()

    # Style des cartes
    st.markdown(
        '<div style="font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;'
        'color:var(--ink-3);margin:14px 0 4px">Style cartes</div>',
        unsafe_allow_html=True,
    )
    cards = st.radio(
        "Cartes", ["flat", "outlined", "glow"],
        index=["flat", "outlined", "glow"].index(
            st.session_state.get("tweak_cards", "flat")
        ),
        key="tweak_cards_radio_dlg",
        label_visibility="collapsed",
        horizontal=True,
    )
    if cards != st.session_state.get("tweak_cards", "flat"):
        st.session_state["tweak_cards"] = cards
        st.rerun()

    # Animations
    anim = st.checkbox(
        "Animations stagger",
        value=st.session_state.get("tweak_anim", True),
        key="tweak_anim_check_dlg",
    )
    if anim != st.session_state.get("tweak_anim", True):
        st.session_state["tweak_anim"] = anim
        st.rerun()


def _render_tweaks() -> None:
    """Panneau de réglages visuels (palette / cartes / animations)."""
    with st.sidebar.expander("🎨  Réglages", expanded=False):
        # Palette accent
        st.markdown(
            '<div style="font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;'
            'color:var(--ink-3);margin-bottom:6px">Palette accent</div>',
            unsafe_allow_html=True,
        )
        palette_options = list(_ACCENT_PALETTES.keys())
        current_palette = st.session_state.get("tweak_palette", "pitch")
        palette = st.radio(
            "Palette", palette_options,
            index=palette_options.index(current_palette),
            key="tweak_palette_radio",
            label_visibility="collapsed",
            horizontal=True,
        )
        if palette != current_palette:
            st.session_state["tweak_palette"] = palette
            st.rerun()

        # Style des cartes
        st.markdown(
            '<div style="font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;'
            'color:var(--ink-3);margin:8px 0 4px">Style cartes</div>',
            unsafe_allow_html=True,
        )
        cards = st.radio(
            "Cartes", ["flat", "outlined", "glow"],
            index=["flat", "outlined", "glow"].index(
                st.session_state.get("tweak_cards", "flat")
            ),
            key="tweak_cards_radio",
            label_visibility="collapsed",
            horizontal=True,
        )
        if cards != st.session_state.get("tweak_cards", "flat"):
            st.session_state["tweak_cards"] = cards
            st.rerun()

        # Animations
        anim = st.checkbox(
            "Animations stagger",
            value=st.session_state.get("tweak_anim", True),
            key="tweak_anim_check",
        )
        if anim != st.session_state.get("tweak_anim", True):
            st.session_state["tweak_anim"] = anim
            st.rerun()


def _apply_tweaks_css() -> None:
    """Override CSS dynamique selon les tweaks utilisateur."""
    palette = st.session_state.get("tweak_palette", "pitch")
    cards = st.session_state.get("tweak_cards", "flat")
    anim = st.session_state.get("tweak_anim", True)

    a1, a2, ink = _ACCENT_PALETTES.get(palette, _ACCENT_PALETTES["pitch"])

    # Override CSS
    overrides = []
    overrides.append(f":root {{ --accent: {a1}; --accent-2: {a2}; --accent-ink: {ink}; }}")

    if cards == "outlined":
        overrides.append(".ef-card { background: var(--bg-0) !important; "
                         "border: 1px solid var(--line) !important; box-shadow: none !important; }")
    elif cards == "glow":
        overrides.append(".ef-card { background: linear-gradient(180deg, var(--bg-2), var(--bg-1)) !important; "
                         "box-shadow: 0 1px 0 rgba(255,255,255,.04) inset, "
                         "0 0 0 1px color-mix(in oklch, var(--accent) 8%, transparent), "
                         "0 18px 40px -28px color-mix(in oklch, var(--accent) 60%, transparent) !important; }")

    if not anim:
        overrides.append(".ef-stagger > * { animation: none !important; }")

    st.markdown(f"<style>{''.join(overrides)}</style>", unsafe_allow_html=True)


def _render_admin() -> None:
    """Menu admin discret."""
    with st.sidebar.expander("⚙  Admin", expanded=False):
        if st.button("🗂  Couverture", key="admin_coverage_btn",
                     use_container_width=True):
            st.session_state["admin_route"] = "coverage"
            st.rerun()
        if st.button("🔄  Vider le cache", key="admin_cache_btn",
                     use_container_width=True):
            st.cache_data.clear()
            st.toast("Cache vidé", icon="✅")
            st.rerun()


def _render_sidebar() -> None:
    _render_brand()
    _render_mode_toggle()
    _render_tab_list()
    _render_side_foot()
    _render_tweaks()
    _render_admin()
    _apply_tweaks_css()


# ── Topbar (dans le contenu principal) ────────────────────────────────────────

def _render_topbar(tab_id: str, mode: str) -> tuple[str, str]:
    """Topbar HTML + popover filtres juste en dessous (clair et accessible)."""
    tab_meta = _tab_meta(tab_id)
    season_keys = list(SEASONS.keys())

    # Lire l'état courant
    cur_idx = min(st.session_state.get("season_idx", len(season_keys) - 1),
                  len(season_keys) - 1)
    season = season_keys[cur_idx]
    season_label = SEASONS[season]
    league = st.session_state.get("league", "Toutes les ligues")

    # Topbar HTML pleine largeur
    st.markdown(
        topbar_html(mode, tab_meta["label"], tab_meta["hint"],
                    season_label, league),
        unsafe_allow_html=True,
    )

    # Popover filtres : bouton clair, alignement à droite
    pop_col_left, pop_col_btn = st.columns([6, 1.5])
    with pop_col_btn:
        with st.popover("⚙  Modifier filtres", use_container_width=True):
            # Layout vertical (pas de columns) pour que les selectboxes
            # ne soient pas coupés dans le popover
            from config import LEAGUES, LEAGUE_LABELS
            season_labels = list(SEASONS.values())
            season_keys_list = list(SEASONS.keys())

            chosen_label = st.selectbox(
                "Saison",
                options=season_labels,
                index=st.session_state.get("season_idx", len(season_labels) - 1),
                key="season_select",
            )
            st.session_state["season_idx"] = season_labels.index(chosen_label)
            season = season_keys_list[st.session_state["season_idx"]]

            league_options = ["Toutes les ligues"] + LEAGUES
            cur_league = st.session_state.get("league", "Toutes les ligues")
            league = st.selectbox(
                "Ligue",
                options=league_options,
                format_func=lambda x: LEAGUE_LABELS.get(x, x),
                index=league_options.index(cur_league)
                if cur_league in league_options else 0,
                key="league_select",
            )
            st.session_state["league"] = league

    return season, league


# ── Router ────────────────────────────────────────────────────────────────────

def _route(tab_id: str, mode: str, season: str, league: str) -> None:
    """Dispatch vers le bon dashboard selon (tab_id, mode)."""
    # Admin override
    if st.session_state.get("admin_route") == "coverage":
        if st.button("← Retour à la navigation"):
            st.session_state["admin_route"] = None
            st.rerun()
        from dashboards.coverage import render
        render()
        return

    if tab_id == "analyse":
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

    elif tab_id == "compare":
        if mode == "player":
            from dashboards.comparison import render_players
            render_players(season=season, league=league)
        else:
            from dashboards.comparison import render_clubs
            render_clubs(season=season, league=league)

    elif tab_id == "scatter":
        if mode == "player":
            from dashboards.scatter_player import render
            render(season=season, league=league)
        else:
            from dashboards.scatter_club import render
            render(season=season, league=league)

    elif tab_id == "ranking":
        if mode == "player":
            from dashboards.ranking_player import render
            render(season=season, league=league)
        else:
            from dashboards.ranking_club import render
            render(season=season, league=league)

    elif tab_id == "trends":
        tab1, tab2 = st.tabs(["📊  Tendances stats", "📰  Tendances médias"])
        with tab1:
            from dashboards.trends import render as render_trends
            render_trends(season=season, league=league)
        with tab2:
            from dashboards.media_intel import render as render_media
            render_media(season=season, league=league)

    elif tab_id == "composition":
        from dashboards.lineup_builder import render
        render(season=season, league=league)

    elif tab_id == "story":
        _render_story_placeholder()

    else:
        st.error(f"Onglet inconnu : {tab_id}")


def _render_story_placeholder() -> None:
    """Onglet Story : board ordonnable + génération texte via Claude Haiku."""
    from components.design import empty_state, card_open, card_close

    board = st.session_state.setdefault("ef_board", [])

    # ── Toolbar ──────────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;'
        f'margin-bottom:14px;border-radius:10px;background:var(--bg-1);'
        f'border:1px solid var(--line-faint)">'
        f'  <span style="font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;'
        f'color:var(--ink-3)">✦ Story · composer · exporter · publier</span>'
        f'  <span style="margin-left:auto;color:var(--ink-3);font-size:11px">'
        f'{len(board)} card{"s" if len(board) > 1 else ""} épinglée{"s" if len(board) > 1 else ""}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if not board:
        st.markdown(
            empty_state(
                primary="Aucune card épinglée pour le moment",
                secondary=(
                    "Va sur Analyse, Comparaison ou Classement et clique sur le bouton "
                    "✦ Story sur les cards intéressantes pour les ajouter à ton thread."
                ),
                icon="✦",
            ),
            unsafe_allow_html=True,
        )
        return

    # ── Toolbar de génération ────────────────────────────────────────────────
    ctrl_cols = st.columns([2, 2, 3])
    with ctrl_cols[0]:
        tone = st.selectbox(
            "Ton du thread",
            ["Analytique", "Grand public", "Provocateur"],
            key="story_tone",
        )
    with ctrl_cols[1]:
        generate_clicked = st.button(
            "✦  Générer texte (Haiku)",
            key="story_generate", type="primary", use_container_width=True,
        )
    with ctrl_cols[2]:
        if st.button("🗑  Vider la story", key="story_clear",
                     use_container_width=True):
            st.session_state["ef_board"] = []
            st.session_state.pop("story_generated_text", None)
            st.rerun()

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

    # ── Liste des cards épinglées (drag-handle visuel + contrôles) ──────────
    type_icons = {
        "gauge": "◉", "radar": "✦", "scatter": "⊕",
        "ranking": "☷", "heatmap": "▦", "comparison": "⚔",
        "generic": "▢",
    }

    for idx, item in enumerate(board):
        icon = type_icons.get(item.get("type", "generic"), "▢")
        with st.container():
            ctl_cols = st.columns([0.35, 0.65, 5, 0.5, 0.5, 0.5])
            with ctl_cols[0]:
                # Drag handle visuel (6 points style ⋮⋮)
                st.markdown(
                    '<div style="display:flex;align-items:center;justify-content:center;'
                    'height:48px;color:var(--ink-3);font-size:18px;cursor:grab;'
                    'letter-spacing:-2px">⋮⋮</div>',
                    unsafe_allow_html=True,
                )
            with ctl_cols[1]:
                st.markdown(
                    f'<div style="display:flex;align-items:center;justify-content:center;'
                    f'background:var(--accent);color:var(--accent-ink);border-radius:6px;'
                    f'width:38px;height:38px;font-weight:700;font-family:ui-monospace,monospace;'
                    f'margin-top:5px;font-size:13px">'
                    f'<span style="margin-right:2px">{icon}</span>{idx+1}</div>',
                    unsafe_allow_html=True,
                )
            with ctl_cols[2]:
                st.markdown(
                    f'<div style="padding:6px 0">'
                    f'  <div style="font-size:13px;font-weight:600;color:var(--ink-0)">'
                    f'{item["title"]}</div>'
                    f'  <div style="font-size:11px;color:var(--ink-3);margin-top:2px">'
                    f'{item.get("subtitle", "")} · '
                    f'<span style="font-family:ui-monospace,monospace;'
                    f'background:var(--bg-2);padding:1px 6px;border-radius:3px">'
                    f'{item.get("type", "—")}</span></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with ctl_cols[3]:
                if st.button("↑", key=f"story_up_{idx}",
                             disabled=(idx == 0), use_container_width=True,
                             help="Monter"):
                    board[idx-1], board[idx] = board[idx], board[idx-1]
                    st.session_state["ef_board"] = board
                    st.rerun()
            with ctl_cols[4]:
                if st.button("↓", key=f"story_down_{idx}",
                             disabled=(idx == len(board)-1),
                             use_container_width=True, help="Descendre"):
                    board[idx+1], board[idx] = board[idx], board[idx+1]
                    st.session_state["ef_board"] = board
                    st.rerun()
            with ctl_cols[5]:
                if st.button("×", key=f"story_del_{idx}",
                             use_container_width=True, help="Retirer"):
                    board.pop(idx)
                    st.session_state["ef_board"] = board
                    st.rerun()
        st.markdown(
            '<div style="border-bottom:1px solid var(--line-faint);'
            'margin:0 0 10px 0"></div>',
            unsafe_allow_html=True,
        )

    # ── Génération texte via Claude Haiku ───────────────────────────────────
    if generate_clicked:
        with st.spinner("Génération via Claude Haiku…"):
            generated = _generate_story_text(board, tone)
            st.session_state["story_generated_text"] = generated

    generated_text = st.session_state.get("story_generated_text")
    if generated_text:
        st.markdown(card_open("Thread généré",
                              actions_html='<span style="color:var(--ink-3);'
                                           'font-size:11px">Claude Haiku</span>'),
                    unsafe_allow_html=True)
        st.markdown(
            f'<div style="white-space:pre-wrap;font-size:13px;line-height:1.6;'
            f'color:var(--ink-1);background:var(--bg-2);padding:14px 16px;'
            f'border-radius:8px;border:1px solid var(--line-faint)">'
            f'{generated_text}</div>',
            unsafe_allow_html=True,
        )

        # Boutons d'action
        b1, b2 = st.columns(2)
        with b1:
            st.download_button(
                "💾  Télécharger thread (.txt)",
                data=generated_text.encode("utf-8"),
                file_name="elevenfield_thread.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with b2:
            if st.button("🔄  Régénérer", key="story_regen",
                         use_container_width=True):
                st.session_state.pop("story_generated_text", None)
                st.rerun()
        st.markdown(card_close(), unsafe_allow_html=True)


def _generate_story_text(board: list, tone: str) -> str:
    """
    Génère le texte du thread via l'API Anthropic (Claude Haiku).
    Fallback : génération locale simple si la clé API n'est pas configurée.
    """
    titles = "\n".join(f"- {item['title']} ({item.get('subtitle', '')})"
                      for item in board)

    tone_instr = {
        "Analytique":   "Ton sec, factuel, basé sur les chiffres. Pas d'emphase inutile.",
        "Grand public": "Ton accessible, pédagogique. Explique le contexte sans jargon.",
        "Provocateur":  "Ton incisif, formules choc, prises de position.",
    }.get(tone, "Ton analytique et factuel.")

    prompt = (
        f"Tu es analyste football. Compose un thread X (Twitter) en 4-6 messages "
        f"(numérotés 1/, 2/, ... ) à partir des éléments suivants :\n\n"
        f"{titles}\n\n"
        f"Ton : {tone_instr}\n"
        f"Format : chaque message ≤ 280 caractères, séparés par une ligne vide. "
        f"Pas de hashtags excessifs. Pas d'emojis. Mets les chiffres en évidence."
    )

    # Appel API Anthropic si dispo
    try:
        import os
        import anthropic
        api_key = (
            os.environ.get("ANTHROPIC_API_KEY")
            or st.secrets.get("ANTHROPIC_API_KEY", None) if hasattr(st, "secrets") else None
        )
        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-3-5-haiku-latest",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
    except Exception:
        pass

    # Fallback local : texte mock à partir des titres
    lines = [
        f"1/ Mini-analyse à partir de {len(board)} card(s) épinglée(s) :",
        "",
    ]
    for i, item in enumerate(board, start=2):
        lines.append(f"{i}/ {item['title']}")
        if item.get("subtitle"):
            lines.append(f"   {item['subtitle']}")
        lines.append("")
    lines.append("(Ce texte est généré localement. Configure ANTHROPIC_API_KEY "
                  "pour la vraie génération via Claude Haiku.)")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def _render_floating_tweaks_button() -> None:
    """Bouton 🎨 flottant en bas à droite qui ouvre le dialog des réglages."""
    # CSS : positionner le bouton st natif en fixed via une classe wrapper
    st.markdown(
        '''
<style>
.ef-floating-tweak {
  position: fixed !important;
  bottom: 24px !important;
  right: 24px !important;
  z-index: 999 !important;
}
.ef-floating-tweak .stButton button {
  background: var(--accent) !important;
  color: var(--accent-ink) !important;
  border: 0 !important;
  border-radius: 50% !important;
  width: 52px !important;
  height: 52px !important;
  min-height: 52px !important;
  padding: 0 !important;
  font-size: 22px !important;
  font-weight: 700 !important;
  box-shadow: 0 12px 30px rgba(0,0,0,.5),
              0 0 0 1px color-mix(in oklch, var(--accent) 40%, transparent) !important;
  transition: transform .15s ease !important;
}
.ef-floating-tweak .stButton button:hover {
  transform: scale(1.08) !important;
  background: color-mix(in oklch, var(--accent) 85%, white) !important;
}
</style>
        ''',
        unsafe_allow_html=True,
    )
    # Conteneur cliquable absolument positionné
    placeholder = st.empty()
    with placeholder.container():
        st.markdown('<div class="ef-floating-tweak">', unsafe_allow_html=True)
        if st.button("🎨", key="floating_tweak_btn", help="Réglages visuels"):
            _show_tweaks_dialog()
        st.markdown('</div>', unsafe_allow_html=True)


def main() -> None:
    _init_state()
    _render_sidebar()

    tab_id = st.session_state["ef_tab"]
    mode   = st.session_state["ef_mode"]
    _reset_gates_on_route_change(tab_id, mode)

    season, league = _render_topbar(tab_id, mode)
    _route(tab_id, mode, season, league)

    # Bouton 🎨 flottant pour ouvrir les Réglages en modal (en bonus de l'expander sidebar)
    _render_floating_tweaks_button()


main()
