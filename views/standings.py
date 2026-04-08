"""Standings page — division standings from MLB Stats API with team colors."""

import streamlit as st
import pandas as pd
from data_loader import get_standings

# Primary team colors (hex)
TEAM_COLORS = {
    "Arizona Diamondbacks": "#A71930",
    "Atlanta Braves": "#CE1141",
    "Baltimore Orioles": "#DF4601",
    "Boston Red Sox": "#BD3039",
    "Chicago Cubs": "#0E3386",
    "Chicago White Sox": "#27251F",
    "Cincinnati Reds": "#C6011F",
    "Cleveland Guardians": "#00385D",
    "Colorado Rockies": "#333366",
    "Detroit Tigers": "#0C2340",
    "Houston Astros": "#002D62",
    "Kansas City Royals": "#004687",
    "Los Angeles Angels": "#BA0021",
    "Los Angeles Dodgers": "#005A9C",
    "Miami Marlins": "#00A3E0",
    "Milwaukee Brewers": "#FFC52F",
    "Minnesota Twins": "#002B5C",
    "New York Mets": "#002D72",
    "New York Yankees": "#003087",
    "Oakland Athletics": "#003831",
    "Philadelphia Phillies": "#E81828",
    "Pittsburgh Pirates": "#FDB827",
    "San Diego Padres": "#2F241D",
    "San Francisco Giants": "#FD5A1E",
    "Seattle Mariners": "#0C2C56",
    "St. Louis Cardinals": "#C41E3A",
    "Tampa Bay Rays": "#092C5C",
    "Texas Rangers": "#003278",
    "Toronto Blue Jays": "#134A8E",
    "Washington Nationals": "#AB0003",
    # Sacramento Athletics alias
    "Athletics": "#003831",
}


def _color_team_name(team_name: str) -> str:
    """Return HTML span with team's primary color."""
    color = TEAM_COLORS.get(team_name, "#EAEAEA")
    return f'<span style="color:{color}; font-weight:600;">{team_name}</span>'


def render():
    st.markdown('<div class="section-header">MLB Standings</div>', unsafe_allow_html=True)

    standings = get_standings()

    if standings.empty:
        st.warning("Could not load standings data.")
        return

    all_divisions = standings["Division"].unique().tolist()
    al_divisions = sorted([d for d in all_divisions if "American" in d])
    nl_divisions = sorted([d for d in all_divisions if "National" in d])

    if not al_divisions and not nl_divisions:
        al_divisions = all_divisions[:len(all_divisions) // 2]
        nl_divisions = all_divisions[len(all_divisions) // 2:]

    al_col, nl_col = st.columns(2)

    with al_col:
        st.markdown("### American League")
        for div in al_divisions:
            div_df = standings[standings["Division"] == div].copy()
            if div_df.empty:
                continue

            short_name = div.replace("American League", "AL")
            st.markdown(f"**{short_name}**")

            # Build HTML table with team colors
            _render_standings_table(div_df)

    with nl_col:
        st.markdown("### National League")
        for div in nl_divisions:
            div_df = standings[standings["Division"] == div].copy()
            if div_df.empty:
                continue

            short_name = div.replace("National League", "NL")
            st.markdown(f"**{short_name}**")

            _render_standings_table(div_df)


def _render_standings_table(div_df: pd.DataFrame):
    """Render a division standings table with colored team names."""
    rows_html = ""
    for _, row in div_df.iterrows():
        team_colored = _color_team_name(row["Team"])
        rows_html += (
            f'<tr>'
            f'<td style="padding:6px 12px; border-bottom:1px solid #2A2A4A;">{team_colored}</td>'
            f'<td style="padding:6px 8px; border-bottom:1px solid #2A2A4A; text-align:center;">{row["W"]}</td>'
            f'<td style="padding:6px 8px; border-bottom:1px solid #2A2A4A; text-align:center;">{row["L"]}</td>'
            f'<td style="padding:6px 8px; border-bottom:1px solid #2A2A4A; text-align:center;">{row["PCT"]:.3f}</td>'
            f'<td style="padding:6px 8px; border-bottom:1px solid #2A2A4A; text-align:center;">{row["GB"]}</td>'
            f'<td style="padding:6px 8px; border-bottom:1px solid #2A2A4A; text-align:center;">{row["Streak"]}</td>'
            f'</tr>'
        )

    header = (
        '<th style="padding:8px 12px; text-align:left; color:#8888AA; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px;">Team</th>'
        '<th style="padding:8px 8px; text-align:center; color:#8888AA; font-size:0.75rem; text-transform:uppercase;">W</th>'
        '<th style="padding:8px 8px; text-align:center; color:#8888AA; font-size:0.75rem; text-transform:uppercase;">L</th>'
        '<th style="padding:8px 8px; text-align:center; color:#8888AA; font-size:0.75rem; text-transform:uppercase;">PCT</th>'
        '<th style="padding:8px 8px; text-align:center; color:#8888AA; font-size:0.75rem; text-transform:uppercase;">GB</th>'
        '<th style="padding:8px 8px; text-align:center; color:#8888AA; font-size:0.75rem; text-transform:uppercase;">Streak</th>'
    )

    html = (
        f'<table style="width:100%; border-collapse:collapse; margin-bottom:20px; '
        f'background:linear-gradient(135deg, #1A1A2E 0%, #16213E 100%); border-radius:10px; '
        f'overflow:hidden; border:1px solid #2A2A4A;">'
        f'<thead><tr style="border-bottom:2px solid #E63946;">{header}</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
    )

    st.markdown(html, unsafe_allow_html=True)
