"""Pitching Stats page — K/9, whiff rate, ERA with date range filtering."""

import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
from data_loader import get_mlb_pitching_stats, get_statcast_data, compute_pitching_leaders


def render():
    st.markdown('<div class="section-header">Pitching Leaderboard</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 2, 3])

    today = datetime.date.today()
    season_start = datetime.date(today.year, 3, 20)

    with col1:
        preset = st.selectbox(
            "Quick Range",
            ["Custom", "Today", "Last 3 Days", "Last 7 Days", "Last 14 Days", "Last 30 Days", "Full Season"],
            key="pitch_preset",
        )

    if preset == "Today":
        start_date = today
        end_date = today
    elif preset == "Last 3 Days":
        start_date = today - datetime.timedelta(days=3)
        end_date = today
    elif preset == "Last 7 Days":
        start_date = today - datetime.timedelta(days=7)
        end_date = today
    elif preset == "Last 14 Days":
        start_date = today - datetime.timedelta(days=14)
        end_date = today
    elif preset == "Last 30 Days":
        start_date = today - datetime.timedelta(days=30)
        end_date = today
    elif preset == "Full Season":
        start_date = season_start
        end_date = today
    else:
        start_date = None
        end_date = None

    with col2:
        start_date = st.date_input("Start Date", value=start_date or season_start, max_value=today, key="pitch_start")
    with col3:
        end_date = st.date_input("End Date", value=end_date or today, max_value=today, key="pitch_end")

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

    source = st.radio(
        "Data Source",
        ["MLB (Traditional)", "Statcast (K/9 & Whiff Rate)"],
        horizontal=True,
        key="pitch_source",
    )

    if source == "MLB (Traditional)":
        st.caption("Full-season totals from the MLB Stats API.")
        min_ip = st.slider("Minimum IP", 0, 100, 5, step=5, key="pitch_min_ip")

        with st.spinner("Pulling MLB season pitching stats..."):
            df = get_mlb_pitching_stats(today.year)

        if df.empty:
            st.warning("No MLB pitching stats available.")
            return

        if min_ip > 0:
            df = df[df["IP"] >= min_ip]

        if df.empty:
            st.info(f"No pitchers with {min_ip}+ IP. Try lowering the minimum.")
            return

        display = ["Name", "Team", "W", "L", "ERA", "G", "GS", "IP", "SO", "BB", "H", "HR", "WHIP", "K9", "BB9", "HR9", "AVG"]
        available = [c for c in display if c in df.columns]

        st.dataframe(
            df[available].style.format({
                "ERA": "{:.2f}",
                "WHIP": "{:.2f}",
                "K9": "{:.2f}",
                "BB9": "{:.2f}",
                "HR9": "{:.2f}",
                "AVG": "{:.3f}",
                "IP": "{:.1f}",
            }).background_gradient(subset=["ERA"], cmap="RdYlGn_r"),
            use_container_width=True,
            height=500,
        )

    else:
        # Statcast advanced pitching with date range
        min_pitches = st.slider("Minimum Pitches Thrown", 0, 500, 50, step=25, key="pitch_min")

        with st.spinner("Pulling Statcast pitching data..."):
            sc = get_statcast_data(start_date.isoformat(), end_date.isoformat())

        if sc.empty:
            st.warning("No Statcast data available for this date range.")
            return

        leaders = compute_pitching_leaders(sc)
        if leaders.empty:
            st.warning("No pitching data found for this range.")
            return

        leaders = leaders[leaders["TotalPitches"] >= min_pitches]

        if leaders.empty:
            st.info(f"No pitchers with {min_pitches}+ pitches. Try lowering the minimum.")
            return

        display_cols = ["Name", "TotalPitches", "BF", "IP_est", "ERA", "WHIP", "SwStr", "WhiffRate", "Strikeouts", "K9", "H", "BB", "HR"]
        available = [c for c in display_cols if c in leaders.columns]

        st.dataframe(
            leaders[available].style.format({
                "WhiffRate": "{:.1f}",
                "K9": "{:.1f}",
                "ERA": "{:.2f}",
                "WHIP": "{:.2f}",
                "IP_est": "{:.1f}",
            }).background_gradient(subset=["ERA"], cmap="RdYlGn_r"),
            use_container_width=True,
            height=500,
        )

        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("#### Whiff Rate vs. K/9")
            fig = px.scatter(
                leaders.head(50),
                x="WhiffRate",
                y="K9",
                size="TotalPitches",
                hover_name="Name",
                color="ERA",
                color_continuous_scale="RdYlGn_r",
                template="plotly_dark",
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(26,26,46,0.8)",
                font_color="#EAEAEA",
                margin=dict(l=20, r=20, t=30, b=20),
                xaxis_title="Whiff Rate (%)",
                yaxis_title="K/9",
            )
            st.plotly_chart(fig, use_container_width=True)

        with chart_col2:
            st.markdown("#### Top Strikeout Artists")
            top_k = leaders.nlargest(15, "Strikeouts")
            fig2 = px.bar(
                top_k,
                x="Name",
                y="Strikeouts",
                color="ERA",
                color_continuous_scale="RdYlGn_r",
                template="plotly_dark",
            )
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(26,26,46,0.8)",
                font_color="#EAEAEA",
                margin=dict(l=20, r=20, t=30, b=20),
                xaxis_tickangle=-45,
            )
            st.plotly_chart(fig2, use_container_width=True)
