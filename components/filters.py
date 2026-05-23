"""
Filtres réutilisables.

Architecture :
  - Sidebar : uniquement les filtres GLOBAUX (saison, ligue).
  - Chaque dashboard utilise des sélecteurs CONTEXTUELS (select_team,
    select_player, select_two_teams, select_two_players) placés EN HAUT du
    contenu de la page, pas dans la sidebar.
  - Les filtres globaux vivent dans st.session_state (season_idx, league).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config import SEASONS, LEAGUES, LEAGUE_LABELS, COLORS
from data.loader import load_team_season_stats, load_player_season_stats
from components.flags import flag_img_html

# Transfermarkt optionnel pour les previews
try:
    from transfermarkt.matcher import (
        get_club_logo, match_club, format_value,
        match_player, get_player_value_season,
    )
    _TM = True
except Exception:
    _TM = False
    def get_club_logo(*a, **kw): return None
    def match_club(*a, **kw): return None
    def format_value(v): return "—"
    def match_player(*a, **kw): return None
    def get_player_value_season(*a, **kw): return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _init_state(key: str, default) -> None:
    if key not in st.session_state:
        st.session_state[key] = default


def _team_preview_card(team: str, season: str, league: str | None) -> None:
    """Mini carte de prévisualisation pour un club (logo + stats clés)."""
    logo_url = get_club_logo(team, league) if _TM else None
    tm_info = match_club(team, league) if _TM else None

    std = load_team_season_stats("standard", [season])
    if league:
        std = std[std["league"] == league]
    row = std[std["team"] == team]

    def _fmt(v, d=1):
        try:
            return f"{float(v):.{d}f}"
        except Exception:
            return "—"

    xg   = _fmt(row.iloc[0].get("xG")   if not row.empty else "—")
    poss = _fmt(row.iloc[0].get("Poss") if not row.empty else "—") + "%"
    gls  = _fmt(row.iloc[0].get("Gls")  if not row.empty else "—", 0)
    pretty_name = (
        tm_info.get("pretty_name", team)
        if tm_info and "pretty_name" in tm_info else team
    )

    # Colours as variables to avoid backslash-in-f-string
    c_card   = COLORS["card"]
    c_border = COLORS["border"]
    c_text   = COLORS["text"]
    c_muted  = COLORS["text_muted"]

    if logo_url:
        logo_html = (
            "<img src='" + logo_url + "' style='width:44px;height:44px;"
            "object-fit:contain;border-radius:4px;flex-shrink:0'"
            " onerror=\"this.style.display='none'\">"
        )
    else:
        logo_html = (
            "<div style='width:44px;height:44px;background:" + c_card + ";"
            "border-radius:4px;display:flex;align-items:center;"
            "justify-content:center;font-size:20px'>🏟️</div>"
        )

    card_html = (
        "<div style='display:flex;align-items:center;gap:10px;padding:10px 14px;"
        "background:" + c_card + ";border:1px solid " + c_border + ";"
        "border-radius:10px;margin-top:6px'>"
        + logo_html +
        "<div>"
        "<div style='font-size:1rem;font-weight:700;color:" + c_text + "'>"
        + pretty_name +
        "</div>"
        "<div style='font-size:0.78rem;color:" + c_muted + ";margin-top:2px'>"
        "xG : <b style='color:" + c_text + "'>" + xg + "</b> &nbsp;·&nbsp; "
        "Possession : <b style='color:" + c_text + "'>" + poss + "</b> &nbsp;·&nbsp; "
        "Buts : <b style='color:" + c_text + "'>" + gls + "</b>"
        "</div></div></div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)


def _player_preview_card(
    player: str, team: str, pos: str, season: str, league: str | None,
) -> None:
    """Mini carte de prévisualisation pour un joueur (photo + stats clés)."""
    photo_url = None
    market_value_str = ""
    if _TM:
        tm = match_player(player, fbref_league=league)
        if tm:
            photo_url = tm.get("image_url")
            try:
                mv = get_player_value_season(player, season, league)
                if mv is not None and pd.notna(mv):
                    market_value_str = format_value(mv)
            except Exception:
                pass

    std = load_player_season_stats("standard", [season])
    if league:
        std = std[std["league"] == league]
    row = std[(std["player"] == player) & (std["team"] == team)]

    def _fmt(v, d=1):
        try:
            return f"{float(v):.{d}f}"
        except Exception:
            return "—"

    gls    = _fmt(row.iloc[0].get("Gls")    if not row.empty else "—", 0)
    ast_   = _fmt(row.iloc[0].get("Ast")    if not row.empty else "—", 0)
    mins   = _fmt(row.iloc[0].get("Min")    if not row.empty else "—", 0)
    age    = _fmt(row.iloc[0].get("age")    if not row.empty else "—", 0)
    nation = ""
    if not row.empty:
        raw_nat = row.iloc[0].get("nation") or ""
        # FBref stocke "fr FRA" ou juste "FRA" — on prend le dernier token
        nation = str(raw_nat).split()[-1] if str(raw_nat).strip() else ""

    c_card   = COLORS["card"]
    c_border = COLORS["border"]
    c_text   = COLORS["text"]
    c_muted  = COLORS["text_muted"]
    c_gold   = COLORS["accent_gold"]

    if photo_url:
        av_html = (
            "<img src='" + photo_url + "' style='width:52px;height:52px;"
            "object-fit:cover;border-radius:50%;border:2px solid " + c_border + ";"
            "flex-shrink:0' onerror=\"this.style.display='none'\">"
        )
    else:
        av_html = (
            "<div style='width:52px;height:52px;background:" + c_card + ";"
            "border-radius:50%;border:2px solid " + c_border + ";"
            "display:flex;align-items:center;justify-content:center;"
            "font-size:22px;flex-shrink:0'>👤</div>"
        )

    flag_html = flag_img_html(nation, size=14) if nation else ""
    nat_html  = (
        " &nbsp;·&nbsp; " + flag_html + "<span style='color:" + c_text + "'>" + nation + "</span>"
        if nation else ""
    )
    val_html = (
        " &nbsp;·&nbsp; 💶 <b style='color:" + c_gold + "'>" + market_value_str + "</b>"
        if market_value_str else ""
    )
    card_html = (
        "<div style='display:flex;align-items:center;gap:10px;padding:10px 14px;"
        "background:" + c_card + ";border:1px solid " + c_border + ";"
        "border-radius:10px;margin-top:6px'>"
        + av_html +
        "<div>"
        "<div style='font-size:1rem;font-weight:700;color:" + c_text + "'>" + player + "</div>"
        "<div style='font-size:0.78rem;color:" + c_muted + ";margin-top:1px'>"
        + team + " · " + pos + " · " + age + " ans" + nat_html
        + "</div>"
        "<div style='font-size:0.78rem;color:" + c_muted + ";margin-top:2px'>"
        "⚽ <b style='color:" + c_text + "'>" + gls + "</b> buts &nbsp;·&nbsp; "
        "🎯 <b style='color:" + c_text + "'>" + ast_ + "</b> passes D. &nbsp;·&nbsp; "
        "⏱ <b style='color:" + c_text + "'>" + mins + "</b> min"
        + val_html +
        "</div></div></div>"
    )
    st.markdown(card_html, unsafe_allow_html=True)


# ── Filtres globaux (sidebar) ─────────────────────────────────────────────────

def render_global_filters() -> tuple[str, str]:
    """[Déprécié, conservé pour compat] Sidebar : Saison + Ligue."""
    st.sidebar.markdown(
        f"<div style='font-size:0.72rem;color:{COLORS['text_muted']};"
        f"text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px'>"
        f"Filtres</div>",
        unsafe_allow_html=True,
    )
    return _filter_widgets(st.sidebar)


def render_inline_filters() -> tuple[str, str]:
    """
    Filtres saison + ligue au-dessus du contenu principal (pas dans la sidebar).
    Retourne (season_key, league). État conservé via session_state.
    """
    c1, c2, _ = st.columns([1.2, 2, 4])
    return _filter_widgets((c1, c2))


def _filter_widgets(target) -> tuple[str, str]:
    """Implémentation partagée des 2 selectbox saison + ligue."""
    season_labels = list(SEASONS.values())
    season_keys = list(SEASONS.keys())
    _init_state("season_idx", len(season_keys) - 1)

    league_options = ["Toutes les ligues"] + LEAGUES

    # target est soit st.sidebar, soit un tuple de colonnes (c1, c2)
    if isinstance(target, tuple):
        c1, c2 = target
        with c1:
            season_label = st.selectbox(
                "Saison",
                options=season_labels,
                index=st.session_state["season_idx"],
                key="season_select",
            )
        with c2:
            league = st.selectbox(
                "Ligue",
                options=league_options,
                format_func=lambda x: LEAGUE_LABELS.get(x, x),
                key="league_select",
                index=league_options.index(
                    st.session_state.get("league", "Toutes les ligues")
                ) if st.session_state.get("league", "Toutes les ligues") in league_options else 0,
            )
    else:
        season_label = target.selectbox(
            "Saison",
            options=season_labels,
            index=st.session_state["season_idx"],
            key="season_select",
        )
        league = target.selectbox(
            "Ligue",
            options=league_options,
            format_func=lambda x: LEAGUE_LABELS.get(x, x),
            key="league_select",
            index=league_options.index(
                st.session_state.get("league", "Toutes les ligues")
            ) if st.session_state.get("league", "Toutes les ligues") in league_options else 0,
        )

    st.session_state["season_idx"] = season_labels.index(season_label)
    season_key = season_keys[st.session_state["season_idx"]]
    st.session_state["league"] = league
    return season_key, league


# ── Gate "Afficher" : bouton qui révèle les visualisations ───────────────────

def render_show_gate(
    state_key: str,
    label: str = "📊  Afficher",
    hint: str = "Configure tes filtres ci-dessus, puis clique sur Afficher pour générer l'analyse.",
    icon: str = "◉",
    primary_text: str = "Configure tes filtres",
) -> bool:
    """
    Empty state animée + bouton 'Afficher'. Tant que l'utilisateur n'a pas
    cliqué, l'onglet affiche un message vide pulsé. Une fois cliqué, l'état
    reste True jusqu'au changement d'onglet (reset auto par app.py).

    Utilisation :

        # ... filtres ...
        if not render_show_gate("ranking_player"):
            return
        # ... visualisations ...
    """
    flag = f"{state_key}_shown"
    if flag not in st.session_state:
        st.session_state[flag] = False

    if st.session_state[flag]:
        # Déjà cliqué : petit bouton Réinitialiser à droite des filtres
        c1, c2 = st.columns([1, 5])
        with c1:
            if st.button("↺  Réinitialiser", key=f"reset_{state_key}_btn",
                         use_container_width=True):
                st.session_state[flag] = False
                st.rerun()
        return True

    # Pas encore cliqué : empty state pulsée + bouton primary
    from components.design import empty_state
    st.markdown(
        empty_state(primary=primary_text, secondary=hint, icon=icon),
        unsafe_allow_html=True,
    )

    # Bouton Afficher centré sous l'empty state
    _, c_btn, _ = st.columns([2, 1, 2])
    with c_btn:
        clicked = st.button(label, key=f"show_{state_key}_btn",
                            type="primary", use_container_width=True)

    if clicked:
        st.session_state[flag] = True
        st.rerun()
    return False


# ── Sélecteurs contextuels (en haut du contenu) ───────────────────────────────

def _teams_for(season_key: str, league: str) -> list[str]:
    df = load_team_season_stats("standard", [season_key])
    if league != "Toutes les ligues":
        df = df[df["league"] == league]
    return sorted(df["team"].dropna().unique().tolist())


def select_team(
    season_key: str,
    league: str,
    label: str = "Équipe",
    key: str = "team_ctx",
    default: str | None = None,
    show_preview: bool = True,
) -> str:
    """Sélecteur d'équipe unique (contextuel, affiché dans le contenu)."""
    teams = _teams_for(season_key, league)
    if not teams:
        st.warning("Aucune équipe disponible pour ces filtres.")
        return ""

    # Session state partagé : si on a sélectionné via Database, on récupère la valeur
    persistent_key = f"_selected_{key}"
    _init_state(persistent_key, default or teams[0])
    current = st.session_state[persistent_key]
    if current not in teams:
        current = teams[0]

    selected = st.selectbox(
        label,
        teams,
        index=teams.index(current),
        key=f"{key}_select",
    )
    st.session_state[persistent_key] = selected

    # Prévisualisation mini-carte
    if show_preview:
        league_filter = None if league == "Toutes les ligues" else league
        _team_preview_card(selected, season_key, league_filter)

    return selected


