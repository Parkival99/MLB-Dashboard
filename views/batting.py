"""Batting Stats page — Statcast advanced + MLB API traditional with date range filtering."""

import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
from data_loader import get_mlb_batting_stats, get_statcast_data, compute_batting_leaders


def render():
    st.markdown('<div class="section-header">Batting Leaderboard</div>', unsafe_allow_html=True)

    # --- Date range controls ---
    col1, col2, col3 = st.columns([2, 2, 3])

    today = datetime.date.today()
    season_start = datetime.date(today.year, 3, 20)

    with col1:
        preset = st.selectbox(
            "Quick Range",
            ["Custom", "Today", "Last 3 Days", "Last 7 Days", "Last 14 Days", "Last 30 Days", "Full Season"],
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
        start_date = st.date_input("Start Date", value=start_date or season_start, max_value=today)
    with col3:
        end_date = st.date_input("End Date", value=end_date or today, max_value=today)

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    min_pa = st.slider("Minimum Plate Appearances", 0, 200, 10, step=5)

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

    source = st.radio(
        "Data Source",
        ["MLB (Traditional)", "Statcast (Advanced)"],
        horizontal=True,
    )

    if source == "MLB (Traditional)":
        st.caption("Full-season totals from the MLB Stats API.")

        with st.spinner("Pulling MLB season stats..."):
            df = get_mlb_batting_stats(today.year)

        if df.empty:
            st.warning("No MLB batting stats available.")
            return

        if min_pa > 0:
            df = df[df["PA"] >= min_pa]

        if df.empty:
            st.info(f"No batters with {min_pa}+ PA. Try lowering the minimum.")
            return

        display = ["Name", "Team", "G", "PA", "AB", "H", "2B", "3B", "HR", "RBI", "BB", "SO", "SB", "AVG", "OBP", "SLG", "OPS"]
        available = [c for c in display if c in df.columns]

        st.dataframe(
            df[available].style.format({
                "AVG": "{:.3f}",
                "OBP": "{:.3f}",
                "SLG": "{:.3f}",
                "OPS": "{:.3f}",
            }).background_gradient(subset=["OPS"], cmap="RdYlGn"),
            use_container_width=True,
            height=500,
        )

    else:
        # Statcast advanced stats with date range
        with st.spinner("Pulling Statcast data..."):
            sc = get_statcast_data(start_date.isoformat(), end_date.isoformat())

        if sc.empty:
            st.warning("No Statcast data available for this date range.")
            return

        leaders = compute_batting_leaders(sc)
        if leaders.empty:
            st.warning("No batting events found in this date range.")
            return

        leaders = leaders[leaders["PA"] >= min_pa]

        if leaders.empty:
            st.info(f"No batters with {min_pa}+ PA in this range. Try lowering the minimum.")
            return

        display_cols = ["Name", "PA", "H", "HR", "BB", "SO", "AVG", "OBP", "SLG", "OPS", "AVG_EV", "MAX_EV"]
        available = [c for c in display_cols if c in leaders.columns]

        st.dataframe(
            leaders[available].style.format({
                "AVG": "{:.3f}",
                "OBP": "{:.3f}",
                "SLG": "{:.3f}",
                "OPS": "{:.3f}",
                "AVG_EV": "{:.1f}",
                "MAX_EV": "{:.1f}",
            }).background_gradient(subset=["OPS"], cmap="RdYlGn"),
            use_container_width=True,
            height=500,
        )

        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("#### Exit Velocity vs. OPS")
            fig = px.scatter(
                leaders.head(50),
                x="AVG_EV",
                y="OPS",
                size="PA",
                hover_name="Name",
                color="HR",
                color_continuous_scale="Reds",
                template="plotly_dark",
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(26,26,46,0.8)",
                font_color="#EAEAEA",
                margin=dict(l=20, r=20, t=30, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

        with chart_col2:
            st.markdown("#### Home Run Leaders")
            top_hr = leaders.nlargest(15, "HR")
            fig2 = px.bar(
                top_hr,
                x="Name",
                y="HR",
                color="OPS",
                color_continuous_scale="RdYlGn",
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
