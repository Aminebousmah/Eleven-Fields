"""
Composants KPI — cartes de métriques clés injectées via st.markdown.
"""
from __future__ import annotations

import streamlit as st

from config import COLORS


def _card_html(label: str, value: str, delta: str = "", color: str = "") -> str:
    accent = color or COLORS["accent_green"]
    delta_html = (
        f'<div style="font-size:0.75rem;color:{COLORS["text_muted"]};margin-top:2px">{delta}</div>'
        if delta else ""
    )
    return f"""
<div style="
    background:{COLORS['card']};
    border-left:3px solid {accent};
    border-radius:10px;
    padding:14px 16px;
    margin-bottom:8px;
">
  <div style="font-size:0.78rem;color:{COLORS['text_muted']};text-transform:uppercase;
              letter-spacing:0.05em;margin-bottom:4px">{label}</div>
  <div style="font-size:1.6rem;font-weight:700;color:{COLORS['text']};line-height:1">{value}</div>
  {delta_html}
</div>
"""


def render_kpi_row(kpis: list[dict]) -> None:
    """
    Affiche une ligne de cartes KPI.
    kpis : [{"label": str, "value": str, "delta": str, "color": str}, ...]
    """
    cols = st.columns(len(kpis))
    for col, kpi in zip(cols, kpis):
        with col:
            st.markdown(
                _card_html(
                    kpi.get("label", ""),
                    kpi.get("value", "—"),
                    kpi.get("delta", ""),
                    kpi.get("color", ""),
                ),
                unsafe_allow_html=True,
            )


def render_stat_table(
    df,
    columns: list[str],
    labels: dict[str, str] | None = None,
    highlight_col: str | None = None,
) -> None:
    """
    Affiche un DataFrame stylisé avec coloration de la colonne highlight.
    """
    display = df[columns].copy()
    if labels:
        display = display.rename(columns=labels)

    if highlight_col and highlight_col in display.columns:
        styled = display.style.background_gradient(
            subset=[highlight_col],
            cmap="RdYlGn",
            vmin=0, vmax=display[highlight_col].max(),
        )
        st.dataframe(styled, use_container_width=True)
    else:
        st.dataframe(display, use_container_width=True)


def render_section_header(title: str, subtitle: str = "") -> None:
    """En-tête de section avec ligne décorative."""
    st.markdown(
        f"""
<div style="border-left:4px solid {COLORS['accent_green']};
            padding:4px 12px;margin:12px 0 8px 0">
  <div style="font-size:1.1rem;font-weight:700;color:{COLORS['text']}">{title}</div>
  {"<div style='font-size:0.82rem;color:" + COLORS['text_muted'] + "'>" + subtitle + "</div>" if subtitle else ""}
</div>
""",
        unsafe_allow_html=True,
    )