def select_two_teams(
    season_key: str,
    league: str,
    key_prefix: str = "cmp",
) -> tuple[str, str]:
    """Sélecteur de deux équipes côte-à-côte pour comparaison."""
    teams = _teams_for(season_key, league)
    if len(teams) < 2:
        st.warning("Moins de 2 équipes disponibles.")
        return teams[0] if teams else "", ""

    k1, k2 = f"_{key_prefix}_t1", f"_{key_prefix}_t2"
    _init_state(k1, teams[0])
    _init_state(k2, teams[1])

    c1, c2 = st.columns(2)
    with c1:
        t1 = st.selectbox(
            "🟢 Club A",
            teams,
            index=teams.index(st.session_state[k1]) if st.session_state[k1] in teams else 0,
            key=f"{key_prefix}_t1_select",
        )
    with c2:
        t2 = st.selectbox(
            "🔴 Club B",
            teams,
            index=teams.index(st.session_state[k2]) if st.session_state[k2] in teams else 1,
            key=f"{key_prefix}_t2_select",
        )
    st.session_state[k1] = t1
    st.session_state[k2] = t2
    return t1, t2


def _render_player_suggestions(
    df: "pd.DataFrame",
    players: list[str],
    key_prefix: str,
    max_shown: int = 8,
) -> None:
    """
    Affiche une liste de suggestions de joueurs en temps réel sous la recherche.
    Chaque ligne montre : drapeau · nom · équipe · poste · âge · Gls · Ast.
    """
    c_card   = COLORS["card"]
    c_border = COLORS["border"]
    c_text   = COLORS["text"]
    c_muted  = COLORS["text_muted"]
    c_green  = COLORS["accent_green"]

    shown = players[:max_shown]
    more  = len(players) - max_shown

    def _fmt(v, d=0):
        try:
            return str(int(float(v))) if d == 0 else f"{float(v):.{d}f}"
        except Exception:
            return "—"

    rows_html = ""
    for p in shown:
        row = df[df["player"] == p]
        if row.empty:
            continue
        r       = row.iloc[0]
        team    = str(r.get("team", ""))
        pos     = str(r.get("pos", "")).split(",")[0]
        age     = _fmt(r.get("age", ""))
        gls     = _fmt(r.get("Gls", "—"))
        ast_    = _fmt(r.get("Ast", "—"))
        raw_nat = str(r.get("nation", "") or "")
        nat_code = raw_nat.split()[-1] if raw_nat.strip() else ""
        flag    = flag_img_html(nat_code, size=14) if nat_code else ""

        rows_html += (
            "<div style='display:flex;align-items:center;gap:8px;"
            "padding:6px 12px;border-bottom:1px solid " + c_border + ";"
            "transition:background 0.15s'>"
            # drapeau + nom
            "<div style='display:flex;align-items:center;gap:6px;min-width:180px'>"
            + flag +
            "<span style='font-weight:600;color:" + c_text + ";font-size:0.88rem'>" + p + "</span>"
            "</div>"
            # équipe · poste
            "<div style='color:" + c_muted + ";font-size:0.8rem;min-width:130px'>"
            + team + " &nbsp;·&nbsp; " + pos
            + "</div>"
            # âge
            "<div style='color:" + c_muted + ";font-size:0.8rem;width:50px'>"
            + (age + " ans" if age != "—" else "") + "</div>"
            # stats
            "<div style='margin-left:auto;display:flex;gap:14px;font-size:0.8rem'>"
            "<span>⚽ <b style='color:" + c_green + "'>" + gls + "</b></span>"
            "<span>🎯 <b style='color:" + c_text + "'>" + ast_ + "</b></span>"
            "</div>"
            "</div>"
        )

    if more > 0:
        rows_html += (
            "<div style='text-align:center;padding:6px;font-size:0.76rem;color:" + c_muted + "'>"
            "… et " + str(more) + " autre(s) — affinez la recherche"
            "</div>"
        )

    html = (
        "<div style='border:1px solid " + c_border + ";"
        "border-radius:8px;overflow:hidden;margin-top:4px;margin-bottom:8px;"
        "background:" + c_card + "'>"
        "<div style='padding:6px 12px;font-size:0.72rem;color:" + c_muted + ";"
        "text-transform:uppercase;letter-spacing:0.06em;border-bottom:1px solid " + c_border + "'>"
        + str(len(players)) + " résultat(s) — sélectionnez dans la liste ci-dessous"
        "</div>"
        + rows_html
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def select_player(
    season_key: str,
    league: str,
    key_prefix: str = "player",
    allow_cross_team: bool = True,
    min_minutes_default: int = 500,
    show_preview: bool = True,
) -> tuple[str, str, str]:
    """
    Sélecteur de joueur multi-critères (Position / Minutes / Recherche / Joueur).
    Retourne (player, team, position_group).
    """
    pdf = load_player_season_stats("standard", [season_key])
    if pdf.empty or "league" not in pdf.columns:
        st.warning(
            f"⚠️ Aucune donnée joueur trouvée pour **{season_key}**. "
            "Vérifie que les CSV `FB_player_season_stats_*.csv` sont bien présents."
        )
        return "", "", ""
    if league != "Toutes les ligues":
        pdf = pdf[pdf["league"] == league]

    if pdf.empty:
        st.warning("Aucun joueur disponible pour cette ligue.")
        return "", "", ""

    # Filtres en ligne
    c1, c2, c3 = st.columns([1, 1, 2])

    with c1:
        position = st.selectbox(
            "Position",
            ["Tous", "FW", "MF", "DF", "GK"],
            key=f"{key_prefix}_pos",
        )

    with c2:
        min_minutes = st.select_slider(
            "Minutes min.",
            options=[0, 300, 500, 900, 1500, 2000, 3000],
            value=min_minutes_default,
            key=f"{key_prefix}_min",
        )

    with c3:
        search = st.text_input(
            "Rechercher un joueur",
            placeholder="Nom…",
            key=f"{key_prefix}_search",
        )

    # Application des filtres
    df = pdf.copy()
    if position != "Tous":
        df = df[df["pos"].astype(str).str.contains(position, na=False)]
    if "Min" in df.columns:
        df = df[pd.to_numeric(df["Min"], errors="coerce").fillna(0) >= min_minutes]
    if search:
        df = df[df["player"].astype(str).str.contains(search, case=False, na=False)]

    players = sorted(df["player"].dropna().unique().tolist())
    if not players:
        st.info("Aucun joueur ne correspond aux filtres.")
        return "", "", ""

    # ── Suggestions live quand une recherche est active ──────────────────────
    if search and len(players) > 0:
        _render_player_suggestions(df, players, key_prefix)

    persistent_key = f"_selected_{key_prefix}"
    _init_state(persistent_key, players[0])
    current = st.session_state[persistent_key]
    if current not in players:
        current = players[0]

    player = st.selectbox(
        f"Joueur ({len(players)} disponibles)",
        players,
        index=players.index(current),
        key=f"{key_prefix}_select",
    )
    st.session_state[persistent_key] = player

    # Récupère l'équipe + la position du joueur
    row = df[df["player"] == player]
    if row.empty:
        return player, "", ""
    team = row["team"].values[0]
    pos_str = str(row["pos"].values[0]) if "pos" in row.columns else ""
    pos_group = _pos_to_group(pos_str)

    # Prévisualisation mini-carte
    if show_preview:
        league_filter = None if league == "Toutes les ligues" else league
        _player_preview_card(player, team, pos_str, season_key, league_filter)

    return player, team, pos_group


def select_two_players(
    season_key: str,
    league: str,
) -> tuple[tuple[str, str], tuple[str, str]]:
    """Deux sélecteurs joueur côte-à-côte. Retourne ((p1,t1), (p2,t2))."""
    pdf = load_player_season_stats("standard", [season_key])
    if league != "Toutes les ligues":
        pdf = pdf[pdf["league"] == league]

    if pdf.empty:
        return ("", ""), ("", "")

    cA, cB = st.columns(2)

    with cA:
        st.markdown(f"<div style='color:{COLORS['accent_green']};font-weight:700'>🟢 Joueur A</div>",
                    unsafe_allow_html=True)
        p1, t1, _ = select_player(season_key, league, key_prefix="pA")
    with cB:
        st.markdown(f"<div style='color:{COLORS['accent_red']};font-weight:700'>🔴 Joueur B</div>",
                    unsafe_allow_html=True)
        p2, t2, _ = select_player(season_key, league, key_prefix="pB")

    return (p1, t1), (p2, t2)


def select_two_players_compact(
    season_key: str,
    league: str,
    label_a: str = "Joueur A",
    label_b: str = "Joueur B",
) -> tuple[tuple[str, str], tuple[str, str]]:
    """
    Variante compacte horizontale : 2 selectbox autocomplete sans filtres.
    Retourne ((p1, t1), (p2, t2)).
    Utilisé par les vues "duel" qui veulent un filtre rail compact.
    """
    pdf = load_player_season_stats("standard", [season_key])
    if league != "Toutes les ligues":
        pdf = pdf[pdf["league"] == league]
    if pdf.empty:
        return ("", ""), ("", "")

    # Construit options "Player — Team"
    pdf = pdf.dropna(subset=["player", "team"]).copy()
    pdf["__opt"] = pdf["player"] + " — " + pdf["team"]
    options = sorted(pdf["__opt"].unique().tolist())

    cA, cB = st.columns(2)
    with cA:
        sel_a = st.selectbox(
            label_a, options=options,
            key="duel_pA", placeholder="Recherche…",
        )
    with cB:
        # Pré-sélectionne un joueur différent par défaut
        default_b = options[1] if len(options) > 1 else (options[0] if options else None)
        try:
            idx_b = options.index(st.session_state.get("duel_pB", default_b))
        except ValueError:
            idx_b = 1 if len(options) > 1 else 0
        sel_b = st.selectbox(
            label_b, options=options,
            index=idx_b, key="duel_pB", placeholder="Recherche…",
        )

    def _split(opt: str) -> tuple[str, str]:
        if not opt or " — " not in opt:
            return ("", "")
        p, t = opt.split(" — ", 1)
        return (p.strip(), t.strip())

    return _split(sel_a), _split(sel_b)


# ── Utilitaires ──────────────────────────────────────────────────────────────

def _pos_to_group(pos_str: str) -> str:
    """FBref pos → FW/MF/DF/GK."""
    if pd.isna(pos_str):
        return "MF"
    p = str(pos_str).upper()
    if "GK" in p:
        return "GK"
    if "FW" in p:
        return "FW"
    if "DF" in p:
        return "DF"
    return "MF"
