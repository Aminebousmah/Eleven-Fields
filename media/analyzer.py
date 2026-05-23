"""
Analyzer — envoie les articles à Claude Haiku pour détecter
les 20 plus grandes tendances médiatiques et proposer des visualisations.
"""
from __future__ import annotations

import json
import re
from typing import Optional

# Mapping narrative_type → (goto_key, label lisible)
NARRATIVE_META: dict[str, dict] = {
    "transfer_target":     {"goto": "player",   "icon": "🔄", "label": "Recrue prioritaire",      "urgency_default": "high"},
    "transfer_departure":  {"goto": "player",   "icon": "✈️", "label": "Départ évoqué",           "urgency_default": "medium"},
    "defensive_crisis":    {"goto": "team",     "icon": "🛡️", "label": "Crise défensive",         "urgency_default": "high"},
    "offensive_slump":     {"goto": "team",     "icon": "⚽", "label": "Baisse offensive",        "urgency_default": "medium"},
    "reinforcement_mf":    {"goto": "database", "icon": "🔍", "label": "Recherche milieu",        "urgency_default": "medium"},
    "reinforcement_gk":    {"goto": "database", "icon": "🔍", "label": "Recherche gardien",       "urgency_default": "medium"},
    "reinforcement_fw":    {"goto": "database", "icon": "🔍", "label": "Recherche attaquant",     "urgency_default": "medium"},
    "reinforcement_df":    {"goto": "database", "icon": "🔍", "label": "Recherche défenseur",     "urgency_default": "medium"},
    "hot_form_player":     {"goto": "player",   "icon": "⭐", "label": "Joueur en grande forme",  "urgency_default": "medium"},
    "hot_form_team":       {"goto": "match",    "icon": "🔥", "label": "Équipe en grande forme",  "urgency_default": "low"},
    "cold_form_team":      {"goto": "match",    "icon": "❄️", "label": "Équipe en méforme",       "urgency_default": "high"},
    "injury":              {"goto": "player",   "icon": "🏥", "label": "Blessure",                "urgency_default": "high"},
    "tactical":            {"goto": "team",     "icon": "♟️", "label": "Changement tactique",     "urgency_default": "low"},
    "contract":            {"goto": "player",   "icon": "📝", "label": "Contrat / prolongation",  "urgency_default": "low"},
    "manager_news":        {"goto": "team",     "icon": "🎩", "label": "Actualité entraîneur",    "urgency_default": "medium"},
    "other":               {"goto": "database", "icon": "📰", "label": "Actualité",               "urgency_default": "low"},
}

_SYSTEM_PROMPT = """Tu es un analyste football expert en veille médiatique.
Tu reçois une liste d'articles des médias football français des 7 derniers jours.

Ton objectif : identifier les 20 plus grandes tendances médiatiques (thèmes qui reviennent le plus et/ou les plus importants), puis pour chaque tendance proposer 1 à 3 visualisations concrètes réalisables avec un dashboard de stats football (radars, percentiles, classements, évolution match par match, profils de poste, comparaisons).

Pour chaque tendance, retourne un objet avec exactement ces champs :
- rank (int 1-20)
- theme (str: titre court et percutant en français, max 60 caractères)
- entity (str: nom exact du club OU du joueur principal, tel qu'écrit dans les articles)
- entity_type ("club" | "player" | "competition" | "other")
- narrative_type (une valeur parmi : transfer_target, transfer_departure, defensive_crisis, offensive_slump, reinforcement_mf, reinforcement_gk, reinforcement_fw, reinforcement_df, hot_form_player, hot_form_team, cold_form_team, injury, tactical, contract, manager_news, other)
- article_count (int: estimation du nombre d'articles sur ce thème)
- sources (list[str]: 2-4 médias qui en parlent le plus)
- headline_example (str: copie exacte du titre d'un article représentatif, max 100 caractères)
- urgency ("high" | "medium" | "low" — high = breaking/crise, medium = suivi, low = contexte)
- suggested_visualizations (list de 1 à 3 objets) :
  Chaque visualisation doit avoir :
  - label (str: texte du bouton d'action, commence par un emoji, max 45 caractères)
  - dashboard_key (str: une valeur parmi team_overview, player_profile, match_analysis, database, comparison)
  - description (str: description courte de ce qu'on va analyser, max 80 caractères)

RÈGLES IMPORTANTES :
- Regroupe les articles sur le même sujet en une seule tendance (pas de doublons)
- Classe par importance décroissante (volume médiatique + impact)
- Si l'entité est un joueur, propose toujours une visualisation dans player_profile
- Si crise défensive/offensive → propose team_overview ET match_analysis
- Si recherche de renfort → propose database avec le bon profil de poste
- Retourne UNIQUEMENT du JSON valide, sans texte avant ou après
- Format exact : {"trends": [...]}"""


