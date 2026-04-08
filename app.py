"""
MLB Stats Dashboard — Main Entry Point
Run with: streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="MLB Stats Hub",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS for sleek dark UI
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* ---- Global ---- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Hide default Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* ---- Sidebar ---- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F0F23 0%, #1A1A2E 100%);
        border-right: 1px solid #2A2A4A;
    }

    section[data-testid="stSidebar"] .stRadio label {
        color: #EAEAEA;
        font-weight: 500;
        padding: 8px 12px;
        border-radius: 8px;
        transition: all 0.2s ease;
    }

    section[data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(230, 57, 70, 0.15);
    }

    /* ---- Cards / Metric containers ---- */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%);
        border: 1px solid #2A2A4A;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }

    div[data-testid="stMetric"] label {
        color: #8888AA;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #FFFFFF;
        font-weight: 700;
    }

    /* ---- Dataframes ---- */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #2A2A4A;
    }

    /* ---- Buttons ---- */
    .stButton > button {
        border-radius: 8px;
        border: 1px solid #E63946;
        color: #E63946;
        background: transparent;
        font-weight: 600;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        background: #E63946;
        color: white;
    }

    /* ---- Tab styling ---- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 500;
    }

    /* ---- Section headers ---- */
    .section-header {
        font-size: 1.4rem;
        font-weight: 700;
        color: #EAEAEA;
        margin-bottom: 0.5rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #E63946;
        display: inline-block;
    }

    /* ---- Game cards ---- */
    .game-card {
        background: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%);
        border: 1px solid #2A2A4A;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .game-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.4);
    }

    .game-card .teams {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }

    .game-card .team-name {
        font-weight: 600;
        font-size: 1.1rem;
        color: #EAEAEA;
    }

    .game-card .score {
        font-size: 1.8rem;
        font-weight: 700;
        color: #E63946;
        text-align: center;
    }

    .game-card .record {
        font-size: 0.8rem;
        color: #8888AA;
    }

    .game-card .status {
        text-align: center;
        font-size: 0.75rem;
        color: #8888AA;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .game-card .pitcher {
        font-size: 0.85rem;
        color: #AAAACC;
    }

    /* ---- Hot / Cold badges ---- */
    .hot-badge {
        background: linear-gradient(135deg, #E63946 0%, #FF6B6B 100%);
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }

    .cold-badge {
        background: linear-gradient(135deg, #1E90FF 0%, #63B3ED 100%);
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }

    /* ---- Player row ---- */
    .player-row {
        background: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%);
        border: 1px solid #2A2A4A;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .player-row .name {
        font-weight: 600;
        color: #EAEAEA;
        font-size: 1rem;
    }

    .player-row .stat {
        color: #E63946;
        font-weight: 700;
        font-size: 1.1rem;
    }

    .player-row .detail {
        color: #8888AA;
        font-size: 0.8rem;
    }

    /* ---- Divider ---- */
    .custom-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, #2A2A4A, transparent);
        margin: 1.5rem 0;
    }

    /* Auto-refresh indicator */
    .refresh-badge {
        background: rgba(230, 57, 70, 0.15);
        color: #E63946;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("# ⚾ MLB Stats Hub")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

    page = st.radio(
        "Navigate",
        ["Dashboard", "Batting Stats", "Pitching Stats", "Standings"],
        label_visibility="collapsed",
    )

    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        '<span class="refresh-badge">Auto-refreshes every few minutes</span>',
        unsafe_allow_html=True,
    )
    if st.button("🔄 Refresh Now"):
        st.cache_data.clear()
        st.rerun()

# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------
if page == "Dashboard":
    from views import dashboard
    dashboard.render()
elif page == "Batting Stats":
    from views import batting
    batting.render()
elif page == "Pitching Stats":
    from views import pitching
    pitching.render()
elif page == "Standings":
    from views import standings
    standings.render()
