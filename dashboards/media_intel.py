"""
Dashboard Intelligence Médias — veille automatique sur les gros médias foot FR.
Détecte les 20 plus grandes tendances des 7 derniers jours et propose
des visualisations ElevenField associées.

Persistance : les résultats sont sauvegardés dans media/cache.json.
L'analyse ne tourne QUE sur clic du bouton Rafraîchir.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from config import COLORS, SEASONS
from components.kpi_cards import render_section_header

# ── Cache disque ──────────────────────────────────────────────────────────────
_CACHE_PATH = Path(__file__).parent.parent / "media" / "cache.json"


def _load_cache() -> dict | None:
    """Charge le cache JSON. Retourne None si absent ou corrompu."""
    try:
        if _CACHE_PATH.exists():
            return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _save_cache(payload: dict) -> None:
    """Écrit le cache JSON sur disque."""
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        st.warning(f"Impossible d'écrire le cache : {e}")


# ── Couleurs urgence ──────────────────────────────────────────────────────────
URGENCY_COLOR = {
    "high":   "#ef4444",
    "medium": "#f59e0b",
    "low":    "#22c55e",
}
URGENCY_LABEL = {
    "high":   "🔴 Prioritaire",
    "medium": "🟡 À suivre",
    "low":    "🟢 Contexte",
}

# Mapping dashboard_key → _goto key (app.py)
DASHBOARD_GOTO = {
    "team_overview":  "team",
    "player_profile": "player",
    "match_analysis": "match",
    "database":       "database",
    "comparison":     "compare",
}

DASHBOARD_LABEL = {
    "team_overview":  "🏟️ Vue Équipe",
    "player_profile": "👤 Profil Joueur",
    "match_analysis": "📅 Analyse Match",
    "database":       "📊 Base de données",
    "comparison":     "⚖️ Comparaison",
}


# ── Navigation ────────────────────────────────────────────────────────────────

def _navigate(dashboard_key: str, entity: str, entity_type: str,
               fbref_entity: str | None) -> None:
    actual   = fbref_entity or entity
    goto_key = DASHBOARD_GOTO.get(dashboard_key, "database")
    st.session_state["_goto"] = goto_key
    if entity_type == "club":
        st.session_state["_selected_team_ctx"] = actual
    elif entity_type == "player":
        st.session_state["_selected_player"] = actual
    st.rerun()


# ── Carte de tendance ──────────────────────────────────────────────────────────

def _render_trend_card(trend: dict, season: str, league: str, idx: int) -> None:
    from media.analyzer import NARRATIVE_META, match_entity_to_fbref

    narrative   = trend.get("narrative_type", "other")
    meta        = NARRATIVE_META.get(narrative, NARRATIVE_META["other"])
    urgency     = trend.get("urgency", meta["urgency_default"])
    border_col  = URGENCY_COLOR.get(urgency, COLORS["border"])
    icon        = meta["icon"]
    entity      = trend.get("entity", "")
    entity_type = trend.get("entity_type", "other")
    theme       = trend.get("theme", "")
    sources     = ", ".join(trend.get("sources", [])[:3])
    art_count   = trend.get("article_count", 0)
    headline    = trend.get("headline_example", "")
    rank        = trend.get("rank", idx + 1)
    vizs        = trend.get("suggested_visualizations", [])

    # Matching FBref (cache session — ne recharge pas la base à chaque render)
    cache_key = f"_fbref_{entity}_{entity_type}"
    if cache_key not in st.session_state:
        league_arg = None if league == "Toutes les ligues" else league
        st.session_state[cache_key] = match_entity_to_fbref(
            entity, entity_type, season, league_arg
        )
    fbref_entity = st.session_state[cache_key]

    st.markdown(
        f"""
<div style="
    background:{COLORS['card']};
    border-left:4px solid {border_col};
    border-radius:10px;
    padding:14px 16px;
    margin-bottom:12px;
">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
    <span style="font-size:1.3rem">{icon}</span>
    <div>
      <div style="font-size:0.7rem;color:{border_col};font-weight:700;
                  text-transform:uppercase;letter-spacing:0.07em">
        #{rank} · {URGENCY_LABEL.get(urgency,'')} · {meta['label']}
      </div>
      <div style="font-size:1.05rem;font-weight:800;color:{COLORS['text']}">{theme}</div>
    </div>
  </div>
  <div style="font-size:0.78rem;color:{COLORS['text_muted']};margin-bottom:8px">
    📰 {art_count} article{"s" if art_count > 1 else ""} · {sources}
  </div>
  <div style="font-size:0.82rem;color:{COLORS['text_muted']};
              font-style:italic;border-left:2px solid {COLORS['border']};
              padding-left:8px;margin-bottom:10px">
    « {headline} »
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if vizs:
        btn_cols = st.columns(min(len(vizs), 3))
        for j, viz in enumerate(vizs[:3]):
            dash_key = viz.get("dashboard_key", "database")
            label    = viz.get("label", DASHBOARD_LABEL.get(dash_key, "Analyser"))
            descr    = viz.get("description", "")
            matched  = fbref_entity is not None
            help_txt = descr
            if not matched and entity_type in ("club", "player"):
                help_txt += f"\n⚠️ '{entity}' non trouvé en base — navigation sans pré-sélection."
            with btn_cols[j]:
                if st.button(label, key=f"media_btn_{idx}_{j}",
                             use_container_width=True, help=help_txt):
                    _navigate(dash_key, entity, entity_type, fbref_entity)


# ── Render principal ──────────────────────────────────────────────────────────

