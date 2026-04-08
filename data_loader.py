"""
Data loading and caching layer for MLB stats.
Uses pybaseball for Statcast data and MLB Stats API for everything else.
FanGraphs scraping is unreliable (403s), so traditional stats come from MLB API.
"""

import datetime
import requests
import pandas as pd
import streamlit as st
from pybaseball import statcast, cache

# Enable pybaseball caching to avoid repeated scrapes
cache.enable()

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"


# ---------------------------------------------------------------------------
# Player name lookup (Statcast only has pitcher names, not batter names)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400, show_spinner=False)  # cache for 24 hours
def lookup_player_names(player_ids: list[int]) -> dict[int, str]:
    """Batch lookup player names from MLB Stats API."""
    if not player_ids:
        return {}

    names = {}
    # API accepts up to ~100 IDs at a time
    batch_size = 100
    for i in range(0, len(player_ids), batch_size):
        batch = player_ids[i:i + batch_size]
        ids_str = ",".join(str(pid) for pid in batch)
        url = f"{MLB_API_BASE}/people?personIds={ids_str}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            for person in resp.json().get("people", []):
                names[person["id"]] = person["fullName"]
        except Exception:
            pass
    return names


# ---------------------------------------------------------------------------
# Statcast data
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def get_statcast_data(start_date: str, end_date: str) -> pd.DataFrame:
    """Pull Statcast pitch-level data (regular season only)."""
    try:
        df = statcast(start_dt=start_date, end_dt=end_date)
        if df is None or df.empty:
            return pd.DataFrame()
        # Filter to regular season games only — excludes spring training (S),
        # postseason (F/D/L/W), and all-star (A) data that inflates stats.
        if "game_type" in df.columns:
            df = df[df["game_type"] == "R"]
        return df
    except Exception as e:
        st.warning(f"Could not load Statcast data: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Batting — from Statcast
# ---------------------------------------------------------------------------

def compute_batting_leaders(sc_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate Statcast pitch-level data into per-batter stats.
    Filters out pitchers, deduplicates plate appearances, and resolves
    correct batter names via MLB API.
    """
    if sc_df.empty:
        return pd.DataFrame()

    # Filter to at-bat events (rows where a PA concluded)
    batted = sc_df.dropna(subset=["events"])

    if batted.empty:
        return pd.DataFrame()

    # CRITICAL: Deduplicate plate appearances.
    # Statcast can have duplicate rows or multiple pitches with the events
    # field set. Keep only one row per PA (game + at_bat_number + batter).
    dedup_cols = ["game_pk", "at_bat_number", "batter"]
    available_dedup = [c for c in dedup_cols if c in batted.columns]
    if len(available_dedup) == len(dedup_cols):
        batted = batted.drop_duplicates(subset=dedup_cols, keep="last")

    # Identify pitchers: players whose ID appears more as 'pitcher' than 'batter'
    pitcher_counts = sc_df["pitcher"].value_counts()
    batter_counts = sc_df["batter"].value_counts()
    pitcher_ids = set()
    for pid in pitcher_counts.index:
        if pitcher_counts.get(pid, 0) > batter_counts.get(pid, 0):
            pitcher_ids.add(pid)
    batted = batted[~batted["batter"].isin(pitcher_ids)]

    if batted.empty:
        return pd.DataFrame()

    hits = ["single", "double", "triple", "home_run"]

    grouped = batted.groupby("batter").agg(
        PA=("events", "count"),
        H=("events", lambda x: x.isin(hits).sum()),
        _2B=("events", lambda x: (x == "double").sum()),
        _3B=("events", lambda x: (x == "triple").sum()),
        HR=("events", lambda x: (x == "home_run").sum()),
        BB=("events", lambda x: (x == "walk").sum()),
        SO=("events", lambda x: (x == "strikeout").sum()),
        HBP=("events", lambda x: (x == "hit_by_pitch").sum()),
        SF=("events", lambda x: (x == "sac_fly").sum()),
    ).reset_index()

    # Calculate exit velocity from batted ball events only (bb_type not null)
    bbe = sc_df.dropna(subset=["launch_speed", "bb_type"])
    if not bbe.empty:
        ev_stats = bbe.groupby("batter")["launch_speed"].agg(
            AVG_EV="mean", MAX_EV="max"
        ).reset_index()
        grouped = grouped.merge(ev_stats, on="batter", how="left")
    else:
        grouped["AVG_EV"] = None
        grouped["MAX_EV"] = None

    # Lookup real batter names from MLB API
    batter_ids = grouped["batter"].tolist()
    name_map = lookup_player_names(batter_ids)
    grouped["Name"] = grouped["batter"].map(name_map).fillna("Unknown")

    # Derive team: Top inning = away team batting, Bot = home team
    if "inning_topbot" in batted.columns and "home_team" in batted.columns:
        def _get_team(sub):
            row = sub.iloc[0]
            if row.get("inning_topbot") == "Top":
                return row.get("away_team", "")
            return row.get("home_team", "")
        team_map = batted.groupby("batter").apply(_get_team, include_groups=False)
        grouped["Team"] = grouped["batter"].map(team_map).fillna("")
    else:
        grouped["Team"] = ""

    # Compute AB (PA minus BB, HBP, SF)
    grouped["AB"] = grouped["PA"] - grouped["BB"] - grouped["HBP"] - grouped["SF"]
    grouped["AB"] = grouped["AB"].clip(lower=1)

    grouped["AVG"] = (grouped["H"] / grouped["AB"]).round(3)
    grouped["HR_PA"] = (grouped["HR"] / grouped["PA"]).round(3)
    grouped["OBP"] = ((grouped["H"] + grouped["BB"] + grouped["HBP"]) / grouped["PA"]).round(3)

    # SLG = TB / AB
    grouped["TB"] = (
        (grouped["H"] - grouped["_2B"] - grouped["_3B"] - grouped["HR"])  # singles
        + grouped["_2B"] * 2 + grouped["_3B"] * 3 + grouped["HR"] * 4
    )
    grouped["SLG"] = (grouped["TB"] / grouped["AB"]).round(3)
    grouped["OPS"] = (grouped["OBP"] + grouped["SLG"]).round(3)

    return grouped.sort_values("PA", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Pitching — from Statcast
# ---------------------------------------------------------------------------

def compute_pitching_leaders(sc_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate Statcast data into per-pitcher metrics."""
    if sc_df.empty:
        return pd.DataFrame()

    hits = ["single", "double", "triple", "home_run"]

    # For event-level stats (BF, H, K, etc.), deduplicate plate appearances
    # but keep all pitches for pitch-level stats (SwStr, TotalPitches)
    events_df = sc_df.dropna(subset=["events"])
    dedup_cols = ["game_pk", "at_bat_number", "batter"]
    available_dedup = [c for c in dedup_cols if c in events_df.columns]
    if len(available_dedup) == len(dedup_cols):
        events_df = events_df.drop_duplicates(subset=dedup_cols, keep="last")

    # Pitch-level aggregates (all pitches, no dedup)
    pitch_agg = sc_df.groupby("pitcher").agg(
        Name=("player_name", "first"),
        TotalPitches=("pitch_type", "count"),
        SwStr=("description", lambda x: x.isin([
            "swinging_strike", "swinging_strike_blocked"
        ]).sum()),
    ).reset_index()

    # Event-level aggregates (deduplicated PAs)
    event_agg = events_df.groupby("pitcher").agg(
        Strikeouts=("events", lambda x: (x == "strikeout").sum()),
        BF=("events", "count"),
        H=("events", lambda x: x.isin(hits).sum()),
        HR=("events", lambda x: (x == "home_run").sum()),
        BB=("events", lambda x: (x == "walk").sum()),
        HBP=("events", lambda x: (x == "hit_by_pitch").sum()),
    ).reset_index()

    grouped = pitch_agg.merge(event_agg, on="pitcher", how="left").fillna(0)

    # Derive pitcher's team: Top inning = home team pitching, Bot = away team
    if "inning_topbot" in sc_df.columns and "home_team" in sc_df.columns:
        def _get_pitcher_team(sub):
            row = sub.iloc[0]
            if row.get("inning_topbot") == "Top":
                return row.get("home_team", "")
            return row.get("away_team", "")
        p_team_map = sc_df.groupby("pitcher").apply(_get_pitcher_team, include_groups=False)
        grouped["Team"] = grouped["pitcher"].map(p_team_map).fillna("")
    else:
        grouped["Team"] = ""

    grouped["WhiffRate"] = (grouped["SwStr"] / grouped["TotalPitches"] * 100).round(1)

    # Estimate IP: ~3 batters faced per inning
    grouped["IP_est"] = (grouped["BF"] / 3).round(1).clip(lower=0.1)

    # K/9
    grouped["K9"] = (grouped["Strikeouts"] / grouped["IP_est"] * 9).round(1)

    # ERA estimate: use runs created approach
    # Approximate earned runs = 0.5*H + 0.33*BB + 0.33*HBP + 1.4*HR (rough linear weight)
    grouped["ER_est"] = (
        0.5 * grouped["H"] + 0.33 * grouped["BB"]
        + 0.33 * grouped["HBP"] + 1.4 * grouped["HR"]
    )
    grouped["ERA"] = (grouped["ER_est"] / grouped["IP_est"] * 9).round(2)

    # WHIP
    grouped["WHIP"] = ((grouped["H"] + grouped["BB"]) / grouped["IP_est"]).round(2)

    return grouped.sort_values("TotalPitches", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# MLB Stats API — traditional season stats (replaces FanGraphs)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=900, show_spinner=False)
def get_mlb_batting_stats(season: int) -> pd.DataFrame:
    """Fetch season batting stats from MLB Stats API."""
    url = (
        f"{MLB_API_BASE}/stats"
        f"?stats=season&group=hitting&season={season}&sportId=1"
        f"&limit=500&offset=0"
        f"&sortStat=plateAppearances&order=desc"
        f"&hydrate=team"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        rows = []
        for split in data.get("stats", []):
            for entry in split.get("splits", []):
                s = entry.get("stat", {})
                player = entry.get("player", {})
                team = entry.get("team", {})
                rows.append({
                    "Name": player.get("fullName", ""),
                    "Team": team.get("abbreviation", ""),
                    "G": s.get("gamesPlayed", 0),
                    "PA": s.get("plateAppearances", 0),
                    "AB": s.get("atBats", 0),
                    "H": s.get("hits", 0),
                    "2B": s.get("doubles", 0),
                    "3B": s.get("triples", 0),
                    "HR": s.get("homeRuns", 0),
                    "RBI": s.get("rbi", 0),
                    "BB": s.get("baseOnBalls", 0),
                    "SO": s.get("strikeOuts", 0),
                    "SB": s.get("stolenBases", 0),
                    "AVG": float(s.get("avg", "0") or "0"),
                    "OBP": float(s.get("obp", "0") or "0"),
                    "SLG": float(s.get("slg", "0") or "0"),
                    "OPS": float(s.get("ops", "0") or "0"),
                })
        return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"Could not load MLB batting stats: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def get_mlb_pitching_stats(season: int) -> pd.DataFrame:
    """Fetch season pitching stats from MLB Stats API."""
    url = (
        f"{MLB_API_BASE}/stats"
        f"?stats=season&group=pitching&season={season}&sportId=1"
        f"&limit=500&offset=0"
        f"&sortStat=inningsPitched&order=desc"
        f"&hydrate=team"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        rows = []
        for split in data.get("stats", []):
            for entry in split.get("splits", []):
                s = entry.get("stat", {})
                player = entry.get("player", {})
                team = entry.get("team", {})

                ip_str = s.get("inningsPitched", "0")
                ip = float(ip_str) if ip_str else 0.0

                rows.append({
                    "Name": player.get("fullName", ""),
                    "Team": team.get("abbreviation", ""),
                    "W": s.get("wins", 0),
                    "L": s.get("losses", 0),
                    "ERA": float(s.get("era", "0") or "0"),
                    "G": s.get("gamesPlayed", 0),
                    "GS": s.get("gamesStarted", 0),
                    "IP": ip,
                    "SO": s.get("strikeOuts", 0),
                    "BB": s.get("baseOnBalls", 0),
                    "H": s.get("hits", 0),
                    "HR": s.get("homeRuns", 0),
                    "WHIP": float(s.get("whip", "0") or "0"),
                    "K9": float(s.get("strikeoutsPer9Inn", "0") or "0"),
                    "BB9": float(s.get("walksPer9Inn", "0") or "0"),
                    "HR9": float(s.get("homeRunsPer9", "0") or "0"),
                    "AVG": float(s.get("avg", "0") or "0"),
                })
        return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"Could not load MLB pitching stats: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# MLB Stats API — live games, scores, matchups
# ---------------------------------------------------------------------------

@st.cache_data(ttl=120, show_spinner=False)
def get_todays_games() -> tuple[str, list[dict]]:
    """Fetch MLB schedule with scores.
    Before 7 AM local time, show yesterday's games so late-night final
    scores stay visible. Returns (label, games).
    """
    now = datetime.datetime.now()
    if now.hour < 7:
        target = (now - datetime.timedelta(days=1)).date()
        label = "Yesterday's Games"
    else:
        target = now.date()
        label = "Today's Games"

    date_str = target.isoformat()
    url = f"{MLB_API_BASE}/schedule?sportId=1&date={date_str}&hydrate=linescore,team,probablePitcher"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        games = []
        for date_entry in data.get("dates", []):
            for g in date_entry.get("games", []):
                # Parse game time — API gives UTC, convert to EST
                game_time_str = ""
                game_date_utc = g.get("gameDate", "")
                status_detail = g["status"]["detailedState"]
                if game_date_utc:
                    try:
                        utc_dt = datetime.datetime.fromisoformat(
                            game_date_utc.replace("Z", "+00:00")
                        )
                        est_dt = utc_dt - datetime.timedelta(hours=4)
                        game_time_str = est_dt.strftime("%I:%M %p ET").lstrip("0")
                    except Exception:
                        game_time_str = ""

                game = {
                    "game_id": g["gamePk"],
                    "status": status_detail,
                    "game_time": game_time_str,
                    "away_team": g["teams"]["away"]["team"]["name"],
                    "home_team": g["teams"]["home"]["team"]["name"],
                    "away_score": g["teams"]["away"].get("score", 0),
                    "home_score": g["teams"]["home"].get("score", 0),
                    "away_record": f'{g["teams"]["away"].get("leagueRecord", {}).get("wins", 0)}-{g["teams"]["away"].get("leagueRecord", {}).get("losses", 0)}',
                    "home_record": f'{g["teams"]["home"].get("leagueRecord", {}).get("wins", 0)}-{g["teams"]["home"].get("leagueRecord", {}).get("losses", 0)}',
                    "venue": g.get("venue", {}).get("name", ""),
                }
                away_pitcher = g["teams"]["away"].get("probablePitcher", {})
                home_pitcher = g["teams"]["home"].get("probablePitcher", {})
                game["away_pitcher"] = away_pitcher.get("fullName", "TBD")
                game["home_pitcher"] = home_pitcher.get("fullName", "TBD")
                games.append(game)
        return label, games
    except Exception as e:
        st.warning(f"Could not load games: {e}")
        return label, []


@st.cache_data(ttl=300, show_spinner=False)
def get_standings() -> pd.DataFrame:
    """Fetch current MLB standings."""
    year = datetime.date.today().year
    url = (
        f"{MLB_API_BASE}/standings"
        f"?leagueId=103,104&season={year}"
        f"&standingsTypes=regularSeason"
        f"&hydrate=division,league"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rows = []
        for record in data.get("records", []):
            league_name = record.get("league", {}).get("name", "")
            div_name = record.get("division", {}).get("name", "")
            if league_name and league_name not in div_name:
                division = f"{league_name} {div_name}"
            else:
                division = div_name if div_name else league_name

            for team in record.get("teamRecords", []):
                rows.append({
                    "Team": team["team"]["name"],
                    "Division": division,
                    "W": team["wins"],
                    "L": team["losses"],
                    "PCT": float(team["winningPercentage"]),
                    "GB": team.get("gamesBack", "-"),
                    "Streak": team.get("streak", {}).get("streakCode", ""),
                })
        return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"Could not load standings: {e}")
        return pd.DataFrame()
