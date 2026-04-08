"""
Data loading and caching layer for MLB stats.
Uses pybaseball for Statcast/FanGraphs data and MLB Stats API for live info.
"""

import datetime
import requests
import pandas as pd
import streamlit as st
from pybaseball import (
    batting_stats,
    pitching_stats,
    statcast,
    cache,
)

# Enable pybaseball caching to avoid repeated scrapes
cache.enable()

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"


# ---------------------------------------------------------------------------
# Batting
# ---------------------------------------------------------------------------

@st.cache_data(ttl=900, show_spinner=False)  # 15-min cache
def get_batting_stats(start_date: str, end_date: str, qual: int = 0) -> pd.DataFrame:
    """
    Pull FanGraphs batting leaderboard for the given date range.
    qual=0 means no plate-appearance minimum (we filter in the UI).
    """
    try:
        start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        start_year = start_dt.year
        end_year = end_dt.year

        df = batting_stats(start_year, end_year, qual=qual)

        if df is None or df.empty:
            return pd.DataFrame()

        # Standardize column names
        df.columns = [c.strip() for c in df.columns]

        return df
    except Exception as e:
        st.warning(f"Could not load batting stats: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def get_statcast_batting(start_date: str, end_date: str) -> pd.DataFrame:
    """Pull Statcast pitch-level data for advanced batting metrics."""
    try:
        df = statcast(start_dt=start_date, end_dt=end_date)
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception as e:
        st.warning(f"Could not load Statcast data: {e}")
        return pd.DataFrame()


def compute_batting_leaders(sc_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate Statcast pitch-level data into per-batter stats."""
    if sc_df.empty:
        return pd.DataFrame()

    # Filter to at-bat events
    batted = sc_df.dropna(subset=["events"])

    if batted.empty:
        return pd.DataFrame()

    hits = ["single", "double", "triple", "home_run"]

    grouped = batted.groupby("batter").agg(
        Name=("player_name", "first"),
        PA=("events", "count"),
        H=("events", lambda x: x.isin(hits).sum()),
        HR=("events", lambda x: (x == "home_run").sum()),
        BB=("events", lambda x: (x == "walk").sum()),
        SO=("events", lambda x: (x == "strikeout").sum()),
        AVG_EV=("launch_speed", "mean"),
        MAX_EV=("launch_speed", "max"),
    ).reset_index()

    grouped["AVG"] = (grouped["H"] / grouped["PA"]).round(3)
    grouped["HR_PA"] = (grouped["HR"] / grouped["PA"]).round(3)

    return grouped.sort_values("PA", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Pitching
# ---------------------------------------------------------------------------

@st.cache_data(ttl=900, show_spinner=False)
def get_pitching_stats(start_date: str, end_date: str, qual: int = 0) -> pd.DataFrame:
    """Pull FanGraphs pitching leaderboard."""
    try:
        start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        start_year = start_dt.year
        end_year = end_dt.year

        df = pitching_stats(start_year, end_year, qual=qual)

        if df is None or df.empty:
            return pd.DataFrame()

        df.columns = [c.strip() for c in df.columns]

        return df
    except Exception as e:
        st.warning(f"Could not load pitching stats: {e}")
        return pd.DataFrame()


def compute_pitching_leaders(sc_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate Statcast data into per-pitcher metrics (K/9, whiff rate)."""
    if sc_df.empty:
        return pd.DataFrame()

    grouped = sc_df.groupby("pitcher").agg(
        Name=("player_name", "first"),
        TotalPitches=("pitch_type", "count"),
        SwStr=("description", lambda x: x.isin(["swinging_strike", "swinging_strike_blocked"]).sum()),
        Strikeouts=("events", lambda x: (x == "strikeout").sum()),
        IP_proxy=("events", lambda x: x.notna().sum()),  # rough proxy
    ).reset_index()

    grouped["WhiffRate"] = (grouped["SwStr"] / grouped["TotalPitches"] * 100).round(1)
    # K/9 approximation: (K / batters faced) * ~27
    grouped["K9"] = (grouped["Strikeouts"] / grouped["IP_proxy"] * 27).round(1)

    return grouped.sort_values("TotalPitches", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# MLB Stats API — live games, scores, matchups
# ---------------------------------------------------------------------------

@st.cache_data(ttl=120, show_spinner=False)  # 2-min cache for live data
def get_todays_games() -> list[dict]:
    """Fetch today's MLB schedule with scores."""
    today = datetime.date.today().isoformat()
    url = f"{MLB_API_BASE}/schedule?sportId=1&date={today}&hydrate=linescore,team,probablePitcher"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        games = []
        for date_entry in data.get("dates", []):
            for g in date_entry.get("games", []):
                game = {
                    "game_id": g["gamePk"],
                    "status": g["status"]["detailedState"],
                    "away_team": g["teams"]["away"]["team"]["name"],
                    "home_team": g["teams"]["home"]["team"]["name"],
                    "away_score": g["teams"]["away"].get("score", 0),
                    "home_score": g["teams"]["home"].get("score", 0),
                    "away_record": f'{g["teams"]["away"].get("leagueRecord", {}).get("wins", 0)}-{g["teams"]["away"].get("leagueRecord", {}).get("losses", 0)}',
                    "home_record": f'{g["teams"]["home"].get("leagueRecord", {}).get("wins", 0)}-{g["teams"]["home"].get("leagueRecord", {}).get("losses", 0)}',
                    "venue": g.get("venue", {}).get("name", ""),
                }
                # Probable pitchers
                away_pitcher = g["teams"]["away"].get("probablePitcher", {})
                home_pitcher = g["teams"]["home"].get("probablePitcher", {})
                game["away_pitcher"] = away_pitcher.get("fullName", "TBD")
                game["home_pitcher"] = home_pitcher.get("fullName", "TBD")
                games.append(game)
        return games
    except Exception as e:
        st.warning(f"Could not load today's games: {e}")
        return []


@st.cache_data(ttl=300, show_spinner=False)
def get_standings() -> pd.DataFrame:
    """Fetch current MLB standings."""
    url = f"{MLB_API_BASE}/standings?leagueId=103,104&season={datetime.date.today().year}&standingsTypes=regularSeason"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rows = []
        for record in data.get("records", []):
            division = record.get("division", {}).get("name", "")
            for team in record.get("teamRecords", []):
                rows.append({
                    "Team": team["team"]["name"],
                    "Division": division,
                    "W": team["wins"],
                    "L": team["losses"],
                    "PCT": float(team["winningPercentage"]),
                    "GB": team.get("gamesBack", "-"),
                    "Streak": team.get("streak", {}).get("streakCode", ""),
                    "L10": f'{team.get("records", {}).get("splitRecords", [{}])[0].get("wins", "")}-{team.get("records", {}).get("splitRecords", [{}])[0].get("losses", "")}',
                })
        return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"Could not load standings: {e}")
        return pd.DataFrame()
