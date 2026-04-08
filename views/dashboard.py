"""Dashboard page — today's games, who's hot, who's cold, top matchups."""

import datetime
import streamlit as st
import pandas as pd
from data_loader import (
    get_todays_games,
    get_statcast_data,
    compute_batting_leaders,
    compute_pitching_leaders,
)


def _render_game_card(game: dict):
    """Render a single game as a styled card."""
    status_color = "#4CAF50" if "Progress" in game["status"] else "#8888AA"
    is_live = "Progress" in game["status"]

    live_dot = '🔴 ' if is_live else ''

    st.markdown(f"""
    <div class="game-card">
        <div class="status">{live_dot}{game['status']}</div>
        <div class="teams">
            <div>
                <div class="team-name">{game['away_team']}</div>
                <div class="record">{game['away_record']}</div>
                <div class="pitcher">SP: {game['away_pitcher']}</div>
            </div>
            <div class="score">{game['away_score']} - {game['home_score']}</div>
            <div style="text-align: right;">
                <div class="team-name">{game['home_team']}</div>
                <div class="record">{game['home_record']}</div>
                <div class="pitcher">SP: {game['home_pitcher']}</div>
            </div>
        </div>
        <div style="text-align:center; font-size:0.75rem; color:#8888AA; margin-top:4px;">
            {game['venue']}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render():
    st.markdown('<div class="section-header">Today\'s Games</div>', unsafe_allow_html=True)

    games = get_todays_games()

    if not games:
        st.info("No games scheduled today or data unavailable.")
    else:
        # Display games in a grid (3 per row)
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
            min_pa = 25  # minimum plate appearances for hot/cold
            qualified = leaders[leaders["PA"] >= min_pa].copy()

            if not qualified.empty:
                hot_col, cold_col = st.columns(2)

                with hot_col:
                    st.markdown("### 🔥 Hottest Hitters")
                    hot = qualified.nlargest(5, "OPS")
                    for _, row in hot.iterrows():
                        ops_val = row.get('OPS', 0)
                        st.markdown(f"""
                        <div class="player-row">
                            <div>
                                <div class="name">{row['Name']}</div>
                                <div class="detail">{int(row['PA'])} PA · {row['AVG']:.3f} AVG · {int(row['HR'])} HR · {row['AVG_EV']:.1f} mph EV</div>
                            </div>
                            <div>
                                <span class="stat">{ops_val:.3f} OPS</span>
                                <span class="hot-badge">HOT</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                with cold_col:
                    st.markdown("### 🥶 Coldest Hitters")
                    cold = qualified.nsmallest(5, "OPS")
                    for _, row in cold.iterrows():
                        ops_val = row.get('OPS', 0)
                        st.markdown(f"""
                        <div class="player-row">
                            <div>
                                <div class="name">{row['Name']}</div>
                                <div class="detail">{int(row['PA'])} PA · {row['AVG']:.3f} AVG · {int(row['SO'])} SO · {row['AVG_EV']:.1f} mph EV</div>
                            </div>
                            <div>
                                <span class="stat">{ops_val:.3f} OPS</span>
                                <span class="cold-badge">COLD</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
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
                        era_val = row.get('ERA', 0)
                        st.markdown(f"""
                        <div class="player-row">
                            <div>
                                <div class="name">{row['Name']}</div>
                                <div class="detail">{int(row['TotalPitches'])} pitches · {int(row['Strikeouts'])} K · {era_val:.2f} ERA</div>
                            </div>
                            <div>
                                <span class="stat">{row['WhiffRate']:.1f}%</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                with k_col:
                    st.markdown("### 🔥 Highest K/9")
                    top_k9 = qual_p.nlargest(5, "K9")
                    for _, row in top_k9.iterrows():
                        era_val = row.get('ERA', 0)
                        st.markdown(f"""
                        <div class="player-row">
                            <div>
                                <div class="name">{row['Name']}</div>
                                <div class="detail">{int(row['TotalPitches'])} pitches · {row['WhiffRate']:.1f}% whiff · {era_val:.2f} ERA</div>
                            </div>
                            <div>
                                <span class="stat">{row['K9']:.1f}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
