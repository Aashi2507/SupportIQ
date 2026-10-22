import html
import logging
from collections import Counter

import altair as alt
import pandas as pd
import streamlit as st

from auth import (
    authenticate_user,
    register_customer,
    request_otp,
    verify_otp,
    get_verified_user,
    reset_password_with_otp,
    email_exists,
)
from db import (
    save_ticket,
    get_customer_ticket_counts,
    get_agent_ticket_counts,
    get_customer_tickets,
    get_agent_tickets,
    get_customer_ticket_by_id,
    get_agent_ticket_by_id,
    update_ticket_status,
)

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("supportiq")

st.set_page_config(
    page_title="SupportIQ",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------
# Session state and navigation
# ---------------------------------------------------------------------

DEFAULTS = {
    "user": None,
    "page": "Dashboard",
    "selected_ticket_id": None,
    "agent_analysis_cache": {},
    "selected_role": None,
    "auth_view": "role_select",
    "auth_notice": None,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def go_to(page):
    st.session_state.page = page


def open_ticket(ticket_id):
    st.session_state.selected_ticket_id = ticket_id
    st.session_state.page = "Ticket Details"


def logout():
    st.session_state.user = None
    st.session_state.page = "Dashboard"
    st.session_state.selected_ticket_id = None
    st.session_state.agent_analysis_cache = {}
    st.session_state.selected_role = None
    st.session_state.auth_view = "role_select"


# ---------------------------------------------------------------------
# Application styling — one valid style block, no duplicate overrides
# ---------------------------------------------------------------------

st.markdown(
    """
    <style>
    :root {
        --sq-navy: #14264D;
        --sq-navy-light: #203B70;
        --sq-blue: #3478D4;
        --sq-blue-hover: #2864B6;
        --sq-purple: #6855C7;
        --sq-purple-hover: #5543AE;
        --sq-bg: #F3F6FB;
        --sq-card: #FFFFFF;
        --sq-text: #1F2A3D;
        --sq-muted: #65738A;
        --sq-border: #DFE6F0;
        --sq-success: #16835D;
        --sq-warning: #A8640B;
        --sq-danger: #B33D52;
        --sq-shadow: 0 8px 24px rgba(20, 38, 77, 0.06);
    }

    html, body, .stApp {
        font-family: Inter, "Segoe UI", ui-sans-serif, system-ui, -apple-system,
                     BlinkMacSystemFont, sans-serif;
    }
    header[data-testid="stHeader"], .stAppHeader {
        background: transparent !important;
    }
    .stApp {
        background: radial-gradient(ellipse at 12% 4%, rgba(217, 224, 255, .55), transparent 34%),
                    radial-gradient(ellipse at 92% 18%, rgba(229, 221, 255, .42), transparent 30%),
                    var(--sq-bg);
        color: var(--sq-text);
    }
    .block-container {
        max-width: 1280px;
        padding: 1.1rem clamp(1rem, 3vw, 2.5rem) 2rem;
    }
    /* Authentication views use a full-bleed split layout. Keep this scoped to
       pages that render the branding panel so the rest of the app is unchanged. */
    .block-container:has(.st-key-auth_brand_panel) {
        box-sizing: border-box;
        width: 100%;
        max-width: none;
        min-height: 100vh;
        margin: 0;
        padding: 0;
    }
    .block-container:has(.st-key-auth_brand_panel)
    [data-testid="stHorizontalBlock"]:has(.st-key-auth_brand_panel) {
        display: flex;
        flex-wrap: nowrap;
        width: 100%;
        min-height: 100vh;
        margin: 0;
        column-gap: 0 !important;
        align-items: stretch;
    }
    .block-container:has(.st-key-auth_brand_panel)
    [data-testid="stHorizontalBlock"]:has(.st-key-auth_brand_panel) > [data-testid="column"]:first-child {
        box-sizing: border-box;
        flex: 0 0 52.5% !important;
        width: 52.5% !important;
        max-width: 52.5% !important;
        min-width: 0;
    }
    .block-container:has(.st-key-auth_brand_panel)
    [data-testid="stHorizontalBlock"]:has(.st-key-auth_brand_panel) > [data-testid="column"]:last-child {
        box-sizing: border-box;
        flex: 1 1 47.5% !important;
        width: 47.5% !important;
        max-width: 47.5% !important;
        min-width: 0;
        position: relative;
        z-index: 2;
    }
    .stApp p, .stApp li, .stApp label,
    .stApp [data-testid="stMarkdownContainer"],
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stWidgetLabel"],
    .stApp [data-testid="stWidgetLabel"] *,
    .stApp [data-testid="stRadio"] label,
    .stApp [data-testid="stRadio"] label *,
    .stApp [data-testid="stSelectbox"] label,
    .stApp [data-testid="stTextInput"] label,
    .stApp [data-testid="stTextArea"] label { color: var(--sq-text) !important; }

    h1, h2, h3, h4 {
        color: var(--sq-navy) !important;
        letter-spacing: -0.025em;
        line-height: 1.2;
    }
    h1 { font-weight: 760 !important; }
    h2, h3 { font-weight: 700 !important; }
    h4 { font-weight: 650 !important; }
    [data-testid="stCaptionContainer"] { color: var(--sq-muted) !important; }
    hr { border-color: var(--sq-border) !important; }

    /* Role-specific navigation keeps one shared shell for both user types. */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div {
        background: linear-gradient(180deg, var(--sq-navy) 0%, #192F5B 100%) !important;
    }
    section[data-testid="stSidebar"] { border-right: 1px solid #203761; }
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: #F5F7FF !important;
    }
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: #C4D0E6 !important;
    }
    section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.16) !important; }
    section[data-testid="stSidebar"] div.stButton > button {
        width: 100%; min-height: 44px; text-align: left;
        border: 1px solid rgba(255,255,255,.10); border-radius: 10px;
        background: rgba(255,255,255,.055); color: #F7F8FC !important;
        font-weight: 600; padding: .6rem .85rem;
        transition: background .16s ease, border-color .16s ease, transform .16s ease;
    }
    section[data-testid="stSidebar"] div.stButton > button:hover {
        background: rgba(104,85,199,.48); border-color: rgba(196,185,255,.5);
        color: #FFFFFF !important; transform: translateX(2px);
    }
    section[data-testid="stSidebar"] div.stButton > button[kind="primary"] {
        background: linear-gradient(110deg, var(--sq-blue), var(--sq-purple));
        border-color: transparent; color: #FFFFFF !important;
        box-shadow: 0 5px 14px rgba(4,12,32,.20);
    }

    .sq-hero {
        position: relative; overflow: hidden;
        background: linear-gradient(118deg, #14264D 0%, #23467D 58%, #6252B9 100%);
        padding: clamp(1.5rem, 3vw, 2.25rem); border-radius: 20px;
        margin: 0 0 1.65rem; box-shadow: 0 14px 32px rgba(20,38,77,.16);
    }
    .sq-hero h1 {
        color: #FFFFFF !important; font-size: clamp(2rem, 4vw, 2.8rem);
        margin: 0 0 .4rem; line-height: 1.12;
    }
    .sq-hero p { color: #E8EDFA !important; margin: .25rem 0; font-size: 1rem; }
    .sq-eyebrow {
        color: #D4CCFF !important; font-size: .74rem !important; font-weight: 750;
        letter-spacing: .13em; text-transform: uppercase; margin-bottom: .55rem !important;
    }

    div[data-testid="stForm"] {
        background: var(--sq-card); border: 1px solid var(--sq-border);
        border-radius: 16px; padding: 1.35rem 1.4rem 1rem;
        box-shadow: var(--sq-shadow);
    }
    .stTextInput input, .stTextArea textarea, .stNumberInput input {
        color: var(--sq-text) !important; -webkit-text-fill-color: var(--sq-text) !important;
        background: #FFFFFF !important; border: 1px solid #C9D3E2 !important;
        border-radius: 10px !important; caret-color: var(--sq-blue);
    }
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: #7B8799 !important; -webkit-text-fill-color: #7B8799 !important; opacity: 1;
    }
    .stTextInput input:focus, .stTextArea textarea:focus,
    .stNumberInput input:focus {
        border-color: var(--sq-blue) !important;
        box-shadow: 0 0 0 3px rgba(52,120,212,.14) !important;
    }
    div[data-baseweb="select"] > div {
        background: #FFFFFF !important; border-color: #C9D3E2 !important;
        border-radius: 10px !important;
    }
    div[data-baseweb="select"] * { color: var(--sq-text) !important; }

    .stApp div.stButton > button,
    .stApp div.stFormSubmitButton > button,
    .stApp [data-testid="stDownloadButton"] button {
        min-height: 42px; border-radius: 10px; font-weight: 650;
        border: 1px solid var(--sq-purple); background: var(--sq-purple);
        color: #FFFFFF !important; box-shadow: 0 3px 8px rgba(70,55,150,.10);
        transition: background .16s ease, border-color .16s ease, transform .16s ease;
    }
    .stApp div.stButton > button *, .stApp div.stFormSubmitButton > button *,
    .stApp [data-testid="stDownloadButton"] button * { color: #FFFFFF !important; }
    .stApp div.stButton > button:hover, .stApp div.stFormSubmitButton > button:hover,
    .stApp [data-testid="stDownloadButton"] button:hover {
        background: var(--sq-purple-hover); border-color: var(--sq-purple-hover);
        color: #FFFFFF !important; transform: translateY(-1px);
    }
    .stApp button:focus-visible {
        outline: 3px solid rgba(52,120,212,.32); outline-offset: 2px;
    }

    [data-testid="stMetric"] {
        height: 100%; background: linear-gradient(145deg, #FFFFFF 0%, #FAFBFF 100%);
        border: 1px solid var(--sq-border); border-radius: 15px;
        padding: 1rem 1.1rem; box-shadow: var(--sq-shadow);
    }
    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] *,
    [data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
        color: var(--sq-navy) !important;
    }
    [data-testid="stMetricLabel"] { font-weight: 650; }
    [data-testid="stMetricValue"] { font-weight: 750; }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--sq-border) !important; border-radius: 14px !important;
        background: #FFFFFF; box-shadow: 0 4px 14px rgba(20,38,77,.035);
    }
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        border: 1px solid var(--sq-border); border-radius: 12px; overflow: hidden;
    }
    div[data-testid="stAlert"] { border-radius: 11px; }
    .sq-muted { color: var(--sq-muted) !important; font-size: .9rem; }
    .sq-section-label {
        color: var(--sq-purple) !important; font-size: .75rem !important;
        font-weight: 750; letter-spacing: .09em; text-transform: uppercase;
    }
    .st-key-customer_dashboard_header {
        margin: .35rem 0 1.25rem;
        padding: clamp(1.35rem, 2.8vw, 2rem);
        border: 1px solid rgba(255,255,255,.18);
        border-radius: 20px;
        background: linear-gradient(120deg, #14264D 0%, #23467D 62%, #594AA8 100%);
        box-shadow: 0 14px 32px rgba(20,38,77,.14);
    }
    .sq-customer-kicker {
        color: #D5D0FF; font-size: .74rem; font-weight: 750;
        letter-spacing: .12em; text-transform: uppercase; margin-bottom: .45rem;
    }
    .sq-customer-heading {
        color: #FFFFFF; font-size: clamp(1.65rem, 3vw, 2.25rem);
        font-weight: 760; letter-spacing: -.035em; line-height: 1.15;
    }
    .sq-customer-intro { color: #E0E7F6; margin-top: .5rem; line-height: 1.55; }
    .sq-customer-ticket-top {
        display: flex; align-items: center; justify-content: space-between;
        gap: .8rem; margin-bottom: .45rem;
    }
    .sq-customer-ticket-id { color: var(--sq-purple); font-size: .8rem; font-weight: 750; }
    .sq-customer-ticket-title { color: var(--sq-navy); font-size: 1.02rem;
        font-weight: 700; line-height: 1.4; overflow-wrap: anywhere; }
    .sq-customer-ticket-date { color: var(--sq-muted); font-size: .82rem; margin-top: .45rem; }
    .sq-status-badge { display: inline-flex; align-items: center; padding: .28rem .62rem;
        border: 1px solid transparent; border-radius: 999px; font-size: .74rem;
        font-weight: 700; white-space: nowrap; }
    .sq-status-new { color: #8A5A00; background: #FFF6DF; border-color: #F2DEAA; }
    .sq-status-progress { color: #285FA8; background: #EAF2FF; border-color: #C9DCF8; }
    .sq-status-resolved { color: #176044; background: #EAF7F0; border-color: #C8E7D5; }
    .sq-status-unknown { color: #65738A; background: #F1F4F8; border-color: #DFE6F0; }
    .st-key-customer_dashboard .sq-customer-ticket-list-heading { margin: 1.1rem 0 .25rem; }

    /* Dedicated sign-in views and role selection */
    .sq-auth-brand { color: var(--sq-navy); font-size: 1rem; font-weight: 750; }
    .sq-auth-title { color: var(--sq-navy); font-size: clamp(1.5rem, 2.6vw, 1.9rem);
        font-weight: 760; letter-spacing: -.035em; margin: .2rem 0 .3rem; }
    .sq-auth-copy { color: var(--sq-muted); font-size: .94rem; margin: 0 0 .8rem; }
    .sq-auth-separator { display: flex; align-items: center; gap: .8rem;
        color: #7B8799; font-size: .75rem; font-weight: 700; letter-spacing: .12em;
        margin: .15rem 0 .45rem; }
    .sq-auth-separator::before, .sq-auth-separator::after {
        content: ""; height: 1px; background: var(--sq-border); flex: 1; }
    .sq-role-icon { font-size: 2rem; margin-bottom: .5rem; }
    .sq-role-title { color: var(--sq-navy); font-size: 1.2rem; font-weight: 720; }
    .sq-role-copy { color: var(--sq-muted); min-height: 3rem; line-height: 1.55; }
    .sq-auth-notice { border: 1px solid #CDE9DC; border-radius: 10px;
        background: #F0FAF5; color: #176044; padding: .75rem .9rem; margin: .7rem 0; }
    .st-key-auth_login_card, .st-key-auth_otp_card,
    .st-key-auth_reset_card, .st-key-auth_register_card {
        background: rgba(255,255,255,.96); border: 1px solid var(--sq-border);
        max-width: 600px; margin: 0 auto; border-radius: 18px;
        padding: 1.25rem 1.35rem;
        box-shadow: 0 14px 36px rgba(20,38,77,.08);
    }
    .st-key-auth_brand_panel {
        position: fixed;
        inset: 0 auto 0 0;
        z-index: 0;
        pointer-events: none;
        box-sizing: border-box;
        width: 52.5vw;
        height: 100vh;
        min-height: 100vh;
        margin: 0;
        padding: clamp(1.5rem, 3vw, 2.6rem);
        border-radius: 0;
        background: radial-gradient(circle at 82% 18%, rgba(144,119,255,.32), transparent 28%),
                    linear-gradient(145deg, #14264D 0%, #1B3670 56%, #4D3E99 100%);
        display: flex; flex-direction: column; justify-content: center;
        color: #FFFFFF;
    }
    .sq-brand-mark { color: #FFFFFF; font-size: 1.08rem; font-weight: 760;
        letter-spacing: .01em; margin-bottom: clamp(2rem, 7vh, 4.2rem); }
    .sq-brand-icon { display: inline-grid; place-items: center; width: 30px; height: 30px;
        margin-right: .45rem; border-radius: 9px; color: #FFFFFF;
        background: linear-gradient(140deg, #8A7AF0, #5B8FEA); }
    .sq-brand-headline { color: #FFFFFF; font-size: clamp(2rem, 3.4vw, 2.8rem);
        font-weight: 760; letter-spacing: -.04em; line-height: 1.08; max-width: 440px; }
    .sq-brand-description { color: #D8E1F5; font-size: 1rem; line-height: 1.65;
        max-width: 440px; margin: .85rem 0 2rem; }
    .sq-brand-feature { display: flex; align-items: flex-start; gap: .8rem;
        color: #D8D1FF; margin: .65rem 0; }
    .sq-brand-feature > span { display: grid; place-items: center; flex: 0 0 32px;
        height: 32px; border: 1px solid rgba(222,215,255,.24); border-radius: 10px;
        background: rgba(255,255,255,.08); }
    .sq-brand-feature b { display: block; color: #FFFFFF; font-size: .9rem; }
    .sq-brand-feature small { display: block; color: #C5D1E8; font-size: .83rem; margin-top: .15rem; }
    .st-key-auth_content_panel {
        position: relative;
        z-index: 3;
        max-width: 640px;
        width: 100%;
        margin: 0 auto;
        /* Keep the first auth control below Streamlit's fixed top header. */
        padding: 4.25rem clamp(1rem, 3vw, 2.5rem) .75rem;
        box-sizing: border-box;
    }
    .st-key-auth_content_panel .st-key-auth_login_card,
    .st-key-auth_content_panel .st-key-auth_otp_card,
    .st-key-auth_content_panel .st-key-auth_reset_card,
    .st-key-auth_content_panel .st-key-auth_register_card { max-width: none; }
    .stApp .st-key-open_forgot_password div.stButton > button,
    .stApp .st-key-open_registration div.stButton > button {
        min-height: 32px !important; padding: .15rem .2rem !important;
        color: var(--sq-blue) !important; background: transparent !important;
        border-color: transparent !important; box-shadow: none !important;
    }
    .stApp .st-key-open_forgot_password div.stButton > button *,
    .stApp .st-key-open_registration div.stButton > button * {
        color: var(--sq-blue) !important;
    }
    .stApp .st-key-open_otp_login div.stButton > button {
        color: var(--sq-purple) !important; background: #F7F5FF !important;
        border-color: #D8D0FA !important; box-shadow: none !important;
    }
    .stApp .st-key-open_otp_login div.stButton > button * {
        color: var(--sq-purple) !important;
    }

    /* SupportIQ product landing page */
    .sq-topnav { display:flex; align-items:center; justify-content:space-between;
        gap:1rem; padding:.65rem 0 1rem; border-bottom:1px solid rgba(31,42,61,.08); }
    .sq-logo { display:flex; align-items:center; gap:.55rem; color:var(--sq-navy);
        font-size:1.08rem; font-weight:780; text-decoration:none; white-space:nowrap; }
    .sq-logo-mark { display:grid; place-items:center; width:31px; height:31px;
        border-radius:10px; color:#fff; background:linear-gradient(145deg,#477FE0,#715BD0);
        font-size:1rem; box-shadow:0 4px 10px rgba(78,92,194,.2); }
    .sq-nav-links { display:flex; align-items:center; gap:clamp(1rem,3vw,2.2rem); }
    .sq-nav-links a { color:#536177; font-size:.9rem; font-weight:600; text-decoration:none; }
    .sq-nav-links a:hover { color:var(--sq-purple); }
    .sq-nav-cta { color:#fff !important; padding:.67rem 1.05rem; border-radius:10px;
        background:var(--sq-purple); box-shadow:0 4px 12px rgba(104,85,199,.18); }
    .sq-landing-hero { display:grid; grid-template-columns:1fr 1fr; align-items:center;
        gap:clamp(2rem,5vw,4.2rem); padding:clamp(2.3rem,6vw,5rem) 0 3.8rem; }
    .sq-hero-kicker { color:var(--sq-purple); font-size:.76rem; font-weight:750;
        letter-spacing:.13em; text-transform:uppercase; margin-bottom:.85rem; }
    .sq-landing-title { color:var(--sq-navy); font-size:clamp(2.45rem,5vw,4rem);
        line-height:1.04; letter-spacing:-.055em; font-weight:780; max-width:610px; margin:0; }
    .sq-landing-copy { color:#5D6B80; font-size:1.05rem; line-height:1.75;
        max-width:570px; margin:1.15rem 0 1.5rem; }
    .sq-trust-note { color:#7A8799; font-size:.79rem; margin-top:.9rem; }
    .sq-landing-cta a { display:inline-flex; justify-content:center; align-items:center;
        min-height:44px; padding:.72rem 1rem; border-radius:10px; font-size:.88rem;
        font-weight:680; text-decoration:none; transition:transform .16s ease, box-shadow .16s ease; }
    .sq-landing-cta a:hover { transform:translateY(-2px); }
    .sq-cta-primary { color:#fff !important; background:var(--sq-purple);
        box-shadow:0 6px 16px rgba(104,85,199,.2); }
    .sq-cta-secondary { color:var(--sq-navy) !important; background:#fff; border:1px solid #DCE3EE; }
    .sq-product-preview { position:relative; background:#fff; border:1px solid #E0E6F0;
        border-radius:19px; padding:1.15rem; box-shadow:0 22px 55px rgba(29,46,83,.12); }
    .sq-preview-top { display:flex; align-items:center; justify-content:space-between;
        border-bottom:1px solid #EEF1F6; padding:.1rem .1rem .9rem; }
    .sq-preview-title { color:var(--sq-navy); font-size:.95rem; font-weight:720; }
    .sq-preview-label { color:#718097; font-size:.69rem; background:#F3F5FA; padding:.35rem .55rem; border-radius:99px; }
    .sq-preview-metrics { display:grid; grid-template-columns:repeat(3,1fr); gap:.65rem; padding:.9rem 0; }
    .sq-preview-metric { background:#F8F9FC; border:1px solid #EDF0F5; border-radius:11px; padding:.65rem .7rem; }
    .sq-preview-metric small { display:block; color:#748197; font-size:.65rem; }
    .sq-preview-metric b { display:block; color:var(--sq-navy); font-size:1.08rem; margin-top:.2rem; }
    .sq-preview-section { color:#59677D; font-size:.7rem; font-weight:700; margin:.2rem 0 .45rem; }
    .sq-preview-row { display:grid; grid-template-columns:minmax(0,1fr) auto auto; align-items:center;
        gap:.6rem; border-top:1px solid #F0F2F6; padding:.65rem .1rem; }
    .sq-preview-ticket b { display:block; color:#24324A; font-size:.7rem; font-weight:650; }
    .sq-preview-ticket small { display:block; color:#8490A1; font-size:.62rem; margin-top:.16rem; }
    .sq-pill { border-radius:99px; padding:.28rem .48rem; font-size:.61rem; font-weight:700; white-space:nowrap; }
    .sq-pill-high { background:#FFF0F1; color:#B53E55; }
    .sq-pill-medium { background:#FFF6E9; color:#9A6415; }
    .sq-pill-low { background:#EEF7F2; color:#28805A; }
    .sq-preview-chart { display:flex; align-items:center; gap:.6rem; margin-top:.65rem;
        padding:.7rem .75rem; border-radius:11px; background:#F8F7FD; }
    .sq-chart-bars { height:28px; display:flex; align-items:end; gap:3px; flex:1; }
    .sq-chart-bars i { display:block; width:8px; border-radius:3px 3px 1px 1px; background:linear-gradient(180deg,#8877E0,#5F78D6); }
    .sq-chart-label { color:#727F94; font-size:.63rem; }
    .sq-section { padding:3.4rem 0; scroll-margin-top:1rem; }
    .sq-section-eyebrow { color:var(--sq-purple); font-size:.72rem; font-weight:750;
        letter-spacing:.12em; text-transform:uppercase; text-align:center; }
    .sq-section-title { color:var(--sq-navy); font-size:clamp(1.8rem,3vw,2.5rem);
        line-height:1.14; letter-spacing:-.04em; text-align:center; font-weight:760; margin:.45rem 0; }
    .sq-section-copy { color:#68768B; line-height:1.65; text-align:center; max-width:650px; margin:.55rem auto 1.8rem; }
    .sq-feature-card { height:100%; padding:1.25rem; border:1px solid #E2E7F0;
        border-radius:15px; background:#fff; box-shadow:0 8px 22px rgba(25,43,77,.045); }
    .sq-feature-icon { display:grid; place-items:center; width:40px; height:40px;
        border-radius:12px; background:#F0EEFC; color:#6352BC; margin-bottom:.85rem; }
    .sq-feature-card h3 { color:var(--sq-navy); font-size:1rem; margin:0 0 .45rem; }
    .sq-feature-card p { color:#69778C; font-size:.88rem; line-height:1.6; margin:0; }
    .sq-workflow { display:grid; grid-template-columns:repeat(3,1fr); gap:1rem; margin-top:1.7rem; }
    .sq-work-step { padding:1.2rem; border:1px solid #E2E7F0; background:linear-gradient(150deg,#fff,#FAFAFE); border-radius:15px; }
    .sq-step-number { display:grid; place-items:center; width:30px; height:30px;
        border-radius:9px; color:#5F50B6; background:#EFEDFC; font-weight:750; font-size:.8rem; }
    .sq-work-step h3 { color:var(--sq-navy); font-size:.96rem; margin:.8rem 0 .35rem; }
    .sq-work-step p { color:#69778C; font-size:.84rem; line-height:1.58; margin:0; }
    .st-key-landing_customer_card, .st-key-landing_agent_card {
        height:100%; padding:1.35rem; border:1px solid #E0E6F0;
        border-radius:16px; background:#fff; box-shadow:0 10px 28px rgba(25,43,77,.055); }
    .st-key-landing_customer_card h3, .st-key-landing_agent_card h3 {
        color:var(--sq-navy); font-size:1.1rem; margin:.65rem 0 .35rem; }
    .st-key-landing_customer_card p, .st-key-landing_agent_card p {
        color:#69778C; font-size:.88rem; min-height:1.4rem; }
    .sq-footer-note { color:#8A95A5; font-size:.75rem; text-align:center; padding:1.3rem 0 0; }

    @media (max-width: 800px) {
        .block-container { padding-top: 1.1rem; padding-bottom: 2rem; }
        div[data-testid="stForm"] { padding: 1rem; }
        [data-testid="stMetric"] { padding: .85rem; }
    }
    @media (max-width: 760px) {
        .block-container { padding-left: .85rem; padding-right: .85rem; }
        .block-container:has(.st-key-auth_brand_panel) {
            width: 100%;
            min-height: 0;
            padding: 0;
        }
        .block-container:has(.st-key-auth_brand_panel)
        [data-testid="stHorizontalBlock"]:has(.st-key-auth_brand_panel) {
            flex-wrap: wrap;
            min-height: 0;
        }
        .block-container:has(.st-key-auth_brand_panel)
        [data-testid="stHorizontalBlock"]:has(.st-key-auth_brand_panel) > [data-testid="column"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            max-width: 100% !important;
            min-width: 100%;
        }
        .sq-hero { padding: 1.35rem; border-radius: 15px; }
        [data-testid="stMetric"] { border-radius: 12px; }
        [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
            flex: 1 1 100%; min-width: 100%;
        }
        .st-key-auth_brand_panel {
            position: relative;
            inset: auto;
            z-index: auto;
            width: 100%;
            height: auto;
            min-height: 0;
            margin: 0;
            padding: 1.5rem;
            border-radius: 0;
        }
        .sq-brand-mark { margin-bottom: 1.5rem; }
        .sq-brand-headline { font-size: clamp(1.8rem, 8vw, 2.35rem); }
        .sq-brand-description { margin: .65rem 0 1rem; }
        .sq-brand-feature { margin: .4rem 0; }
        .st-key-auth_content_panel { padding: .8rem 1rem 1.2rem; }
        .sq-topnav { flex-wrap:wrap; }
        .sq-nav-links { gap:.8rem; }
        .sq-landing-hero { grid-template-columns:1fr; padding:2.3rem 0 1.6rem; gap:1.5rem; }
        .sq-landing-title { font-size:clamp(2.3rem,9vw,3.3rem); }
        .sq-workflow { grid-template-columns:1fr; }
        .sq-section { padding:2.5rem 0; }
    }
    @media (max-width: 480px) {
        .sq-nav-links { width:100%; justify-content:space-between; }
        .sq-nav-cta { padding:.55rem .7rem; }
        .sq-preview-row { grid-template-columns:minmax(0,1fr) auto; }
        .sq-preview-row .sq-pill-low { display:none; }
        .sq-landing-cta a { padding:.65rem .7rem; font-size:.78rem; }
        .st-key-auth_login_card, .st-key-auth_otp_card,
        .st-key-auth_reset_card, .st-key-auth_register_card {
            padding: 1rem; border-radius: 15px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# Reusable UI helpers
# ---------------------------------------------------------------------

def render_hero():
    st.markdown(
        """
        <div class="sq-hero">
            <p class="sq-eyebrow">Customer support workspace</p>
            <h1>SupportIQ</h1>
            <p>Smarter support. Faster resolutions.</p>
            <p>One place to raise requests, manage tickets, and track progress.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metrics(counts):
    columns = st.columns(4)
    counts = counts or {}
    metrics = [
        ("My Tickets", int(counts.get("total") or 0)),
        ("Open", int(counts.get("new") or 0)),
        ("In Progress", int(counts.get("in_progress") or 0)),
        ("Resolved", int(counts.get("resolved") or 0)),
    ]
    for column, (label, value) in zip(columns, metrics):
        with column:
            st.metric(label, value)


def render_customer_dashboard_ticket(ticket):
    ticket_id = ticket.get("id")
    subject = html.escape(str(ticket.get("subject") or "Untitled ticket"))
    status = str(ticket.get("status") or "Unknown")
    status_class = {
        "new": "new",
        "in progress": "progress",
        "resolved": "resolved",
    }.get(status.lower(), "unknown")
    created_at = ticket.get("created_at")
    if hasattr(created_at, "strftime"):
        created_at = created_at.strftime("%b %d, %Y")
    created_at = html.escape(str(created_at or "Date unavailable"))
    safe_id = html.escape(str(ticket_id if ticket_id is not None else "—"))
    safe_status = html.escape(status)

    with st.container(border=True):
        st.markdown(
            f'<div class="sq-customer-ticket-top">'
            f'<span class="sq-customer-ticket-id">Ticket #{safe_id}</span>'
            f'<span class="sq-status-badge sq-status-{status_class}">'
            f'{safe_status}</span></div>'
            f'<div class="sq-customer-ticket-title">{subject}</div>'
            f'<div class="sq-customer-ticket-date">Created {created_at}</div>',
            unsafe_allow_html=True,
        )
        st.button(
            "View details",
            key=f"customer_dashboard_open_{ticket_id}",
            on_click=open_ticket,
            args=(ticket_id,),
            use_container_width=True,
        )


def render_status(status):
    if status == "Resolved":
        st.success(f"Status: {status}")
    elif status == "In Progress":
        st.info(f"Status: {status}")
    else:
        st.warning(f"Status: {status}")


def render_ticket_rows(tickets, customer_view=True):
    if not tickets:
        st.info("No tickets found for the selected filters.")
        return

    for ticket in tickets:
        with st.container(border=True):
            left, middle, right = st.columns([4, 2, 1], gap="medium")
            with left:
                st.markdown(f"**#{ticket['id']} — {ticket['subject']}**")
                st.caption(f"Created {ticket['created_at']}")
                if not customer_view:
                    st.caption(
                        f"{ticket.get('customer_name', 'Unknown')} · "
                        f"{ticket.get('predicted_category') or 'Unclassified'}"
                    )
            with middle:
                render_status(ticket["status"])
                if not customer_view:
                    priority = ticket.get("predicted_priority") or "Unknown"
                    st.caption(f"Priority: {priority.title()}")
            with right:
                st.button(
                    "Open",
                    key=f"open_ticket_{'customer' if customer_view else 'agent'}_{ticket['id']}",
                    on_click=open_ticket,
                    args=(ticket["id"],),
                    use_container_width=True,
                )


def render_back_buttons(primary_label, primary_page, secondary_label="Dashboard"):
    first, second = st.columns(2)
    with first:
        st.button(
            primary_label,
            key=f"back_{st.session_state.page}_{primary_page}",
            on_click=go_to,
            args=(primary_page,),
            use_container_width=True,
        )
    with second:
        st.button(
            secondary_label,
            key=f"back_{st.session_state.page}_dashboard",
            on_click=go_to,
            args=("Dashboard",),
            use_container_width=True,
        )


def choose_auth_role(role):
    st.session_state.selected_role = role
    st.session_state.auth_view = "login"


def navigate_auth(view):
    if view == "role_select":
        st.session_state.auth_view = "role_select"
        st.session_state.selected_role = None
        st.session_state.page = "Dashboard"
        st.session_state.selected_ticket_id = None
    else:
        st.session_state.auth_view = view


def prepare_agent_chart_data(tickets):
    """Build chart frames from ticket records without changing database queries."""
    tickets = list(tickets or [])

    def display_value(value, missing_label):
        text = str(value or "").strip()
        return text if text else missing_label

    def counts_frame(values):
        counts = Counter(values)
        return pd.DataFrame(
            sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold())),
            columns=["label", "tickets"],
        )

    priorities = [
        display_value(ticket.get("predicted_priority"), "Unknown").title()
        for ticket in tickets
    ]

    dates = pd.to_datetime(
        [ticket.get("created_at") for ticket in tickets], errors="coerce"
    )
    valid_dates = pd.Series(dates).dropna()
    if valid_dates.empty:
        volume = pd.DataFrame(columns=["date", "tickets"])
    else:
        daily = valid_dates.dt.floor("D").value_counts().sort_index()
        volume = daily.rename_axis("date").reset_index(name="tickets")

    return {
        "priority": counts_frame(priorities),
        "volume": volume,
    }


def style_agent_chart(chart):
    """Apply the light SupportIQ palette explicitly to Vega-Lite charts."""
    return (
        chart.configure(background="#FFFFFF")
        .configure_view(fill="#FFFFFF", strokeOpacity=0)
        .configure_axis(
            labelColor="#14264D",
            titleColor="#14264D",
            labelFontSize=11,
            titleFontSize=12,
            labelPadding=7,
            titlePadding=9,
            gridColor="#E8EDF5",
            domainColor="#D7DFEA",
            tickColor="#C9D3E2",
        )
        .configure_legend(
            labelColor="#14264D",
            titleColor="#14264D",
            labelFontSize=12,
            titleFontSize=12,
            padding=10,
        )
    )


def render_agent_priority_donut(frame):
    with st.container(border=True):
        st.markdown("#### Ticket Priority Distribution")
        if frame.empty:
            st.caption("No ticket data is available for this chart yet.")
            return

        chart = (
            alt.Chart(frame)
            .mark_arc(innerRadius=54, outerRadius=86, stroke="#FFFFFF", strokeWidth=2)
            .encode(
                theta=alt.Theta("tickets:Q", stack=True),
                color=alt.Color(
                    "label:N",
                    title=None,
                    scale=alt.Scale(
                        domain=["High", "Medium", "Low", "Unknown"],
                        range=["#14264D", "#6855C7", "#8A7AF0", "#C9D2E0"],
                    ),
                    legend=alt.Legend(
                        orient="right",
                        direction="vertical",
                        offset=14,
                        symbolSize=95,
                        labelLimit=100,
                        labelColor="#14264D",
                        titleColor="#14264D",
                    ),
                ),
                tooltip=["label:N", "tickets:Q"],
            )
            .properties(
                width="container",
                height=265,
                padding={"left": 16, "right": 16, "top": 18, "bottom": 24},
            )
        )
        chart = style_agent_chart(chart)
        st.altair_chart(
            chart,
            width="stretch",
            alt="Ticket counts grouped by predicted priority",
        )


def render_agent_volume_chart(frame):
    with st.container(border=True):
        st.markdown("#### Ticket Volume Over Time")
        if frame.empty:
            st.caption("No ticket dates are available for this chart yet.")
            return

        chart = (
            alt.Chart(frame)
            .mark_line(color="#6855C7", point=alt.OverlayMarkDef(color="#3478D4", size=55))
            .encode(
                x=alt.X(
                    "date:T",
                    title="Created",
                    axis=alt.Axis(
                        format="%b %d",
                        labelAngle=-35,
                        labelLimit=72,
                        labelOverlap=True,
                        labelFlush=True,
                        tickCount=5,
                    ),
                ),
                y=alt.Y("tickets:Q", title="Tickets", axis=alt.Axis(tickMinStep=1)),
                tooltip=[alt.Tooltip("date:T", title="Created", format="%b %d, %Y"), "tickets:Q"],
            )
        ).properties(
            width="container",
            height=265,
            padding={"left": 16, "right": 16, "top": 18, "bottom": 42},
        )
        chart = style_agent_chart(chart)
        st.altair_chart(
            chart,
            width="stretch",
            alt="Ticket counts by the actual ticket creation date",
        )


def render_landing_page():
    st.markdown(
        """
        <nav class="sq-topnav" aria-label="Main navigation">
            <a class="sq-logo" href="#top"><span class="sq-logo-mark">✦</span>SupportIQ</a>
            <div class="sq-nav-links">
                <a href="#features">Features</a>
                <a href="#how-it-works">How It Works</a>
                <a class="sq-nav-cta" href="#get-started">Get Started</a>
            </div>
        </nav>
        <div id="top"></div>
        """,
        unsafe_allow_html=True,
    )

    hero_copy, hero_visual = st.columns([1.03, .97], gap="large")
    with hero_copy:
        st.markdown(
            """
            <div class="sq-landing-hero-copy">
                <div class="sq-hero-kicker">AI-powered customer support</div>
                <h1 class="sq-landing-title">Smarter Support. Faster Resolutions.</h1>
                <p class="sq-landing-copy">SupportIQ uses AI-powered ticket classification, priority prediction, and sentiment analysis to help customers get support and agents resolve issues more efficiently.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        cta_customer, cta_agent = st.columns(2, gap="small")
        with cta_customer:
            st.button(
                "Continue as Customer",
                key="landing_choose_customer",
                type="primary",
                use_container_width=True,
                on_click=choose_auth_role,
                args=("CUSTOMER",),
            )
        with cta_agent:
            st.button(
                "Continue as Support Agent",
                key="landing_choose_agent",
                type="primary",
                use_container_width=True,
                on_click=choose_auth_role,
                args=("SUPPORT",),
            )
        st.markdown('<div class="sq-trust-note">One workspace for customer requests and agent triage.</div>', unsafe_allow_html=True)

    with hero_visual:
        st.markdown(
            """
            <div class="sq-product-preview" aria-label="Illustrative SupportIQ ticket queue preview">
                <div class="sq-preview-top">
                    <span class="sq-preview-title">Support workspace</span>
                    <span class="sq-preview-label">Illustrative preview</span>
                </div>
                <div class="sq-preview-metrics">
                    <div class="sq-preview-metric"><small>Active tickets</small><b>12</b></div>
                    <div class="sq-preview-metric"><small>High priority</small><b>04</b></div>
                    <div class="sq-preview-metric"><small>In progress</small><b>07</b></div>
                </div>
                <div class="sq-preview-section">PRIORITY QUEUE</div>
                <div class="sq-preview-row">
                    <span class="sq-preview-ticket"><b>Unable to access my account</b><small>Account access · Customer request</small></span>
                    <span class="sq-pill sq-pill-high">High</span><span class="sq-pill sq-pill-high">New</span>
                </div>
                <div class="sq-preview-row">
                    <span class="sq-preview-ticket"><b>Payment was charged twice</b><small>Billing · Negative sentiment</small></span>
                    <span class="sq-pill sq-pill-medium">Medium</span><span class="sq-pill sq-pill-medium">In progress</span>
                </div>
                <div class="sq-preview-row">
                    <span class="sq-preview-ticket"><b>Question about my recent order</b><small>Order support · Customer request</small></span>
                    <span class="sq-pill sq-pill-low">Low</span><span class="sq-pill sq-pill-low">New</span>
                </div>
                <div class="sq-preview-chart">
                    <span class="sq-chart-label">Ticket insights<br><b>Priority and sentiment</b></span>
                    <span class="sq-chart-bars" aria-hidden="true">
                        <i style="height:45%"></i><i style="height:70%"></i><i style="height:55%"></i>
                        <i style="height:90%"></i><i style="height:63%"></i><i style="height:78%"></i>
                        <i style="height:48%"></i><i style="height:100%"></i><i style="height:66%"></i>
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <section class="sq-section" id="features">
            <div class="sq-section-eyebrow">Designed for the support journey</div>
            <h2 class="sq-section-title">The right context for every ticket</h2>
            <p class="sq-section-copy">Bring AI-assisted triage and clear ticket tracking into one straightforward support workflow.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    f1, f2, f3 = st.columns(3, gap="medium")
    feature_cards = [
        ("↗", "Intelligent Prioritization", "Surface urgent complaints with SupportIQ’s existing predicted priority, helping agents decide what to review first."),
        ("◌", "Sentiment Insights", "See the sentiment analysis associated with a complaint and understand the customer’s tone while reviewing a ticket."),
        ("▤", "Centralized Ticket Management", "Submit and track requests as a customer, or review queues and update ticket status as a support agent."),
    ]
    for col, (icon, title, copy) in zip((f1, f2, f3), feature_cards):
        with col:
            st.markdown(
                f'<article class="sq-feature-card"><span class="sq-feature-icon">{icon}</span><h3>{title}</h3><p>{copy}</p></article>',
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <section class="sq-section" id="how-it-works">
            <div class="sq-section-eyebrow">A clear path to resolution</div>
            <h2 class="sq-section-title">How SupportIQ works</h2>
            <p class="sq-section-copy">A customer request moves from submission to AI-assisted review and a visible status update.</p>
            <div class="sq-workflow">
                <article class="sq-work-step"><span class="sq-step-number">01</span><h3>Customer submits a ticket</h3><p>Customers describe their issue and can follow the ticket from their account.</p></article>
                <article class="sq-work-step"><span class="sq-step-number">02</span><h3>AI adds useful context</h3><p>SupportIQ predicts a category and priority, analyzes sentiment, and can recommend similar historical tickets.</p></article>
                <article class="sq-work-step"><span class="sq-step-number">03</span><h3>Agent reviews and updates</h3><p>Agents review the queue and ticket details, then update the status as the issue progresses.</p></article>
            </div>
        </section>
        <section class="sq-section" id="get-started">
            <div class="sq-section-eyebrow">Choose your workspace</div>
            <h2 class="sq-section-title">Get started with SupportIQ</h2>
            <p class="sq-section-copy">Continue to the sign-in experience that matches your role.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    customer_col, agent_col = st.columns(2, gap="large")
    with customer_col:
        with st.container(key="landing_customer_card"):
            st.markdown('<span class="sq-role-icon">♙</span><h3>Customer</h3><p>Submit and track tickets.</p>', unsafe_allow_html=True)
            st.button("Continue as Customer", key="choose_customer", type="primary", use_container_width=True, on_click=choose_auth_role, args=("CUSTOMER",))
    with agent_col:
        with st.container(key="landing_agent_card"):
            st.markdown('<span class="sq-role-icon">▣</span><h3>Support Agent</h3><p>Review and manage support tickets.</p>', unsafe_allow_html=True)
            st.button("Continue as Support Agent", key="choose_support", type="primary", use_container_width=True, on_click=choose_auth_role, args=("SUPPORT",))
    st.markdown('<div class="sq-footer-note">SupportIQ · Intelligent customer support ticket triage</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------
# Authentication screens: role selection, then one focused workflow.
# ---------------------------------------------------------------------

if st.session_state.user is None and st.session_state.get("auth_view", "role_select") == "role_select":
    render_landing_page()
    st.stop()

if st.session_state.user is None:
    view = st.session_state.get("auth_view", "role_select")
    selected_role = st.session_state.get("selected_role")

    def auth_brand(back_target=None):
        if back_target and st.button(
            "← Back",
            key=f"auth_back_{selected_role}_{view}",
        ):
            navigate_auth(back_target)
            st.rerun()


    def auth_heading(title, copy):
        st.markdown(
            f'<div class="sq-auth-title">{title}</div><div class="sq-auth-copy">{copy}</div>',
            unsafe_allow_html=True,
        )

    left_panel, content_panel = st.columns([1.05, .95], gap="large")
    with left_panel:
        with st.container(key="auth_brand_panel"):
            st.markdown('<div class="sq-brand-mark"><span class="sq-brand-icon">✦</span> SupportIQ</div>', unsafe_allow_html=True)
            st.markdown('<div class="sq-brand-headline">Support, made smarter.</div>', unsafe_allow_html=True)
            st.markdown('<div class="sq-brand-description">AI-powered ticket triage that helps teams understand, prioritize, and resolve customer issues.</div>', unsafe_allow_html=True)
            st.markdown('<div class="sq-brand-feature"><span>✦</span><div><b>Intelligent prioritization</b><small>Find urgent issues faster.</small></div></div>', unsafe_allow_html=True)
            st.markdown('<div class="sq-brand-feature"><span>◉</span><div><b>Sentiment insights</b><small>Understand customer concerns.</small></div></div>', unsafe_allow_html=True)
    with content_panel:
        with st.container(key="auth_content_panel"):
            if view == "role_select":
                st.markdown('<div class="sq-auth-title">Get started</div>', unsafe_allow_html=True)
                st.markdown('<div class="sq-auth-copy">Choose how you want to continue.</div>', unsafe_allow_html=True)
                customer_col, agent_col = st.columns(2, gap="large")
                with customer_col:
                    with st.container(border=True):
                        st.markdown('<div class="sq-role-icon">👋</div><div class="sq-role-title">Customer</div>', unsafe_allow_html=True)
                        st.markdown('<div class="sq-role-copy">Submit complaints, track tickets, and stay updated on resolutions.</div>', unsafe_allow_html=True)
                        if st.button("Continue as Customer", key="choose_customer", type="primary", use_container_width=True):
                            st.session_state.selected_role = "CUSTOMER"
                            st.session_state.auth_view = "login"
                            st.rerun()
                with agent_col:
                    with st.container(border=True):
                        st.markdown('<div class="sq-role-icon">🛟</div><div class="sq-role-title">Support Agent</div>', unsafe_allow_html=True)
                        st.markdown('<div class="sq-role-copy">Review incoming tickets, prioritize issues, and resolve customer complaints.</div>', unsafe_allow_html=True)
                        if st.button("Continue as Support Agent", key="choose_support", type="primary", use_container_width=True):
                            st.session_state.selected_role = "SUPPORT"
                            st.session_state.auth_view = "login"
                            st.rerun()

            elif selected_role not in ("CUSTOMER", "SUPPORT"):
                st.session_state.auth_view = "role_select"
                st.rerun()

            else:
                required_role = selected_role
                is_customer = required_role == "CUSTOMER"

                if view == "login":
                    auth_brand("role_select")
                    if is_customer:
                        auth_heading("Welcome back", "Sign in to continue to your SupportIQ account.")
                    else:
                        auth_heading("Support Agent Login", "Sign in to review and manage customer support tickets.")

                    with st.container(key="auth_login_card"):
                        email = st.text_input("Email address", placeholder="you@example.com", key="password_login_email")
                        password = st.text_input("Password", type="password", key="password_login_password")
                        if st.button("Forgot Password?", key="open_forgot_password"):
                            st.session_state.auth_view = "forgot_password"
                            st.rerun()
                        login_submitted = st.button("Login", key="password_login_submit", type="primary", use_container_width=True)

                        if login_submitted:
                            if not email.strip() or not password:
                                st.warning("Please enter your email and password.")
                            else:
                                try:
                                    authenticated = authenticate_user(email, password)
                                    if authenticated and authenticated.get("role") == required_role:
                                        st.session_state.user = authenticated
                                        st.session_state.page = "Dashboard"
                                        st.session_state.selected_ticket_id = None
                                        st.session_state.agent_analysis_cache = {}
                                        st.session_state.auth_notice = None
                                        st.rerun()
                                    else:
                                        st.error("Invalid credentials, unverified email, or account type mismatch.")
                                except Exception:
                                    logger.exception("SupportIQ password login failed")
                                    st.error("Login could not be completed. Please try again.")

                        if st.session_state.get("auth_notice"):
                            st.markdown(f'<div class="sq-auth-notice">{st.session_state.auth_notice}</div>', unsafe_allow_html=True)

                        if is_customer:
                            st.markdown('<div class="sq-auth-separator">OR</div>', unsafe_allow_html=True)
                            if st.button("Login with Email OTP", key="open_otp_login", use_container_width=True):
                                st.session_state.auth_view = "otp_login"
                                st.rerun()
                            if st.button("New to SupportIQ? Create an account.", key="open_registration"):
                                st.session_state.auth_view = "register"
                                st.rerun()

                elif view == "otp_login" and is_customer:
                    auth_brand("login")
                    auth_heading("Login with Email OTP", "We’ll send a one-time code to your verified customer email.")
                    with st.container(key="auth_otp_card"):
                        with st.form("request_login_otp_form"):
                            otp_login_email = st.text_input("Email address", placeholder="you@example.com", key="otp_login_email")
                            request_login_otp = st.form_submit_button("Send Login Code", use_container_width=True)
                        if request_login_otp:
                            clean_email = otp_login_email.strip().lower()
                            if not clean_email:
                                st.warning("Please enter your email address.")
                            else:
                                try:
                                    success, message = request_otp(clean_email, "LOGIN", role=required_role)
                                    if success:
                                        st.session_state["login_otp_email"] = clean_email
                                        st.session_state["login_otp_role"] = required_role
                                        st.success(message)
                                    else:
                                        st.error(message)
                                except Exception:
                                    logger.exception("Login OTP request failed")
                                    st.error("Could not send the code. Please try again later.")
                        if st.session_state.get("login_otp_email") and st.session_state.get("login_otp_role") == required_role:
                            st.caption(f"Enter the 6-digit code sent to {st.session_state['login_otp_email']}.")
                            with st.form("verify_login_otp_form"):
                                login_code = st.text_input("Verification code", max_chars=6, key="login_otp_code")
                                verify_login_submitted = st.form_submit_button("Verify and Login", type="primary", use_container_width=True)
                            if verify_login_submitted:
                                try:
                                    clean_email = st.session_state["login_otp_email"]
                                    valid, message = verify_otp(clean_email, login_code, "LOGIN")
                                    if valid:
                                        authenticated = get_verified_user(clean_email, required_role)
                                        if authenticated:
                                            st.session_state.user = authenticated
                                            st.session_state.page = "Dashboard"
                                            st.session_state.selected_ticket_id = None
                                            st.session_state.agent_analysis_cache = {}
                                            st.session_state.pop("login_otp_email", None)
                                            st.session_state.pop("login_otp_role", None)
                                            st.rerun()
                                        else:
                                            st.error("The account could not be found for this role.")
                                    else:
                                        st.error(message)
                                except Exception:
                                    logger.exception("Login OTP verification failed")
                                    st.error("Verification failed. Please try again.")

                elif view == "forgot_password":
                    auth_brand("login")
                    auth_heading("Reset your password", "Verify your email to choose a new password.")
                    with st.container(key="auth_reset_card"):
                        with st.form("request_reset_otp_form"):
                            reset_email = st.text_input("Registered email address", key="reset_email")
                            request_reset = st.form_submit_button("Send Password Reset Code", use_container_width=True)
                        if request_reset:
                            clean_email = reset_email.strip().lower()
                            if not clean_email:
                                st.warning("Please enter your registered email address.")
                            else:
                                try:
                                    success, message = request_otp(clean_email, "RESET_PASSWORD", role=required_role)
                                    if success:
                                        st.session_state["reset_otp_email"] = clean_email
                                        st.session_state["reset_otp_role"] = required_role
                                        st.success(message)
                                    else:
                                        st.error(message)
                                except Exception:
                                    logger.exception("Password reset OTP request failed")
                                    st.error("Could not send the code. Please try again later.")
                        if st.session_state.get("reset_otp_email") and st.session_state.get("reset_otp_role") == required_role:
                            with st.form("reset_password_form"):
                                reset_code = st.text_input("6-digit verification code", max_chars=6, key="reset_otp_code")
                                new_password = st.text_input("New password", type="password", key="reset_new_password")
                                confirm_new_password = st.text_input("Confirm new password", type="password", key="reset_confirm_password")
                                reset_submitted = st.form_submit_button("Verify Code and Reset Password", type="primary", use_container_width=True)
                            if reset_submitted:
                                if len(new_password) < 8:
                                    st.warning("Your new password must contain at least 8 characters.")
                                elif new_password != confirm_new_password:
                                    st.warning("The passwords do not match.")
                                else:
                                    try:
                                        success, message = reset_password_with_otp(st.session_state["reset_otp_email"], reset_code, new_password, required_role)
                                        if success:
                                            st.session_state.pop("reset_otp_email", None)
                                            st.session_state.pop("reset_otp_role", None)
                                            st.session_state.auth_notice = "Password updated. You can now log in."
                                            st.session_state.auth_view = "login"
                                            st.rerun()
                                        else:
                                            st.error(message)
                                    except Exception:
                                        logger.exception("Password reset failed")
                                        st.error("Password reset failed. Please try again.")

                elif view == "register" and is_customer:
                    auth_brand("login")
                    auth_heading("Create your customer account", "Verify your email first, then complete your profile.")
                    with st.container(key="auth_register_card"):
                        if not st.session_state.get("registration_verified_email"):
                            with st.form("registration_email_form"):
                                registration_email = st.text_input("Email address", placeholder="you@example.com", key="registration_email")
                                request_registration_otp = st.form_submit_button("Send Verification Code", use_container_width=True)
                            if request_registration_otp:
                                clean_email = registration_email.strip().lower()
                                if not clean_email or "@" not in clean_email:
                                    st.warning("Please enter a valid email address.")
                                else:
                                    try:
                                        existing_account = email_exists(clean_email)
                                        success, message = request_otp(clean_email, "REGISTER")
                                        if success:
                                            st.session_state["registration_otp_email"] = clean_email
                                            st.session_state["registration_existing_account"] = existing_account
                                            st.success(message)
                                        else:
                                            st.error(message)
                                    except Exception:
                                        logger.exception("Registration OTP request failed")
                                        st.error("Could not send the code. Please try again later.")
                            if st.session_state.get("registration_otp_email"):
                                with st.form("verify_registration_otp_form"):
                                    registration_code = st.text_input("6-digit verification code", max_chars=6, key="registration_otp_code")
                                    verify_registration = st.form_submit_button("Verify Email", type="primary", use_container_width=True)
                                if verify_registration:
                                    try:
                                        clean_email = st.session_state["registration_otp_email"]
                                        valid, message = verify_otp(clean_email, registration_code, "REGISTER")
                                        if valid:
                                            if st.session_state.get("registration_existing_account"):
                                                st.session_state.pop("registration_otp_email", None)
                                                st.session_state.pop("registration_existing_account", None)
                                                st.session_state.auth_notice = "Your existing account email is now verified. You can log in."
                                                st.session_state.auth_view = "login"
                                                st.rerun()
                                            else:
                                                st.session_state["registration_verified_email"] = clean_email
                                                st.session_state.pop("registration_otp_email", None)
                                                st.rerun()
                                        else:
                                            st.error(message)
                                    except Exception:
                                        logger.exception("Registration OTP verification failed")
                                        st.error("Email verification failed. Please try again.")
                        verified_email = st.session_state.get("registration_verified_email")
                        if verified_email:
                            st.text_input("Verified email address", value=verified_email, disabled=True, key="verified_registration_email_display")
                            with st.form("registration_details_form"):
                                full_name = st.text_input("Full name", key="register_full_name")
                                new_password = st.text_input("Create password", type="password", key="register_password")
                                confirm_password = st.text_input("Confirm password", type="password", key="register_confirm_password")
                                create_account = st.form_submit_button("Create Account", type="primary", use_container_width=True)
                            if create_account:
                                name = full_name.strip()
                                if not name or not new_password:
                                    st.warning("Please complete all fields.")
                                elif len(new_password) < 8:
                                    st.warning("Your password must contain at least 8 characters.")
                                elif new_password != confirm_password:
                                    st.warning("The passwords do not match.")
                                else:
                                    try:
                                        success, message = register_customer(name, verified_email, new_password, email_verified=True)
                                        if success:
                                            st.session_state.pop("registration_verified_email", None)
                                            st.session_state.auth_notice = "Account created. You can now log in."
                                            st.session_state.auth_view = "login"
                                            st.rerun()
                                        else:
                                            st.error(message)
                                    except Exception:
                                        logger.exception("Customer registration failed")
                                        st.error("Registration could not be completed. Please try again.")

                else:
                    st.session_state.auth_view = "login"
                    st.rerun()


# ---------------------------------------------------------------------
# Role validation and sidebar navigation
# ---------------------------------------------------------------------

user = st.session_state.get("user")

if not user:
    st.warning("Please log in to continue.")
    st.stop()

role = user.get("role")
if role not in ("CUSTOMER", "SUPPORT"):
    logout()
    st.error("Your session is invalid. Please log in again.")
    st.stop()

if role == "CUSTOMER":
    navigation = ["Dashboard", "Submit Complaint", "My Tickets", "Profile"]
else:
    navigation = [
        "Dashboard", "All Tickets", "New Tickets", "In Progress", "Resolved"
    ]

if st.session_state.page not in navigation + ["Ticket Details"]:
    st.session_state.page = "Dashboard"

with st.sidebar:
    st.markdown("## 🎫 SupportIQ")
    st.caption("Customer Workspace" if role == "CUSTOMER" else "Support Workspace")
    st.divider()

    for page_name in navigation:
        st.button(
            page_name,
            key=f"nav_{role}_{page_name}",
            type="primary" if st.session_state.page == page_name else "secondary",
            on_click=go_to,
            args=(page_name,),
            use_container_width=True,
        )

    st.divider()
    st.markdown(f"**{user['full_name']}**")
    st.caption(user["email"])
    st.caption("Customer" if role == "CUSTOMER" else "Support Agent")
    st.button(
        "Logout",
        key="logout_button",
        on_click=logout,
        use_container_width=True,
    )


# ---------------------------------------------------------------------
# Customer dashboard
# ---------------------------------------------------------------------

page = st.session_state.page

if role == "CUSTOMER" and page == "Dashboard":
    with st.container(key="customer_dashboard"):
        with st.container(key="customer_dashboard_header"):
            heading_col, action_col = st.columns([3.4, 1.25], vertical_alignment="center")
            with heading_col:
                customer_name = html.escape(str(user.get("full_name") or "there"))
                st.markdown(
                    '<div class="sq-customer-kicker">Customer workspace</div>'
                    f'<div class="sq-customer-heading">Welcome back, {customer_name}</div>'
                    '<div class="sq-customer-intro">Track your requests and get help from one clear, organized view.</div>',
                    unsafe_allow_html=True,
                )
            with action_col:
                st.button(
                    "＋ Create New Ticket",
                    key="dashboard_submit",
                    type="primary",
                    on_click=go_to,
                    args=("Submit Complaint",),
                    use_container_width=True,
                )

        try:
            render_metrics(get_customer_ticket_counts(user["user_id"]))
        except Exception:
            logger.exception("Customer dashboard metrics failed")
            st.error("Your ticket summary could not be loaded.")

        st.markdown('<h2 class="sq-customer-ticket-list-heading">Recent tickets</h2>', unsafe_allow_html=True)
        search_col, status_col = st.columns([2.2, 1])
        with search_col:
            dashboard_search = st.text_input(
                "Search your tickets",
                placeholder="Ticket ID or subject",
                key="customer_dashboard_search",
            )
        with status_col:
            dashboard_status = st.selectbox(
                "Status",
                ["All", "New", "In Progress", "Resolved"],
                key="customer_dashboard_status",
            )

        try:
            dashboard_tickets = get_customer_tickets(
                user["user_id"],
                status=None if dashboard_status == "All" else dashboard_status,
                search=dashboard_search,
            )
            if dashboard_tickets:
                for ticket in dashboard_tickets[:5]:
                    render_customer_dashboard_ticket(ticket)
                if len(dashboard_tickets) > 5:
                    st.caption(
                        f"Showing 5 of {len(dashboard_tickets)} matching tickets. "
                        "Open My Tickets to view the full list."
                    )
            else:
                st.info("No tickets match these filters yet.")
        except Exception:
            logger.exception("Customer dashboard tickets failed")
            st.error("Your recent tickets could not be loaded.")

        st.button(
            "View All My Tickets",
            key="dashboard_tickets",
            on_click=go_to,
            args=("My Tickets",),
        )


# ---------------------------------------------------------------------
# Customer: submit complaint
# ---------------------------------------------------------------------

elif role == "CUSTOMER" and page == "Submit Complaint":
    st.title("Submit a Complaint")
    st.write("Describe your issue clearly so our support team can investigate.")

    with st.form("complaint_form"):
        subject = st.text_input(
            "Subject",
            placeholder="Briefly describe your issue",
            max_chars=255,
        )
        body = st.text_area(
            "Complaint details",
            placeholder="Explain what happened, when it happened, and what help you need.",
            height=180,
            max_chars=5000,
        )
        submitted = st.form_submit_button(
            "Submit Complaint", type="primary", use_container_width=True
        )

    if submitted:
        clean_subject, clean_body = subject.strip(), body.strip()
        if not clean_subject or not clean_body:
            st.warning("Please provide both a subject and details.")
        else:
            try:
                with st.spinner("Submitting your complaint..."):
                    from src.ml_service import analyze_ticket

                    result = analyze_ticket(clean_body)
                    sentiment_data = result.get("sentiment") or {}
                    ticket_id = save_ticket(
                        user_id=user["user_id"],
                        subject=clean_subject,
                        body=clean_body,
                        category=result["category"],
                        priority=result["priority"],
                        sentiment=sentiment_data.get("sentiment"),
sentiment_score=sentiment_data.get("score"),
                    )
                st.success(f"Your complaint has been submitted. Ticket ID: #{ticket_id}.")
                st.info("Our support team will review it. Track progress in My Tickets.")
                st.button(
                    "View My Ticket",
                    key="new_ticket_details",
                    type="primary",
                    on_click=open_ticket,
                    args=(ticket_id,),
                )
            except Exception:
                logger.exception("Complaint submission failed")
                st.error("Your complaint could not be submitted. Please try again.")

    st.button(
        "← Back to Dashboard",
        key="submit_back_dashboard",
        on_click=go_to,
        args=("Dashboard",),
    )


# ---------------------------------------------------------------------
# Customer: ticket history
# ---------------------------------------------------------------------

elif role == "CUSTOMER" and page == "My Tickets":
    st.title("My Tickets")
    st.write("View and track the complaints you have submitted.")

    status_filter = st.selectbox(
        "Filter by status",
        ["All", "New", "In Progress", "Resolved"],
        key="customer_status_filter",
    )
    search_text = st.text_input(
        "Search by ticket ID or subject",
        placeholder="Enter a ticket ID or subject",
        key="customer_ticket_search",
    )

    try:
        tickets = get_customer_tickets(
            user["user_id"],
            status=None if status_filter == "All" else status_filter,
            search=search_text,
        )
        render_ticket_rows(tickets, customer_view=True)
    except Exception:
        logger.exception("Customer ticket history failed")
        st.error("Your tickets could not be loaded.")

    st.button(
        "＋ Submit Another Complaint",
        key="tickets_new_complaint",
        on_click=go_to,
        args=("Submit Complaint",),
    )
    st.button(
        "← Back to Dashboard",
        key="tickets_back_dashboard",
        on_click=go_to,
        args=("Dashboard",),
    )


# ---------------------------------------------------------------------
# Customer: ticket details
# ---------------------------------------------------------------------

elif role == "CUSTOMER" and page == "Ticket Details":
    ticket_id = st.session_state.selected_ticket_id
    st.title("Ticket Details")

    if ticket_id is None:
        st.info("Choose a ticket from My Tickets to see its details.")
    else:
        try:
            ticket = get_customer_ticket_by_id(ticket_id, user["user_id"])
            if not ticket:
                st.error("This ticket was not found or does not belong to your account.")
            else:
                st.markdown(f"## #{ticket['id']} — {ticket['subject']}")
                st.caption(f"Submitted: {ticket['created_at']}")
                st.markdown("### Complaint")
                with st.container(border=True):
                    st.write(ticket["body"])

                st.markdown("### Current Status")
                render_status(ticket["status"])

                statuses = ["New", "In Progress", "Resolved"]
                current_index = statuses.index(ticket["status"])
                st.markdown("### Progress")
                progress_cols = st.columns(3)
                for index, status in enumerate(statuses):
                    with progress_cols[index]:
                        if index < current_index:
                            st.success(f"✓ {status}")
                        elif index == current_index:
                            st.info(f"● {status}\n\nCurrent status")
                        else:
                            st.caption(f"○ {status}")

                st.caption("Status updates are managed by the support team.")
        except Exception:
            logger.exception("Customer ticket details failed")
            st.error("Ticket details could not be loaded.")

    render_back_buttons("← My Tickets", "My Tickets")


# ---------------------------------------------------------------------
# Customer: profile
# ---------------------------------------------------------------------

elif role == "CUSTOMER" and page == "Profile":
    st.title("My Profile")
    st.write("Your account information.")

    with st.container(border=True):
        st.text_input("Full name", value=user["full_name"], disabled=True)
        st.text_input("Email address", value=user["email"], disabled=True)
        st.text_input("Account role", value="Customer", disabled=True)

    st.caption("Profile editing is not enabled in this version.")
    st.button(
        "← Back to Dashboard",
        key="profile_back_dashboard",
        on_click=go_to,
        args=("Dashboard",),
    )



# ---------------------------------------------------------------------
# Agent dashboard - Freshdesk-inspired UI
# ---------------------------------------------------------------------

elif role == "SUPPORT" and page == "Dashboard":
    st.markdown(
        """
        <style>
        .agent-dashboard-header {
            display: flex; align-items: center; gap: .85rem;
            margin: .25rem 0 1rem; padding: .15rem 0 .9rem;
            border-bottom: 1px solid #DFE6F0;
        }
        .agent-dashboard-brand {
            color: #14264D; font-size: .96rem; font-weight: 760;
            letter-spacing: -.015em; white-space: nowrap;
        }
        .agent-dashboard-title {
            color: #14264D; font-size: 1.15rem; font-weight: 720;
            line-height: 1.3; margin: 0;
        }
        .agent-dashboard-welcome { color: #65738A; font-size: .82rem; margin-left: auto; }
        .agent-ticket-badge {
            display: inline-block; border-radius: 999px; padding: .25rem .55rem;
            font-size: .76rem; font-weight: 700; white-space: nowrap;
        }
        .agent-priority-high { color: #963B53; background: #FCEEF1; }
        .agent-priority-medium { color: #85581A; background: #FBF3E5; }
        .agent-priority-low { color: #28684F; background: #EAF5EF; }
        .agent-priority-unknown, .agent-status-badge { color: #53627A; background: #EEF1F6; }
        .agent-status-new { color: #315F9E; background: #EDF4FC; }
        .agent-status-in-progress { color: #5D4CA8; background: #F0EDFC; }
        @media (max-width: 760px) {
            .agent-dashboard-header { flex-wrap: wrap; gap: .45rem .7rem; }
            .agent-dashboard-welcome { width: 100%; margin-left: 0; }
            .agent-dashboard-title { font-size: 1.05rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    safe_agent_name = html.escape(str(user.get("full_name") or "Support Agent"))
    st.markdown(
        '<div class="agent-dashboard-header">'
        '<span class="agent-dashboard-brand">✦ SupportIQ</span>'
        '<h1 class="agent-dashboard-title">Support Agent Dashboard</h1>'
        f'<span class="agent-dashboard-welcome">Welcome back, {safe_agent_name}</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    try:
        # Fetch actual ticket records once. Resolved tickets stay out of the
        # active queue while remaining available to analytics and the KPI row.
        all_tickets = get_agent_tickets()
        queue = [
            ticket for ticket in all_tickets
            if ticket.get("status") != "Resolved"
        ]

        # Keep the queue ordered by predicted priority, then status and age.
        priority_order = {
            "high": 0,
            "medium": 1,
            "low": 2,
        }
        status_order = {
            "New": 0,
            "In Progress": 1,
        }

        queue.sort(
            key=lambda ticket: (
                priority_order.get(
                    str(ticket.get("predicted_priority") or "").lower(),
                    3,
                ),
                status_order.get(ticket.get("status"), 2),
                ticket.get("created_at") or "",
            )
        )

        high_count = sum(
            1 for ticket in queue
            if str(ticket.get("predicted_priority") or "").lower() == "high"
        )
        progress_count = sum(
            1 for ticket in queue if ticket.get("status") == "In Progress"
        )
        resolved_count = sum(
            1 for ticket in all_tickets if ticket.get("status") == "Resolved"
        )

        chart_data = prepare_agent_chart_data(all_tickets)
        overview_tab, queue_tab = st.tabs(["Overview", "Ticket Queue"])

        with overview_tab:
            metric_cols = st.columns(4, gap="small")
            metrics = (
                ("Active Tickets", len(queue)),
                ("High-Priority Tickets", high_count),
                ("Under Review", progress_count),
                ("Resolved", resolved_count),
            )
            for metric_col, (label, value) in zip(metric_cols, metrics):
                with metric_col:
                    st.metric(label, value, border=True)

            st.markdown("### Ticket Analytics")
            chart_col1, chart_col2 = st.columns(2, gap="medium")
            with chart_col1:
                render_agent_priority_donut(chart_data["priority"])
            with chart_col2:
                render_agent_volume_chart(chart_data["volume"])

        with queue_tab:
            st.markdown("### Active Ticket Queue")
            st.caption("Resolved tickets are excluded. Tickets are ordered by predicted priority.")
            filter_col, search_col = st.columns([1, 2], gap="medium")

            with filter_col:
                priority_filter = st.selectbox(
                    "Priority filter",
                    ["All", "High", "Medium", "Low"],
                    key="dashboard_priority_filter",
                )

            with search_col:
                dashboard_search = st.text_input(
                    "Search active tickets",
                    placeholder="Search subject or customer",
                    key="dashboard_ticket_search",
                )

            filtered_queue = queue
            if priority_filter != "All":
                filtered_queue = [
                    ticket for ticket in filtered_queue
                    if str(ticket.get("predicted_priority") or "").lower()
                    == priority_filter.lower()
                ]

            if dashboard_search.strip():
                search_term = dashboard_search.strip().lower()
                filtered_queue = [
                    ticket for ticket in filtered_queue
                    if search_term in str(ticket.get("subject") or "").lower()
                    or search_term in str(ticket.get("customer_name") or "").lower()
                    or search_term in str(ticket.get("id") or "").lower()
                ]

            if filtered_queue:
                for ticket in filtered_queue[:5]:
                    ticket_id = ticket["id"]
                    priority = str(ticket.get("predicted_priority") or "Unknown")
                    priority_class = {
                        "high": "agent-priority-high",
                        "medium": "agent-priority-medium",
                        "low": "agent-priority-low",
                    }.get(priority.lower(), "agent-priority-unknown")
                    status = str(ticket.get("status") or "Unknown")
                    status_class = {
                        "new": "agent-status-new",
                        "in progress": "agent-status-in-progress",
                    }.get(status.lower(), "agent-status-badge")

                    with st.container(border=True):
                        subject_col, priority_col, status_col, action_col = st.columns(
                            [4, 1.1, 1.15, 1.1],
                            vertical_alignment="center",
                        )
                        with subject_col:
                            st.markdown(
                                f"**#{html.escape(str(ticket_id))} — "
                                f"{html.escape(str(ticket.get('subject') or 'Untitled ticket'))}**"
                            )
                            st.caption(
                                f"Customer: {html.escape(str(ticket.get('customer_name') or 'Unknown'))}"
                                f" · {html.escape(str(ticket.get('predicted_category') or 'Unclassified'))}"
                            )
                        with priority_col:
                            st.markdown(
                                f'<span class="agent-ticket-badge {priority_class}">'
                                f'{html.escape(priority.title())}</span>',
                                unsafe_allow_html=True,
                            )
                        with status_col:
                            st.markdown(
                                f'<span class="agent-ticket-badge {status_class}">'
                                f'{html.escape(status)}</span>',
                                unsafe_allow_html=True,
                            )
                        with action_col:
                            st.button(
                                "Review",
                                key=f"dashboard_review_{ticket_id}",
                                on_click=open_ticket,
                                args=(ticket_id,),
                                width="stretch",
                            )

                if len(filtered_queue) > 5:
                    st.caption(
                        f"Showing 5 of {len(filtered_queue)} matching active tickets. "
                        "Open All Tickets to see the complete queue."
                    )
            else:
                st.info("No active tickets match these filters.")

            st.button(
                "Open All Tickets",
                key="agent_dashboard_all",
                type="primary",
                on_click=go_to,
                args=("All Tickets",),
                width="stretch",
            )

    except Exception:
        logger.exception("Agent dashboard failed")
        st.error("The agent dashboard could not be loaded.")





# ---------------------------------------------------------------------
# Agent: ticket queues
# ---------------------------------------------------------------------

elif role == "SUPPORT" and page in (
    "All Tickets", "New Tickets", "In Progress", "Resolved"
):
    st.title(page)
    st.write("Search, review, and manage customer support requests.")

    fixed_status = {
        "New Tickets": "New",
        "In Progress": "In Progress",
        "Resolved": "Resolved",
    }.get(page)

    filter_col, search_col = st.columns([1, 2])
    with filter_col:
        if fixed_status:
            st.text_input("Current status filter", value=fixed_status, disabled=True)
            status_filter = fixed_status
        else:
            selected_status = st.selectbox(
                "Filter by status",
                ["All", "New", "In Progress", "Resolved"],
                key="agent_status_filter",
            )
            status_filter = None if selected_status == "All" else selected_status

    with search_col:
        search_text = st.text_input(
            "Search tickets",
            placeholder="Ticket, customer name, or email",
            key="agent_ticket_search",
        )

    try:
        tickets = get_agent_tickets(status=status_filter, search=search_text)
        render_ticket_rows(tickets, customer_view=False)
    except Exception:
        logger.exception("Agent ticket queue failed")
        st.error("The ticket queue could not be loaded.")

    st.button(
        "← Back to Dashboard",
        key="agent_queue_dashboard",
        on_click=go_to,
        args=("Dashboard",),
    )


# ---------------------------------------------------------------------
# Agent: ticket details and AI review
# ---------------------------------------------------------------------

elif role == "SUPPORT" and page == "Ticket Details":
    ticket_id = st.session_state.selected_ticket_id
    st.title("Ticket Details")

    if ticket_id is None:
        st.info("Select a ticket from the ticket queue.")
    else:
        try:
            ticket = get_agent_ticket_by_id(ticket_id)
            if not ticket:
                st.error("Ticket not found.")
            else:
                st.markdown(f"## #{ticket['id']} — {ticket['subject']}")

                customer_col, ticket_col = st.columns(2)
                with customer_col:
                    st.markdown("### Customer Information")
                    st.write(f"**Name:** {ticket.get('customer_name', 'N/A')}")
                    st.write(f"**Email:** {ticket.get('customer_email', 'N/A')}")
                    st.write(f"**Customer ID:** {ticket.get('customer_id', 'N/A')}")
                with ticket_col:
                    st.markdown("### Ticket Information")
                    st.write(f"**Created:** {ticket['created_at']}")
                    render_status(ticket["status"])

                st.divider()
                st.markdown("### Complaint Details")
                with st.container(border=True):
                    st.write(ticket["body"])

                st.divider()
                st.markdown("### AI-Assisted Review")
                ai1, ai2, ai3 = st.columns(3)
                with ai1:
                    st.metric("Predicted Category", ticket.get("predicted_category") or "N/A")
                with ai2:
                    priority = ticket.get("predicted_priority")
                    st.metric("Predicted Priority", priority.title() if priority else "N/A")
                with ai3:
                    sentiment = ticket.get("predicted_sentiment")
                    st.metric("Sentiment", sentiment.title() if sentiment else "N/A")

                score = ticket.get("sentiment_score")
                if score is not None:
                    st.caption(f"Stored sentiment score: {float(score):.2%}")
                st.caption(f"Model version: {ticket.get('model_version') or 'N/A'}")

                if ticket_id not in st.session_state.agent_analysis_cache:
                    try:
                        with st.spinner("Finding similar historical tickets..."):
                            from src.ml_service import analyze_ticket
                            st.session_state.agent_analysis_cache[ticket_id] = analyze_ticket(
                                ticket["body"]
                            )
                    except Exception:
                        logger.exception("Similar ticket analysis failed")
                        st.session_state.agent_analysis_cache[ticket_id] = {}

                analysis = st.session_state.agent_analysis_cache.get(ticket_id, {})
                similar_tickets = analysis.get("similar_tickets", [])
                st.markdown("### Similar Historical Tickets")

                if similar_tickets:
                    for index, similar in enumerate(similar_tickets, start=1):
                        title = similar.get("subject", "Similar historical ticket")
                        with st.expander(f"{index}. {title}"):
                            st.write(similar.get("body", ""))
                            st.write(f"**Category:** {similar.get('queue', 'N/A')}")
                            st.write(f"**Priority:** {similar.get('priority', 'N/A')}")
                            similarity = similar.get("similarity_score")
                            if similarity is not None:
                                st.write(f"**Similarity:** {float(similarity):.1%}")
                else:
                    st.info(
                        "No similar historical tickets were found, or the results are unavailable."
                    )

                st.divider()
                st.markdown("### Update Ticket Status")
                valid_statuses = ["New", "In Progress", "Resolved"]
                current_status = ticket["status"]
                status_index = valid_statuses.index(current_status)

                new_status = st.selectbox(
                    "Status",
                    valid_statuses,
                    index=status_index,
                    key=f"agent_update_status_{ticket_id}",
                )

                if st.button("Save Status", key=f"save_status_{ticket_id}", type="primary"):
                    try:
                        update_ticket_status(ticket_id, new_status)
                        st.session_state.agent_analysis_cache.pop(ticket_id, None)
                        st.success("Ticket status updated.")
                        st.rerun()
                    except Exception:
                        logger.exception("Ticket status update failed")
                        st.error("The ticket status could not be updated.")
        except Exception:
            logger.exception("Agent ticket details failed")
            st.error("Ticket details could not be loaded.")

    render_back_buttons("← Back to Ticket Queue", "All Tickets")