def analyze_trends(articles: list[dict], api_key: str) -> tuple[list[dict], dict]:
    """
    Envoie les articles à Claude Haiku et retourne (trends, metadata).
    trends = liste de dicts structurés
    metadata = {model, input_tokens, output_tokens, article_count}
    """
    if not articles:
        return [], {"error": "Aucun article à analyser."}

    try:
        import anthropic
    except ImportError:
        return [], {"error": "Package 'anthropic' non installé. Lancer : pip install anthropic"}

    client = anthropic.Anthropic(api_key=api_key)

    # Formate les articles pour le prompt (max 400 articles, ~300 tokens chacun max)
    batch = articles[:400]
    articles_text = "\n".join(
        f"[{a['source']} · {a['date']}] {a['title']}"
        + (f" — {a['summary'][:200]}" if a.get("summary") else "")
        for a in batch
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8192,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Voici {len(batch)} articles des 7 derniers jours :\n\n"
                        f"{articles_text}\n\n"
                        f"Identifie les 20 plus grandes tendances médiatiques."
                    ),
                }
            ],
        )
    except Exception as e:
        return [], {"error": str(e)}

    raw = response.content[0].text.strip()

    # Nettoie les éventuels blocs markdown
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
        trends = data.get("trends", [])
    except json.JSONDecodeError as e:
        return [], {"error": f"JSON invalide : {e}", "raw": raw[:500]}

    metadata = {
        "model":          response.model,
        "input_tokens":   response.usage.input_tokens,
        "output_tokens":  response.usage.output_tokens,
        "article_count":  len(batch),
        "trend_count":    len(trends),
    }
    return trends, metadata


def match_entity_to_fbref(
    entity: str,
    entity_type: str,
    season: str,
    league: Optional[str] = None,
) -> Optional[str]:
    """
    Tente de matcher l'entité LLM vers un nom FBref exact via rapidfuzz.
    Retourne le nom FBref ou None si pas de match fiable.
    """
    if not entity or entity_type not in ("club", "player"):
        return None

    try:
        from rapidfuzz import process, fuzz
        from data.loader import load_team_season_stats, load_player_season_stats
        from transfermarkt.matcher import _normalize
    except ImportError:
        return None

    norm = _normalize(entity)

    try:
        if entity_type == "club":
            df = load_team_season_stats("standard", [season])
            if league and league != "Toutes les ligues":
                df = df[df["league"] == league]
            if df.empty:
                return None
            candidates = df["team"].dropna().unique().tolist()
            result = process.extractOne(
                norm, [_normalize(t) for t in candidates],
                scorer=fuzz.WRatio, score_cutoff=72,
            )
            if result:
                return candidates[result[2]]

        elif entity_type == "player":
            df = load_player_season_stats("standard", [season])
            if league and league != "Toutes les ligues":
                df = df[df["league"] == league]
            if df.empty:
                return None
            candidates = df["player"].dropna().unique().tolist()
            result = process.extractOne(
                norm, [_normalize(p) for p in candidates],
                scorer=fuzz.WRatio, score_cutoff=75,
            )
            if result:
                return candidates[result[2]]
    except Exception:
        pass

    return None
