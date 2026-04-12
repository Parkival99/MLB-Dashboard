"""Dashboard page — today's games, who's hot, who's cold, top matchups."""

import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data_loader import (
    get_todays_games,
    get_statcast_data,
    compute_batting_leaders,
    compute_pitching_leaders,
    compute_batter_daily_stats,
    get_pitcher_game_log,
)

# Team colors: (primary for gradient, text color for name visibility)
# Text color uses secondary/accent so names pop against the dark card background
TEAM_COLORS = {
    "Arizona Diamondbacks": ("#A71930", "#E3D4AD"),
    "Atlanta Braves": ("#CE1141", "#CE1141"),
    "Baltimore Orioles": ("#DF4601", "#DF4601"),
    "Boston Red Sox": ("#BD3039", "#BD3039"),
    "Chicago Cubs": ("#0E3386", "#CC3433"),
    "Chicago White Sox": ("#27251F", "#C4CED4"),
    "Cincinnati Reds": ("#C6011F", "#C6011F"),
    "Cleveland Guardians": ("#00385D", "#E31937"),
    "Colorado Rockies": ("#333366", "#C4CED4"),
    "Detroit Tigers": ("#0C2340", "#FA4616"),
    "Houston Astros": ("#002D62", "#EB6E1F"),
    "Kansas City Royals": ("#004687", "#7BB2DD"),
    "Los Angeles Angels": ("#BA0021", "#BA0021"),
    "Los Angeles Dodgers": ("#005A9C", "#5A8FBE"),
    "Miami Marlins": ("#00A3E0", "#00A3E0"),
    "Milwaukee Brewers": ("#12284B", "#FFC52F"),
    "Minnesota Twins": ("#002B5C", "#D31145"),
    "New York Mets": ("#002D72", "#FF5910"),
    "New York Yankees": ("#003087", "#C4CED4"),
    "Oakland Athletics": ("#003831", "#EFB21E"),
    "Philadelphia Phillies": ("#E81828", "#E81828"),
    "Pittsburgh Pirates": ("#27251F", "#FDB827"),
    "San Diego Padres": ("#2F241D", "#FFC425"),
    "San Francisco Giants": ("#FD5A1E", "#FD5A1E"),
    "Seattle Mariners": ("#0C2C56", "#00C2B3"),
    "St. Louis Cardinals": ("#C41E3A", "#C41E3A"),
    "Tampa Bay Rays": ("#092C5C", "#8FBCE6"),
    "Texas Rangers": ("#003278", "#C0111F"),
    "Toronto Blue Jays": ("#134A8E", "#5BA5E1"),
    "Washington Nationals": ("#AB0003", "#AB0003"),
    "Athletics": ("#003831", "#EFB21E"),
}


def _get_color(team: str) -> str:
    """Get primary (gradient) color."""
    if team in TEAM_COLORS:
        return TEAM_COLORS[team][0]
    for full, colors in TEAM_COLORS.items():
        if team in full or full.endswith(team):
            return colors[0]
    return "#1A1A2E"


def _get_text_color(team: str) -> str:
    """Get text color for team name (bright/contrasting)."""
    if team in TEAM_COLORS:
        return TEAM_COLORS[team][1]
    for full, colors in TEAM_COLORS.items():
        if team in full or full.endswith(team):
            return colors[1]
    return "#EAEAEA"


# Team name/abbreviation -> MLB team ID for logo URLs
TEAM_IDS = {
    "Arizona Diamondbacks": 109, "Atlanta Braves": 144, "Baltimore Orioles": 110,
    "Boston Red Sox": 111, "Chicago Cubs": 112, "Chicago White Sox": 145,
    "Cincinnati Reds": 113, "Cleveland Guardians": 114, "Colorado Rockies": 115,
    "Detroit Tigers": 116, "Houston Astros": 117, "Kansas City Royals": 118,
    "Los Angeles Angels": 108, "Los Angeles Dodgers": 119, "Miami Marlins": 146,
    "Milwaukee Brewers": 158, "Minnesota Twins": 142, "New York Mets": 121,
    "New York Yankees": 147, "Athletics": 133, "Oakland Athletics": 133,
    "Philadelphia Phillies": 143, "Pittsburgh Pirates": 134, "San Diego Padres": 135,
    "San Francisco Giants": 137, "Seattle Mariners": 136, "St. Louis Cardinals": 138,
    "Tampa Bay Rays": 139, "Texas Rangers": 140, "Toronto Blue Jays": 141,
    "Washington Nationals": 120,
    # Abbreviations (from Statcast)
    "AZ": 109, "ATL": 144, "BAL": 110, "BOS": 111, "CHC": 112, "CWS": 145,
    "CIN": 113, "CLE": 114, "COL": 115, "DET": 116, "HOU": 117, "KC": 118,
    "LAA": 108, "LAD": 119, "MIA": 146, "MIL": 158, "MIN": 142, "NYM": 121,
    "NYY": 147, "ATH": 133, "OAK": 133, "PHI": 143, "PIT": 134, "SD": 135,
    "SF": 137, "SEA": 136, "STL": 138, "TB": 139, "TEX": 140, "TOR": 141,
    "WSH": 120,
}


