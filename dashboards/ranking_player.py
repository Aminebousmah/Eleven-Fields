"""
Classement Joueurs — style DataScout.

Rendu : pour chaque joueur, une carte horizontale avec rang, infos, score
circulaire et boutons d'action (Radar, Voir la fiche).

Filtres : catégorie de profil → profil précis, position(s) sur le terrain,
âge, minutes, valeur marchande.

Réf. visuelle : visualisations/Capture d'écran 2026-05-17 130103.png
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import (
    COLORS, PLAYER_PROFILES, PROFILE_CATEGORIES, FIELD_POSITIONS,
    LEAGUE_LABELS, PLOTLY_LAYOUT,
)
from data.processor import compute_profile_ranking

# Transfermarkt optionnel (photo + logo + valeur marché)
try:
    from transfermarkt.matcher import (
        match_player, get_club_logo, format_value,
        get_player_value_season,
    )
    _TM_OK = True
except Exception:
    _TM_OK = False
    def match_player(*a, **kw): return None
    def get_club_logo(*a, **kw): return None
    def format_value(v): return "—"
    def get_player_value_season(*a, **kw): return None


# ── Helpers UI ────────────────────────────────────────────────────────────────

def _score_color(score: float) -> str:
    """Couleur du cercle de score selon la valeur."""
    if score >= 90:  return "#00ff99"   # vert vif
    if score >= 75:  return "#7cd86b"   # vert
    if score >= 60:  return "#ffd700"   # jaune
    if score >= 45:  return "#ff9f43"   # orange
    return "#ff4655"                    # rouge


def _rank_box_html(rank: int) -> str:
    if rank == 1:
        bg, color = COLORS["accent_gold"], "#1a1a2e"
    elif rank == 2:
        bg, color = "#c5cce0", "#1a1a2e"
    elif rank == 3:
        bg, color = "#cd853f", "#fff"
    else:
        bg, color = COLORS["card"], COLORS["text_muted"]
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
        f"display:flex;align-items:center;justify-content:center;"
        f"position:relative'>"
        f"<div style='width:48px;height:48px;border-radius:50%;"
        f"background:{COLORS['surface']};display:flex;align-items:center;"
        f"justify-content:center;font-weight:900;font-size:1.1rem;"
        f"color:{color}'>{int(round(score))}</div></div>"
    )


def _badge_html(text: str, accent: str | None = None) -> str:
    bg = (accent or COLORS["border"])
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


def _info_html(row: pd.Series, profile_label: str, market_value_str: str) -> str:
    """Bloc info joueur : nom + badges position + tags méta."""
    name = row.get("player", "—")
    team = row.get("team", "—")
    league = row.get("league", "—")
    age = row.get("age", "")
    minutes = row.get("Min", "")
    pos = str(row.get("pos", "")).strip()

    badges_html = _badge_html(profile_label, COLORS["accent_blue"])
    if pos:
        # Première position FBref (avant la virgule éventuelle)
        first_pos = pos.split(",")[0].strip()
        badges_html += _badge_html(first_pos)

    meta_html = (
        _meta_tag_html(f"🏟️ {team}")
        + _meta_tag_html(f"🇪🇺 {LEAGUE_LABELS.get(league, league)}")
    )
    if age:
        try:
            age_int = int(float(age))
            meta_html += _meta_tag_html(f"👤 {age_int} ans")
        except Exception:
            pass
    if minutes:
        try:
            mins_int = int(float(minutes))
            meta_html += _meta_tag_html(f"⏱ {mins_int:,} min.".replace(",", " "))
        except Exception:
            pass
    if market_value_str and market_value_str != "—":
        meta_html += _meta_tag_html(f"💰 {market_value_str}")

    return (
        f"<div style='display:flex;flex-direction:column;gap:4px'>"
        f"  <div style='font-size:1.05rem;font-weight:700;color:{COLORS['text']}'>"
        f"    {name}"
        f"  </div>"
        f"  <div>{badges_html}</div>"
        f"  <div style='margin-top:4px'>{meta_html}</div>"
        f"</div>"
    )


# ── Filtres ───────────────────────────────────────────────────────────────────

def _select_profile() -> tuple[str, str]:
    """
    Sélecteur catégorie → profil. Retourne (category, profile_name).
    Si category == "Toutes catégories", profile_name peut être "" (tous profils).
    """
    cats = ["Toutes catégories"] + PROFILE_CATEGORIES
    c1, c2 = st.columns(2)
    with c1:
        category = st.selectbox("Catégorie", cats, key="rkp_cat")
    if category == "Toutes catégories":
        return category, ""

    # Profils filtrés par catégorie
    profile_options = [
        name for name, cfg in PLAYER_PROFILES.items()
        if cfg.get("category") == category
    ]
    if not profile_options:
        return category, ""
    with c2:
        profile = st.selectbox("Profil", profile_options, key="rkp_prof")
    return category, profile


def _select_field_positions() -> set[str]:
    """[Conservé pour compat] Filtre par position terrain (multiselect)."""
    options = list(FIELD_POSITIONS.keys())
    labels = {k: f"{k} — {v['label']}" for k, v in FIELD_POSITIONS.items()}
    selected = st.multiselect(
        "Positions sur le terrain (laisse vide = toutes)",
        options=options,
        format_func=lambda k: labels[k],
        key="rkp_fpos",
    )
    return set(selected)


def _render_field_picker() -> set[str]:
    """
    PositionPicker SVG : terrain vertical avec rayures + 14 positions dots.
    Le SVG est visuel uniquement ; les clics passent par des boutons Streamlit
    en grille positionnée comme le terrain (compromis Streamlit).
    """
    if "rkp_fpos_set" not in st.session_state:
        st.session_state["rkp_fpos_set"] = set()
    selected = st.session_state["rkp_fpos_set"]

    # ── Mini-terrain SVG en arrière-plan (visuel, non cliquable) ─────────────
    _render_pitch_svg_bg(selected)

    # ── Grille de boutons toggle positionnés comme un 4-3-3 ─────────────────
    layout = [
        [None, None,  "BU",  None, None],
        [None, "AG",  "MOC", "AD",  None],
        [None, None,  "MC",  None, None],
        [None, None,  "MDC", None, None],
        ["DG", "DCG", None,  "DCD", "DD"],
        [None, None,  "G",   None, None],
    ]
    for row in layout:
        cols = st.columns(5, gap="small")
        for col_obj, pos_key in zip(cols, row):
            with col_obj:
                if pos_key is None:
                    st.markdown('<div style="height:28px"></div>',
                                unsafe_allow_html=True)
                    continue
                is_on = pos_key in selected
                if st.button(
                    pos_key, key=f"fp_{pos_key}",
                    type="primary" if is_on else "secondary",
                    use_container_width=True,
                ):
                    if is_on:
                        selected.discard(pos_key)
                    else:
                        selected.add(pos_key)
                    st.session_state["rkp_fpos_set"] = selected
                    st.rerun()

    # Légende
    n_sel = len(selected)
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin-top:8px;'
        f'font-size:10px;color:var(--ink-3)">'
        f'<span style="width:8px;height:8px;border-radius:50%;'
        f'background:var(--bg-2);border:1px solid var(--line)"></span> Disponible '
        f'<span style="width:8px;height:8px;border-radius:50%;'
        f'background:var(--accent);margin-left:6px"></span> Sélectionné'
        f'<span style="margin-left:auto">{n_sel} sélection{("s" if n_sel > 1 else "")}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    return selected


def _render_pitch_svg_bg(selected: set[str]) -> None:
    """Mini-terrain SVG en fond (cosmétique, sous les boutons)."""
    # 14 positions sur le terrain (% x, % y)
    positions = {
        "G":   (50, 92), "DG":  (12, 75), "DCG": (36, 78),
        "DCD": (64, 78), "DD":  (88, 75), "MDC": (50, 60),
        "MC":  (50, 50), "MOC": (50, 38), "MOG": (28, 38),
        "MOD": (72, 38), "AG":  (12, 25), "AD":  (88, 25),
        "SA":  (38, 12), "BU":  (50, 8),
    }
    width, height = 240, 320
    line_color = "rgba(255,255,255,0.30)"

    # Rayures de tonte (8 bandes alternées)
    stripes = "".join(
        f'<rect x="0" y="{i * height / 8}" width="{width}" height="{height / 8}" '
        f'fill="{"#1e4a2e" if i % 2 == 0 else "#234d33"}"/>'
        for i in range(8)
    )

    # Dots (14 positions, accent si sélectionné, gris sinon)
    dots = ""
    for pos, (px, py) in positions.items():
        cx = (px / 100) * width
        cy = (py / 100) * height
        is_on = pos in selected
        fill = "#84e06e" if is_on else "rgba(40,42,56,0.85)"
        stroke = "#84e06e" if is_on else "rgba(255,255,255,0.45)"
        dots += (
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )

    # SVG concaténé sur une seule ligne logique (sans indent) — sinon Markdown
    # interprète les lignes >= 4 espaces comme un bloc de code.
    svg = (
        f'<svg width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" '
        f'style="border-radius:8px;background:#1e4a2e;'
        f'margin-bottom:8px;display:block">'
        f'{stripes}'
        f'<rect x="4" y="4" width="{width-8}" height="{height-8}" '
        f'fill="none" stroke="{line_color}" stroke-width="1.5"/>'
        f'<line x1="4" x2="{width-4}" y1="{height/2}" y2="{height/2}" '
        f'stroke="{line_color}" stroke-width="1.2"/>'
        f'<circle cx="{width/2}" cy="{height/2}" r="26" fill="none" '
        f'stroke="{line_color}" stroke-width="1.2"/>'
        f'<rect x="{(width-90)/2}" y="4" width="90" height="38" '
        f'fill="none" stroke="{line_color}" stroke-width="1.2"/>'
        f'<rect x="{(width-90)/2}" y="{height-42}" width="90" height="38" '
        f'fill="none" stroke="{line_color}" stroke-width="1.2"/>'
        f'{dots}'
        f'</svg>'
    )
    st.markdown(
        f'<div style="display:flex;justify-content:center">{svg}</div>',
        unsafe_allow_html=True,
    )


def _filter_profiles_by_positions(positions: set[str]) -> list[str]:
    """Retourne les noms de profils dont au moins une position est dans le filtre."""
    if not positions:
        return list(PLAYER_PROFILES.keys())
    return [
        name for name, cfg in PLAYER_PROFILES.items()
        if positions & set(cfg.get("field_positions", []))
    ]


# ── Navigation programmatique vers la fiche joueur ────────────────────────────

def _goto_player_profile(player: str, team: str) -> None:
    """Route vers Analyse Joueur avec le joueur pré-rempli."""
    # Force le mode joueur
    st.session_state["mode"] = "player"
    st.session_state["mode_radio"] = "👤  Joueurs"
    # Force la nav sur "Analyse"
    st.session_state["nav_radio"] = "👤  Analyse Joueurs"
    # Pré-remplit le contexte
    st.session_state["ctx_player"] = player
    st.session_state["ctx_team"] = team
    st.session_state["_selected_player"] = player
    st.rerun()


# ── Radar inline ──────────────────────────────────────────────────────────────

def _render_radar_inline(
    player: str, team: str, profile_name: str,
    season: str, league_filter: str | None,
) -> None:
    """
    Mini-radar percentile du joueur sur les métriques du profil sélectionné.
    Affiché sous la carte quand on clique sur "Radar".
    """
    from components.charts import make_radar
    from data.processor import build_radar_with_context

    profile = PLAYER_PROFILES.get(profile_name)
    if not profile:
        st.info("Profil indisponible pour le radar.")
        return

    # dict {label: (stat_type, col)} pour build_radar_with_context
    metrics_dict = {col: (stat_type, col) for stat_type, col, _ in profile["metrics"]}
    labels = list(metrics_dict.keys())

    try:
        radar_data = build_radar_with_context(
            metrics=metrics_dict,
            entity_name=player,
            entity_type="player",
            season=season,
            league=league_filter,
            min_minutes=500,
        )
    except Exception as exc:
        st.info(f"Erreur radar : {exc}")
        return

    if not radar_data or not radar_data.get("focus"):
        st.info("Données insuffisantes pour ce radar.")
        return

    # build_radar_with_context renvoie {focus, median, top10, bottom10}.
    # On affiche le joueur + la médiane de la ligue.
    series = {
        player:           radar_data["focus"],
        "Médiane ligue":  radar_data["median"],
    }
    fig = make_radar(
        series, labels,
        title=f"Radar percentile — {profile_name} ({profile['pos_group']})",
    )
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)


# ── Carte joueur ──────────────────────────────────────────────────────────────

def _render_ranking_card(
    rank: int, row: pd.Series, profile_name: str,
    season: str, league_filter: str | None,
) -> None:
    """Une carte de classement complète : rang + photo + infos + score + actions."""
    score = float(row.get("score", 0))
    player = row.get("player", "")
    team = row.get("team", "")

    # Récupération Transfermarkt : photo + valeur marché
    photo_url = None
    market_value_str = "—"
    if _TM_OK:
        try:
            tm = match_player(player, fbref_league=league_filter)
            if tm:
                photo_url = tm.get("image_url")
            mv = get_player_value_season(player, season, league_filter)
            if mv is not None and pd.notna(mv):
                market_value_str = format_value(mv)
        except Exception:
            pass

    with st.container(border=True):
        c_rank, c_photo, c_info, c_score, c_actions = st.columns([0.6, 0.9, 4.4, 0.8, 1.6])

        with c_rank:
            st.markdown(_rank_box_html(rank), unsafe_allow_html=True)

        with c_photo:
            if photo_url:
                st.image(photo_url, width=60)
            else:
                st.markdown(
                    f"<div style='width:60px;height:60px;border-radius:50%;"
                    f"background:{COLORS['border']};display:flex;align-items:center;"
                    f"justify-content:center;font-size:28px'>👤</div>",
                    unsafe_allow_html=True,
                )

        with c_info:
            st.markdown(
                _info_html(row, profile_name, market_value_str),
                unsafe_allow_html=True,
            )

        with c_score:
            st.markdown(_score_circle_html(score), unsafe_allow_html=True)

        with c_actions:
            uid = f"{rank}_{player}_{team}".replace(" ", "_")
            # Toggle radar
            radar_key = f"_radar_open_{uid}"
            if st.button("📊  Radar",
                         key=f"btn_radar_{uid}", use_container_width=True):
                st.session_state[radar_key] = not st.session_state.get(radar_key, False)

            # Navigation vers fiche
            if st.button("→  Voir la fiche",
                         key=f"btn_fiche_{uid}", use_container_width=True):
                _goto_player_profile(player, team)

        # Radar inline si déplié
        if st.session_state.get(f"_radar_open_{rank}_{player}_{team}".replace(" ", "_")):
            st.divider()
            _render_radar_inline(player, team, profile_name, season, league_filter)


# ── Render principal ──────────────────────────────────────────────────────────

def render(season: str, league: str) -> None:
    league_filter = None if league == "Toutes les ligues" else league

    # ────────────────────────────────────────────────────────────────────────
    # FILTER RAIL HORIZONTAL (en haut) — Catégorie · Profil · Top N
    # ────────────────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;padding:10px 12px;'
        'margin-bottom:12px;border-radius:10px;background:var(--bg-1);'
        'border:1px solid var(--line-faint)">'
        '<span style="font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;'
        'color:var(--ink-3);padding-right:8px">Catégorie · Profil · Limite</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    f_cat, f_prof, f_top = st.columns([2, 3, 3])
    with f_cat:
        cats = ["Toutes catégories"] + PROFILE_CATEGORIES
        category = st.selectbox("Catégorie", cats, key="rkp_cat",
                                 label_visibility="collapsed")
    with f_prof:
        if category == "Toutes catégories":
            profile_name = ""
            st.selectbox("Profil", ["—  Sélectionne d'abord une catégorie  —"],
                         disabled=True, label_visibility="collapsed")
        else:
            profile_options = [
                n for n, c in PLAYER_PROFILES.items()
                if c.get("category") == category
            ]
            profile_name = st.selectbox(
                "Profil", profile_options, key="rkp_prof",
                label_visibility="collapsed",
            )
    with f_top:
        # 4 boutons chips Top N
        cN1, cN2, cN3, cN4 = st.columns(4)
        if "rkp_topn" not in st.session_state:
            st.session_state["rkp_topn"] = 20
        cur_n = st.session_state["rkp_topn"]
        for idx, (col_n, n_val) in enumerate(zip([cN1, cN2, cN3, cN4],
                                                  [10, 25, 50, 100])):
            with col_n:
                if st.button(
                    f"Top {n_val}",
                    key=f"rkp_n{n_val}",
                    type="primary" if cur_n == n_val else "secondary",
                    use_container_width=True,
                ):
                    st.session_state["rkp_topn"] = n_val
                    st.rerun()
    top_n = st.session_state.get("rkp_topn", 20)

    # ────────────────────────────────────────────────────────────────────────
    # LAYOUT 2 COLONNES : sidebar filtres avancés / content cards
    # ────────────────────────────────────────────────────────────────────────
    col_sidebar, col_content = st.columns([1.4, 5], gap="medium")

    with col_sidebar:
        st.markdown(
            '<div class="ef-card" style="padding:14px">'
            '<div style="display:flex;align-items:center;gap:6px;'
            'margin-bottom:12px">'
            '<span style="font-size:14px">▽</span>'
            '<span style="font-size:14px;font-weight:600;color:var(--ink-0)">'
            'Filtres de classement</span></div>',
            unsafe_allow_html=True,
        )

        # Positions terrain (mini grille style 4-3-3 — boutons toggle)
        st.markdown(
            '<div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;'
            'color:var(--ink-3);margin-bottom:6px">Postes sur le terrain</div>',
            unsafe_allow_html=True,
        )
        field_positions = _render_field_picker()

        st.markdown(
            '<div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;'
            'color:var(--ink-3);margin:14px 0 4px">Tranche d\'âge</div>',
            unsafe_allow_html=True,
        )
        age_range = st.slider(
            "Âge", 15, 45, (16, 40),
            key="rkp_age", label_visibility="collapsed",
        )

        st.markdown(
            '<div style="font-size:10px;letter-spacing:.12em;text-transform:uppercase;'
            'color:var(--ink-3);margin:14px 0 4px">Minutes jouées (min.)</div>',
            unsafe_allow_html=True,
        )
        min_minutes = st.slider(
            "Minutes min.", 0, 4000, 500, 100,
            key="rkp_min", label_visibility="collapsed",
        )

        # Info collapsible
        with st.expander("ℹ️  Comment ça marche ?", expanded=False):
            st.markdown(
                "Indice de performance calculé par profil tactique, pondéré par "
                "le niveau du championnat. Un joueur de Premier League sera "
                "souvent classé plus haut qu'un joueur d'une ligue mineure à "
                "profil équivalent."
            )

        st.markdown('</div>', unsafe_allow_html=True)

    # ── Résultats ────────────────────────────────────────────────────────────
    with col_content:
        # Gate "Afficher"
        from components.filters import render_show_gate
        if not render_show_gate(
            "ranking_player",
            label="🏆  Générer le classement",
            primary_text="Configure ton classement",
            hint="Choisis catégorie, profil et filtres puis clique pour générer.",
            icon="☷",
        ):
            return

        if category != "Toutes catégories" and not profile_name:
            st.info("Choisissez un profil dans la catégorie sélectionnée.")
            return

        # Si on a un profil précis, calcul direct
        if profile_name:
            profile = PLAYER_PROFILES[profile_name]
            scores_df = compute_profile_ranking(
                profile_name=profile_name,
                season=season,
                league=league_filter,
                pos_group=profile["pos_group"],
                min_minutes=min_minutes,
            )
        else:
            # Toutes catégories : prend tous les profils dont la position est compatible
            profile_candidates = _filter_profiles_by_positions(field_positions)
            if not profile_candidates:
                st.info("Aucun profil ne correspond aux positions sélectionnées.")
                return
            # On agrège : pour chaque joueur, on prend son MEILLEUR profil parmi les candidats
            frames = []
            for pname in profile_candidates:
                p = PLAYER_PROFILES[pname]
                df = compute_profile_ranking(
                    profile_name=pname,
                    season=season,
                    league=league_filter,
                    pos_group=p["pos_group"],
                    min_minutes=min_minutes,
                )
                if not df.empty:
                    df["_profile"] = pname
                    frames.append(df)
            if not frames:
                st.info("Aucune donnée disponible.")
                return
            agg = pd.concat(frames, ignore_index=True)
            # Pour chaque (player, team), garder la meilleure ligne
            scores_df = (
                agg.sort_values("score", ascending=False)
                   .drop_duplicates(subset=["player", "team"], keep="first")
                   .reset_index(drop=True)
            )

        if scores_df is None or scores_df.empty:
            st.info("Aucun joueur ne correspond aux critères.")
            return

        # Filtre âge
        if "age" in scores_df.columns:
            ages = pd.to_numeric(scores_df["age"], errors="coerce")
            scores_df = scores_df[ages.between(age_range[0], age_range[1])]

        full_count = len(scores_df)
        med_min = (
            int(pd.to_numeric(scores_df["Min"], errors="coerce").median())
            if "Min" in scores_df.columns and not scores_df.empty else 0
        )
        avg_score = scores_df["score"].mean() if not scores_df.empty else 0

        scores_df = scores_df.sort_values("score", ascending=False).head(top_n).reset_index(drop=True)

        if scores_df.empty:
            st.info("Aucun joueur après filtres.")
            return

        # ── Header profil tactique (style mockup 4) ──────────────────────────
        profile_obj = PLAYER_PROFILES.get(profile_name, {})
        tagline = profile_obj.get("tagline", "")

        st.markdown(
            f'<div style="display:flex;align-items:flex-start;gap:14px;'
            f'padding:14px 16px;margin-bottom:12px;border-radius:10px;'
            f'background:var(--bg-1);border:1px solid var(--line-faint)">'
            f'  <div style="flex:1;min-width:0">'
            f'    <div style="font-size:10px;letter-spacing:.14em;text-transform:uppercase;'
            f'color:var(--ink-3);margin-bottom:4px">Profil tactique</div>'
            f'    <div style="font-size:22px;font-weight:700;color:var(--ink-0);'
            f'letter-spacing:-.01em">{profile_name or "Multi-profils"}</div>'
            f'    <div style="font-size:12px;color:var(--ink-3);margin-top:4px;'
            f'line-height:1.4">{tagline}</div>'
            f'  </div>'
            f'  <div style="display:grid;grid-template-columns:repeat(3,auto);'
            f'gap:18px;align-items:center">'
            f'    <div style="text-align:center">'
            f'      <div style="font-size:9px;letter-spacing:.14em;text-transform:uppercase;'
            f'color:var(--ink-3)">Joueurs match</div>'
            f'      <div style="font-size:20px;font-weight:600;color:var(--ink-0);'
            f'font-family:ui-monospace,monospace">{full_count}</div>'
            f'    </div>'
            f'    <div style="text-align:center">'
            f'      <div style="font-size:9px;letter-spacing:.14em;text-transform:uppercase;'
            f'color:var(--ink-3)">Min médiane</div>'
            f'      <div style="font-size:20px;font-weight:600;color:var(--ink-0);'
            f'font-family:ui-monospace,monospace">{med_min:,}'.replace(",", " ") + '</div>'
            f'    </div>'
            f'    <div style="text-align:center">'
            f'      <div style="font-size:9px;letter-spacing:.14em;text-transform:uppercase;'
            f'color:var(--ink-3)">Score moy.</div>'
            f'      <div style="font-size:20px;font-weight:600;color:var(--ink-0);'
            f'font-family:ui-monospace,monospace">{avg_score:.0f}</div>'
            f'    </div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Rendu des cartes
        for idx, row in scores_df.iterrows():
            rank = idx + 1
            displayed_profile = row.get("_profile", profile_name) if not profile_name else profile_name
            _render_ranking_card(rank, row, displayed_profile, season, league_filter)