def render(season: str = None, league: str = "Toutes les ligues") -> None:
    if season is None:
        season = list(SEASONS.keys())[-1]

    st.markdown(
        f"<h2 style='color:{COLORS['text']};margin-bottom:0'>📰 Intelligence Médias</h2>"
        f"<div style='color:{COLORS['text_muted']};font-size:0.85rem;margin-bottom:14px'>"
        f"Veille automatique · Top 20 tendances · 7 derniers jours</div>",
        unsafe_allow_html=True,
    )

    # ── Contrôles ─────────────────────────────────────────────────────────────
    col_info, col_btn = st.columns([5, 1])

    cache = _load_cache()

    with col_info:
        if cache:
            fetched_at = cache.get("fetched_at", "")
            art_n      = cache.get("article_count", 0)
            src_n      = cache.get("source_count", 0)
            try:
                dt    = datetime.fromisoformat(fetched_at)
                delta = datetime.now() - dt
                hrs   = int(delta.total_seconds() // 3600)
                mins  = int((delta.total_seconds() % 3600) // 60)
                age   = f"{hrs}h {mins}min" if hrs else f"{mins} min"
            except Exception:
                age = "?"
            st.caption(
                f"Dernière analyse : **il y a {age}** · "
                f"{art_n} articles · {src_n} sources"
            )
        else:
            st.caption("Aucune analyse en cache. Clique sur **🔄 Rafraîchir** pour lancer l'analyse.")

    with col_btn:
        refresh = st.button("🔄 Rafraîchir", use_container_width=True, type="primary")

    # ── Lancement uniquement sur clic ─────────────────────────────────────────
    if refresh:
        cache = _run_analysis_and_save(season, league)
        if cache is None:
            return

    if not cache:
        st.info(
            "📡 Clique sur **🔄 Rafraîchir** pour lancer la première analyse.\n\n"
            "L'algo récupère les articles des 7 derniers jours et détecte "
            "les 20 plus grandes tendances médiatiques."
        )
        return

    trends = cache.get("trends", [])
    errors = cache.get("errors", [])
    meta   = cache.get("meta", {})

    if errors:
        with st.expander(f"⚠️ {len(errors)} source(s) inaccessible(s)", expanded=False):
            for e in errors:
                st.caption(e)

    if meta.get("error"):
        st.error(f"Erreur d'analyse : {meta['error']}")
        return

    if not trends:
        st.info("Aucune tendance détectée dans le cache. Relance l'analyse.")
        return

    # ── Légende urgence ───────────────────────────────────────────────────────
    st.markdown(
        f"<div style='display:flex;gap:20px;margin-bottom:18px;font-size:0.8rem'>"
        f"<span style='color:{URGENCY_COLOR['high']};font-weight:700'>🔴 Prioritaire</span>"
        f"<span style='color:{URGENCY_COLOR['medium']};font-weight:700'>🟡 À suivre</span>"
        f"<span style='color:{URGENCY_COLOR['low']};font-weight:700'>🟢 Contexte</span>"
        f"<span style='color:{COLORS['text_muted']}'>· Clique un bouton pour ouvrir l'analyse dans ElevenField</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Méta LLM (discret) ────────────────────────────────────────────────────
    if meta.get("input_tokens"):
        cost = (meta["input_tokens"] * 0.8 + meta["output_tokens"] * 4) / 1_000_000
        st.caption(
            f"🤖 {meta.get('model','?')} · "
            f"{meta['input_tokens']:,} → {meta['output_tokens']:,} tokens · "
            f"~{cost:.4f}$ · {meta.get('trend_count', len(trends))} tendances"
        )

    st.divider()

    # ── Tri + affichage ───────────────────────────────────────────────────────
    urgency_order = {"high": 0, "medium": 1, "low": 2}
    sorted_trends = sorted(
        trends,
        key=lambda t: (
            urgency_order.get(t.get("urgency", "low"), 2),
            -t.get("article_count", 0),
        ),
    )

    col_a, col_b = st.columns(2)
    for i, trend in enumerate(sorted_trends[:20]):
        with (col_a if i % 2 == 0 else col_b):
            _render_trend_card(trend, season, league, i)


# ── Fetch + LLM + sauvegarde ──────────────────────────────────────────────────

def _run_analysis_and_save(season: str, league: str) -> dict | None:
    """Lance le fetch RSS + Claude Haiku, sauvegarde en cache JSON, retourne le payload."""

    try:
        api_key = st.secrets["anthropic"]["api_key"]
    except Exception:
        st.error(
            "Clé API Anthropic introuvable dans `.streamlit/secrets.toml`.\n"
            "```toml\n[anthropic]\napi_key = \"sk-ant-...\"\n```"
        )
        return None

    # Étape 1 — fetch RSS
    with st.spinner("📡 Récupération des articles RSS…"):
        try:
            from media.fetcher import fetch_articles
            articles, fetch_errors = fetch_articles(days=7)
        except Exception as e:
            st.error(f"Erreur fetch RSS : {e}")
            return None

    if not articles:
        st.warning("Aucun article récupéré. Vérifie ta connexion internet.")
        return None

    unique_sources = len({a["source"] for a in articles})

    # Invalide le cache de matching FBref
    for key in list(st.session_state.keys()):
        if key.startswith("_fbref_"):
            del st.session_state[key]

    # Étape 2 — analyse Claude Haiku
    with st.spinner(
        f"🧠 Analyse de {len(articles)} articles ({unique_sources} sources) "
        f"avec Claude Haiku…"
    ):
        from media.analyzer import analyze_trends
        trends, meta = analyze_trends(articles, api_key)

    # Étape 3 — sauvegarde disque
    payload = {
        "fetched_at":    datetime.now().isoformat(),
        "article_count": len(articles),
        "source_count":  unique_sources,
        "trends":        trends,
        "meta":          meta,
        "errors":        fetch_errors,
    }
    _save_cache(payload)

    st.success(f"✅ {len(trends)} tendances détectées — cache mis à jour.")
    return payload