def _team_logo_img(team_name: str) -> str:
    """Return an <img> tag for a team logo."""
    team_id = TEAM_IDS.get(team_name)
    if not team_id:
        # Fuzzy match
        for name, tid in TEAM_IDS.items():
            if team_name in name or name.endswith(team_name):
                team_id = tid
                break
    if not team_id:
        return ''
    url = f"https://www.mlbstatic.com/team-logos/{team_id}.svg"
    return (
        f'<img src="{url}" '
        f'style="width:40px;height:40px;margin-right:12px;object-fit:contain;">'
    )


def _render_game_card(game: dict):
    """Render a single game as a styled card with team color gradient."""
    away_color = _get_color(game["away_team"])
    home_color = _get_color(game["home_team"])
    away_text = _get_text_color(game["away_team"])
    home_text = _get_text_color(game["home_team"])
    is_live = "Progress" in game["status"]
    is_final = "Final" in game["status"]

    live_dot = '<span style="color:#FF4444;font-size:0.6rem;">&#9679;</span> ' if is_live else ''

    # Show time for scheduled games, status for live/final
    if is_live or is_final:
        status_text = f'{live_dot}{game["status"]}'
    else:
        time_str = game.get("game_time", "")
        status_text = time_str if time_str else game["status"]

    st.markdown(
        f'<div style="background:linear-gradient(135deg, {away_color}55 0%, #1A1A2E 35%, #1A1A2E 65%, {home_color}55 100%);'
        f'border:1px solid #2A2A4A;border-radius:12px;padding:20px;margin-bottom:12px;'
        f'box-shadow:0 4px 15px rgba(0,0,0,0.3);">'
        f'<div style="text-align:center;font-size:0.75rem;color:#8888AA;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">'
        f'{status_text}</div>'
        f'<div style="display:flex;align-items:center;margin-bottom:8px;">'
        f'<div style="flex:1;min-width:0;">'
        f'<div style="font-weight:600;font-size:1.1rem;color:{away_text};">{game["away_team"]}</div>'
        f'<div style="font-size:0.8rem;color:#8888AA;">{game["away_record"]}</div>'
        f'<div style="font-size:0.85rem;color:#AAAACC;">SP: {game["away_pitcher"]}</div>'
        f'</div>'
        f'<div class="game-score" style="padding:0 10px;font-size:1.6rem;font-weight:700;color:#EAEAEA;text-align:center;white-space:nowrap;">'
        f'{game["away_score"]} - {game["home_score"]}</div>'
        f'<div style="flex:1;min-width:0;text-align:right;">'
        f'<div style="font-weight:600;font-size:1.1rem;color:{home_text};">{game["home_team"]}</div>'
        f'<div style="font-size:0.8rem;color:#8888AA;">{game["home_record"]}</div>'
        f'<div style="font-size:0.85rem;color:#AAAACC;">SP: {game["home_pitcher"]}</div>'
        f'</div></div>'
        f'<div style="text-align:center;font-size:0.75rem;color:#8888AA;margin-top:4px;">'
        f'{game["venue"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render():
    games_label, games = get_todays_games()
    st.markdown(f'<div class="section-header">{games_label}</div>', unsafe_allow_html=True)

    if not games:
        st.info("No games scheduled or data unavailable.")
    else:
        cols_per_row = 3
        for i in range(0, len(games), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                if i + j < len(games):
                    with col:
                        _render_game_card(games[i + j])

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

    # --- Who's Hot / Who's Cold (last 7 days) ---
    st.markdown('<div class="section-header">Who\'s Hot & Who\'s Cold</div>', unsafe_allow_html=True)
    st.caption("Based on last 7 days of Statcast data")

    end = datetime.date.today()
    start = end - datetime.timedelta(days=7)

    with st.spinner("Loading recent performance data..."):
        sc = get_statcast_data(start.isoformat(), end.isoformat())

    if not sc.empty:
        leaders = compute_batting_leaders(sc)

        if not leaders.empty:
            min_pa = 15
            qualified = leaders[leaders["PA"] >= min_pa].copy()

            if not qualified.empty:
                hot_col, cold_col = st.columns(2)

                with hot_col:
                    st.markdown("### 🔥 Hottest Hitters")
                    hot = qualified.nlargest(5, "OPS")
                    for _, row in hot.iterrows():
                        img = _team_logo_img(row.get("Team", ""))
                        ops_val = row.get("OPS", 0)
                        st.markdown(
                            f'<div class="player-row">'
                            f'{img}'
                            f'<div style="flex:1;">'
                            f'<div class="name">{row["Name"]}</div>'
                            f'<div class="detail">{int(row["PA"])} PA &middot; {row["AVG"]:.3f} AVG &middot; {int(row["HR"])} HR &middot; {row["AVG_EV"]:.1f} mph EV</div>'
                            f'</div>'
                            f'<div><span class="stat">{ops_val:.3f} OPS</span> <span class="hot-badge">HOT</span></div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        with st.expander("📊 7-Day Breakdown"):
                            daily = compute_batter_daily_stats(sc, int(row["batter"]))
                            if not daily.empty:
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=daily["game_date"], y=daily["OPS"],
                                    mode="lines+markers",
                                    line=dict(color="#E63946", width=2),
                                    marker=dict(size=8, color="#E63946"),
                                    customdata=daily[["TB", "H_AB", "SO", "HR"]].values,
                                    hovertemplate=(
                                        "<b>%{x|%a %m/%d}</b><br>"
                                        "OPS: %{y:.3f}<br>"
                                        "Total Bases: %{customdata[0]}<br>"
                                        "H-AB: %{customdata[1]}<br>"
                                        "Strikeouts: %{customdata[2]}<br>"
                                        "Home Runs: %{customdata[3]}"
                                        "<extra></extra>"
                                    ),
                                ))
                                fig.update_layout(
                                    height=220,
                                    margin=dict(l=40, r=20, t=10, b=40),
                                    xaxis_title="Date",
                                    yaxis_title="OPS",
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    font=dict(color="#8888AA"),
                                    xaxis=dict(gridcolor="#2A2A4A"),
                                    yaxis=dict(gridcolor="#2A2A4A"),
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.caption("No game-by-game data available.")

                with cold_col:
                    st.markdown("### 🥶 Coldest Hitters")
                    cold = qualified.nsmallest(5, "OPS")
                    for _, row in cold.iterrows():
                        img = _team_logo_img(row.get("Team", ""))
                        ops_val = row.get("OPS", 0)
                        st.markdown(
                            f'<div class="player-row">'
                            f'{img}'
                            f'<div style="flex:1;">'
                            f'<div class="name">{row["Name"]}</div>'
                            f'<div class="detail">{int(row["PA"])} PA &middot; {row["AVG"]:.3f} AVG &middot; {int(row["SO"])} SO &middot; {row["AVG_EV"]:.1f} mph EV</div>'
                            f'</div>'
                            f'<div><span class="stat">{ops_val:.3f} OPS</span> <span class="cold-badge">COLD</span></div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        with st.expander("📊 7-Day Breakdown"):
                            daily = compute_batter_daily_stats(sc, int(row["batter"]))
                            if not daily.empty:
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=daily["game_date"], y=daily["OPS"],
                                    mode="lines+markers",
                                    line=dict(color="#1E90FF", width=2),
                                    marker=dict(size=8, color="#1E90FF"),
                                    customdata=daily[["TB", "H_AB", "SO", "HR"]].values,
                                    hovertemplate=(
                                        "<b>%{x|%a %m/%d}</b><br>"
                                        "OPS: %{y:.3f}<br>"
                                        "Total Bases: %{customdata[0]}<br>"
                                        "H-AB: %{customdata[1]}<br>"
                                        "Strikeouts: %{customdata[2]}<br>"
                                        "Home Runs: %{customdata[3]}"
                                        "<extra></extra>"
                                    ),
                                ))
                                fig.update_layout(
                                    height=220,
                                    margin=dict(l=40, r=20, t=10, b=40),
                                    xaxis_title="Date",
                                    yaxis_title="OPS",
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    font=dict(color="#8888AA"),
                                    xaxis=dict(gridcolor="#2A2A4A"),
                                    yaxis=dict(gridcolor="#2A2A4A"),
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.caption("No game-by-game data available.")
            else:
                st.info("Not enough qualified plate appearances in the last 7 days.")
        else:
            st.info("Could not compute batting leaders from recent data.")
    else:
        st.info("No Statcast data available for the last 7 days.")

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

    # --- Top Pitchers (last 7 days) ---
    st.markdown('<div class="section-header">Pitching Highlights — Last 7 Days</div>', unsafe_allow_html=True)

    if not sc.empty:
        p_leaders = compute_pitching_leaders(sc)

        if not p_leaders.empty:
            min_pitches = 50
            qual_p = p_leaders[p_leaders["TotalPitches"] >= min_pitches].copy()

            if not qual_p.empty:
                whiff_col, k_col = st.columns(2)

                with whiff_col:
                    st.markdown("### 💨 Highest Whiff Rate")
                    top_whiff = qual_p.nlargest(5, "WhiffRate")
                    for _, row in top_whiff.iterrows():
                        img = _team_logo_img(row.get("Team", ""))
                        era_val = row.get("ERA", 0)
                        st.markdown(
                            f'<div class="player-row">'
                            f'{img}'
                            f'<div style="flex:1;">'
                            f'<div class="name">{row["Name"]}</div>'
                            f'<div class="detail">{int(row["TotalPitches"])} pitches &middot; {int(row["Strikeouts"])} K &middot; {era_val:.2f} ERA</div>'
                            f'</div>'
                            f'<div><span class="stat">{row["WhiffRate"]:.1f}%</span></div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        with st.expander("📊 Season ERA Trend"):
                            game_log = get_pitcher_game_log(int(row["pitcher"]), datetime.date.today().year)
                            if not game_log.empty:
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=game_log["date"], y=game_log["ERA"],
                                    mode="lines+markers",
                                    line=dict(color="#E63946", width=2),
                                    marker=dict(size=8, color="#E63946"),
                                    customdata=game_log[["IP", "SO", "ER", "opponent"]].values,
                                    hovertemplate=(
                                        "<b>%{x|%m/%d}</b><br>"
                                        "ERA: %{y:.2f}<br>"
                                        "IP: %{customdata[0]}<br>"
                                        "K: %{customdata[1]}<br>"
                                        "ER: %{customdata[2]}<br>"
                                        "vs %{customdata[3]}"
                                        "<extra></extra>"
                                    ),
                                ))
                                fig.update_layout(
                                    height=220,
                                    margin=dict(l=40, r=20, t=10, b=40),
                                    xaxis_title="Date",
                                    yaxis_title="Cumulative ERA",
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    font=dict(color="#8888AA"),
                                    xaxis=dict(gridcolor="#2A2A4A"),
                                    yaxis=dict(gridcolor="#2A2A4A"),
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.caption("No season game log available.")

                with k_col:
                    st.markdown("### ❌ Highest K/9")
                    top_k9 = qual_p.nlargest(5, "K9")
                    for _, row in top_k9.iterrows():
                        img = _team_logo_img(row.get("Team", ""))
                        era_val = row.get("ERA", 0)
                        st.markdown(
                            f'<div class="player-row">'
                            f'{img}'
                            f'<div style="flex:1;">'
                            f'<div class="name">{row["Name"]}</div>'
                            f'<div class="detail">{int(row["TotalPitches"])} pitches &middot; {row["WhiffRate"]:.1f}% whiff &middot; {era_val:.2f} ERA</div>'
                            f'</div>'
                            f'<div><span class="stat">{row["K9"]:.1f}</span></div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                        with st.expander("📊 Season ERA Trend"):
                            game_log = get_pitcher_game_log(int(row["pitcher"]), datetime.date.today().year)
                            if not game_log.empty:
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=game_log["date"], y=game_log["ERA"],
                                    mode="lines+markers",
                                    line=dict(color="#E63946", width=2),
                                    marker=dict(size=8, color="#E63946"),
                                    customdata=game_log[["IP", "SO", "ER", "opponent"]].values,
                                    hovertemplate=(
                                        "<b>%{x|%m/%d}</b><br>"
                                        "ERA: %{y:.2f}<br>"
                                        "IP: %{customdata[0]}<br>"
                                        "K: %{customdata[1]}<br>"
                                        "ER: %{customdata[2]}<br>"
                                        "vs %{customdata[3]}"
                                        "<extra></extra>"
                                    ),
                                ))
                                fig.update_layout(
                                    height=220,
                                    margin=dict(l=40, r=20, t=10, b=40),
                                    xaxis_title="Date",
                                    yaxis_title="Cumulative ERA",
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    font=dict(color="#8888AA"),
                                    xaxis=dict(gridcolor="#2A2A4A"),
                                    yaxis=dict(gridcolor="#2A2A4A"),
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.caption("No season game log available.")
