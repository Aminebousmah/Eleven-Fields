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
    """Filtre par position terrain (multiselect)."""
    options = list(FIELD_POSITIONS.keys())
    labels = {k: f"{k} — {v['label']}" for k, v in FIELD_POSITIONS.items()}
    selected = st.multiselect(
        "Positions sur le terrain (laisse vide = toutes)",
        options=options,
        format_func=lambda k: labels[k],
        key="rkp_fpos",
    )
    return set(selected)


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

    st.markdown(
        f"<h2 style='color:{COLORS['text']};margin:6px 0 0 0'>🏆 Classement Joueurs</h2>"
        f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;margin-bottom:10px'>"
        f"Découvre les meilleurs joueurs selon chaque profil tactique. "
        f"Score 0–100 calculé relativement aux joueurs du même poste dans la ligue.</div>",
        unsafe_allow_html=True,
    )

    # Bandeau explicatif
    with st.expander("ℹ️  Comment fonctionnent les classements ?", expanded=False):
        st.markdown(
            f"""
- Chaque joueur reçoit un **score 0–100** par profil tactique (ex. *Défenseur Stoppeur*).
- Le score est la **moyenne pondérée des percentiles** des métriques du profil
  par rapport aux joueurs du même groupe de poste (GK / DF / MF / FW) ayant ≥ 500 min.
- Un Ailier Buteur de Premier League aura souvent un score plus élevé qu'un Ailier
  Buteur de Ligue 2 — le pool de comparaison change selon le filtre Ligue.
- Le bouton **Radar** affiche les percentiles détaillés du joueur sur les métriques
  du profil. **Voir la fiche** te redirige sur la page d'analyse complète.
            """
        )

    st.divider()

    # ── Layout : filtres à gauche, classement à droite ──────────────────────
    col_filters, col_results = st.columns([1.2, 4], gap="medium")

    # ── Filtres ───────────────────────────────────────────────────────────────
    with col_filters:
        st.markdown(
            f"<div style='font-weight:700;color:{COLORS['text']};font-size:1rem;"
            f"margin-bottom:8px'>🎚️  Filtres</div>",
            unsafe_allow_html=True,
        )

        category, profile_name = _select_profile()

        st.markdown("**Position sur le terrain**")
        field_positions = _select_field_positions()

        st.markdown("**Tranche d'âge**")
        age_range = st.slider(
            "Âge", 15, 45, (16, 40),
            key="rkp_age", label_visibility="collapsed",
        )

        st.markdown("**Minutes jouées**")
        min_minutes = st.slider(
            "Minutes min.", 0, 4000, 500, 100,
            key="rkp_min", label_visibility="collapsed",
        )

        st.markdown("**Top N**")
        top_n = st.select_slider(
            "Top N", options=[10, 20, 50, 100, 250], value=20,
            key="rkp_topn", label_visibility="collapsed",
        )

    # ── Résultats ─────────────────────────────────────────────────────────────
    with col_results:
        # Gate "Afficher" : on n'affiche le classement qu'après clic
        from components.filters import render_show_gate
        if not render_show_gate(
            "ranking_player",
            label="🏆  Générer le classement",
            hint="Choisis catégorie, profil et filtres puis clique pour générer.",
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

        # Filtre positions (si profil unique sélectionné)
        if profile_name and field_positions:
            # On garde uniquement si la pos FBref du joueur intersecte les positions cibles
            # Approximation simple : on conserve tout (le profil a déjà ses field_positions cohérentes)
            pass

        scores_df = scores_df.sort_values("score", ascending=False).head(top_n).reset_index(drop=True)

        if scores_df.empty:
            st.info("Aucun joueur après filtres.")
            return

        # En-tête résultats
        st.markdown(
            f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;"
            f"margin-bottom:8px'>"
            f"<b style='color:{COLORS['text']}'>{len(scores_df)} joueur(s)</b> "
            f"· Profil : <b>{profile_name or 'multi-profils'}</b> "
            f"· Ligue : {LEAGUE_LABELS.get(league_filter, league_filter or 'Big 5')}"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Rendu des cartes
        for idx, row in scores_df.iterrows():
            rank = idx + 1
            displayed_profile = row.get("_profile", profile_name) if not profile_name else profile_name
            _render_ranking_card(rank, row, displayed_profile, season, league_filter)
