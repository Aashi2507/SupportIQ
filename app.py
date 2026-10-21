import logging
import streamlit as st

from auth import authenticate_user, register_customer
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


# ---------------------------------------------------------------------
# Application styling — one valid style block, no duplicate overrides
# ---------------------------------------------------------------------

st.markdown( """
    <style>
    :root {
        --sq-navy: #172554;
        --sq-navy-light: #243B78;
        --sq-purple: #6D5BD0;
        --sq-purple-hover: #5545B8;
        --sq-bg: #F5F6FC;
        --sq-card: #FFFFFF;
        --sq-text: #1E293B;
        --sq-muted: #64748B;
        --sq-border: #DCE1F0;
    }

    html, body, [class*="css"] {
        font-family: Inter, ui-sans-serif, system-ui, -apple-system,
                     BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    .stApp {
        background: var(--sq-bg);
        color: var(--sq-text);
    }

    .block-container {
        max-width: 1220px;
        padding-top: 1.6rem;
        padding-bottom: 3rem;
    }

    /* Default text contrast. Widget labels are explicitly dark. */
    .stApp p,
    .stApp li,
    .stApp label,
    .stApp [data-testid="stMarkdownContainer"],
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stWidgetLabel"],
    .stApp [data-testid="stWidgetLabel"] *,
    .stApp [data-testid="stRadio"] label,
    .stApp [data-testid="stRadio"] label *,
    .stApp [data-testid="stSelectbox"] label,
    .stApp [data-testid="stTextInput"] label,
    .stApp [data-testid="stTextArea"] label {
        color: var(--sq-text) !important;
    }

    h1, h2, h3, h4 {
        color: var(--sq-navy) !important;
        letter-spacing: -0.02em;
    }

    h1 { font-weight: 750 !important; }
    h2, h3 { font-weight: 700 !important; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: var(--sq-navy) !important;
        border-right: 1px solid #24366A;
    }

    section[data-testid="stSidebar"] > div {
        background: var(--sq-navy) !important;
    }

    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: #FFFFFF !important;
    }

    section[data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.20);
    }

    section[data-testid="stSidebar"] div.stButton > button {
        width: 100%;
        min-height: 42px;
        text-align: left;
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 10px;
        background: #203466;
        color: #FFFFFF !important;
        font-weight: 600;
        padding: 0.55rem 0.8rem;
        transition: background 0.15s ease, border-color 0.15s ease;
    }

    section[data-testid="stSidebar"] div.stButton > button:hover {
        background: var(--sq-purple);
        border-color: var(--sq-purple);
        color: #FFFFFF !important;
    }

    section[data-testid="stSidebar"] div.stButton > button[kind="primary"] {
        background: var(--sq-purple);
        border-color: var(--sq-purple);
        color: #FFFFFF !important;
    }

    /* Hero banner */
    .sq-hero {
        background: linear-gradient(120deg, #172554 0%, #283B78 58%, #6049B8 100%);
        padding: 1.8rem 2rem;
        border-radius: 18px;
        margin: 0 0 1.5rem 0;
        box-shadow: 0 10px 28px rgba(23,37,84,0.13);
    }

    .sq-hero h1 {
        color: #FFFFFF !important;
        font-size: clamp(2rem, 4vw, 2.8rem);
        margin: 0 0 0.45rem 0;
        line-height: 1.15;
    }

    .sq-hero p {
        color: #F0EEFF !important;
        margin: 0.25rem 0;
        font-size: 1rem;
    }

    .sq-eyebrow {
        color: #DCD6FF !important;
        font-size: 0.78rem !important;
        font-weight: 750;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 0.55rem !important;
    }

    /* Forms and inputs */
    div[data-testid="stForm"] {
        background: #FFFFFF;
        border: 1px solid var(--sq-border);
        border-radius: 16px;
        padding: 1.35rem 1.4rem 1rem 1.4rem;
        box-shadow: 0 5px 18px rgba(23,37,84,0.045);
    }

    .stTextInput input,
    .stTextArea textarea,
    .stNumberInput input {
        color: var(--sq-text) !important;
        -webkit-text-fill-color: var(--sq-text) !important;
        background: #FFFFFF !important;
        border: 1px solid #BFC7DF !important;
        border-radius: 9px !important;
        caret-color: var(--sq-navy);
    }

    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {
        color: #7B849A !important;
        -webkit-text-fill-color: #7B849A !important;
        opacity: 1;
    }

    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border-color: var(--sq-purple) !important;
        box-shadow: 0 0 0 2px rgba(109,91,208,0.14) !important;
    }

    div[data-baseweb="select"] > div {
        background: #FFFFFF !important;
        border-color: #BFC7DF !important;
        border-radius: 9px !important;
    }

    div[data-baseweb="select"] * {
        color: var(--sq-text) !important;
    }

    /* Buttons */
    .stApp div.stButton > button,
    .stApp div.stFormSubmitButton > button,
    .stApp [data-testid="stDownloadButton"] button {
        min-height: 40px;
        border-radius: 9px;
        font-weight: 650;
        border: 1px solid var(--sq-purple);
        background: var(--sq-purple);
        color: #FFFFFF !important;
        transition: background 0.15s ease, border-color 0.15s ease;
    }

    .stApp div.stButton > button *,
    .stApp div.stFormSubmitButton > button *,
    .stApp [data-testid="stDownloadButton"] button * {
        color: #FFFFFF !important;
    }

    .stApp div.stButton > button:hover,
    .stApp div.stFormSubmitButton > button:hover,
    .stApp [data-testid="stDownloadButton"] button:hover {
        background: var(--sq-purple-hover);
        border-color: var(--sq-purple-hover);
        color: #FFFFFF !important;
    }

    .stApp button:focus-visible {
        outline: 3px solid rgba(109,91,208,0.30);
        outline-offset: 2px;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid var(--sq-border);
        border-radius: 14px;
        padding: 1rem 1.1rem;
        box-shadow: 0 4px 14px rgba(23,37,84,0.035);
    }

    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] *,
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] * {
        color: var(--sq-navy) !important;
    }

    [data-testid="stMetricLabel"] {
        font-weight: 650;
    }

    /* Ticket cards and tables */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--sq-border) !important;
        border-radius: 13px !important;
        background: #FFFFFF;
    }

    [data-testid="stDataFrame"],
    [data-testid="stTable"] {
        border: 1px solid var(--sq-border);
        border-radius: 10px;
        overflow: hidden;
    }

    .sq-muted {
        color: var(--sq-muted) !important;
        font-size: 0.9rem;
    }

    .sq-section-label {
        color: var(--sq-purple) !important;
        font-size: 0.76rem !important;
        font-weight: 750;
        letter-spacing: 0.09em;
        text-transform: uppercase;
    }

    div[data-testid="stAlert"] {
        border-radius: 10px;
    }

    @media (max-width: 700px) {
        .block-container {
            padding-top: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        .sq-hero {
            padding: 1.35rem;
        }
        div[data-testid="stForm"] {
            padding: 1rem;
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
    metrics = [
        ("Total Tickets", counts.get("total", 0)),
        ("New", counts.get("new", 0)),
        ("In Progress", counts.get("in_progress", 0)),
        ("Resolved", counts.get("resolved", 0)),
    ]
    for column, (label, value) in zip(columns, metrics):
        with column:
            st.metric(label, value)


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
            left, middle, right = st.columns([4, 2, 1])
            with left:
                st.markdown(f"**#{ticket['id']} — {ticket['subject']}**")
                st.caption(f"Created: {ticket['created_at']}")
                if not customer_view:
                    st.caption(
                        f"Customer: {ticket.get('customer_name', 'Unknown')} · "
                        f"Category: {ticket.get('predicted_category') or 'Unclassified'}"
                    )
            with middle:
                st.write(ticket["status"])
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


# ---------------------------------------------------------------------
# Login and customer registration
# ---------------------------------------------------------------------

if st.session_state.user is None:
    render_hero()

    login_left, login_center, login_right = st.columns([1, 1.25, 1])
    with login_center:
        st.subheader("Welcome to SupportIQ")
        st.write("Sign in to access your support workspace.")

        account_type = st.radio(
            "Sign in as",
            ["Customer", "Support Agent"],
            horizontal=True,
            key="account_type",
        )

        with st.form("login_form"):
            email = st.text_input("Email address", placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            login_submitted = st.form_submit_button(
                "Login",
                type="primary",
                use_container_width=True,
            )

        if login_submitted:
            if not email.strip() or not password:
                st.warning("Please enter your email and password.")
            else:
                try:
                    authenticated = authenticate_user(email, password)
                    required_role = "CUSTOMER" if account_type == "Customer" else "SUPPORT"

                    if authenticated and authenticated.get("role") == required_role:
                        st.session_state.user = authenticated
                        st.session_state.page = "Dashboard"
                        st.session_state.selected_ticket_id = None
                        st.session_state.agent_analysis_cache = {}
                        st.rerun()
                    else:
                        st.error(
                            "Invalid email or password, or the account "
                            "does not match the selected account type."
                        )
                except Exception:
                    logger.exception("SupportIQ login failed")
                    st.error("Login could not be completed. Please try again.")

        if account_type == "Customer":
            with st.expander("New to SupportIQ? Create a customer account"):
                with st.form("registration_form"):
                    full_name = st.text_input("Full name", key="register_full_name")
                    new_email = st.text_input("Email address", key="register_email")
                    new_password = st.text_input(
                        "Create password", type="password", key="register_password"
                    )
                    confirm_password = st.text_input(
                        "Confirm password", type="password", key="register_confirm_password"
                    )
                    register_submitted = st.form_submit_button(
                        "Create Account", use_container_width=True
                    )

                if register_submitted:
                    name = full_name.strip()
                    clean_email = new_email.strip()

                    if not name or not clean_email or not new_password:
                        st.warning("Please complete all fields.")
                    elif (
                        "@" not in clean_email
                        or "." not in clean_email.rsplit("@", 1)[-1]
                    ):
                        st.warning("Please enter a valid email address.")
                    elif len(new_password) < 8:
                        st.warning("Your password must contain at least 8 characters.")
                    elif new_password != confirm_password:
                        st.warning("The passwords do not match.")
                    else:
                        try:
                            success, message = register_customer(
                                name, clean_email, new_password
                            )
                            if success:
                                st.success(
                                    "Account created! Sign in using the Customer option."
                                )
                            else:
                                st.error(message)
                        except Exception:
                            logger.exception("Customer registration failed")
                            st.error(
                                "Registration could not be completed. Please try again."
                            )
        else:
            st.info(
                "Support-agent accounts are created by an administrator. "
                "There is no public agent-registration option."
            )

        st.caption("SupportIQ · Customer support ticket management")

    st.stop()


# ---------------------------------------------------------------------
# Role validation and sidebar navigation
# ---------------------------------------------------------------------

user = st.session_state.user
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
    render_hero()
    st.title("Customer Dashboard")
    st.write(f"Welcome back, {user['full_name']}.")

    try:
        render_metrics(get_customer_ticket_counts(user["user_id"]))
        st.subheader("Your Recent Tickets")
        recent = get_customer_tickets(user["user_id"])[:5]
        render_ticket_rows(recent, customer_view=True)
    except Exception:
        logger.exception("Customer dashboard failed")
        st.error("Your dashboard could not be loaded.")

    st.subheader("Need help with something?")
    st.write("Create a support request and track its progress.")
    action1, action2 = st.columns(2)
    with action1:
        st.button(
            "＋ Submit a Complaint",
            key="dashboard_submit",
            type="primary",
            on_click=go_to,
            args=("Submit Complaint",),
            use_container_width=True,
        )
    with action2:
        st.button(
            "View All My Tickets",
            key="dashboard_tickets",
            on_click=go_to,
            args=("My Tickets",),
            use_container_width=True,
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
    render_hero()

    st.markdown(
        """
        <style>
        .agent-heading {
            font-size: 30px;
            font-weight: 750;
            color: #172554;
            margin-bottom: 2px;
        }
        .agent-subheading {
            color: #64748b;
            font-size: 14px;
            margin-bottom: 22px;
        }
        .priority-note {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 13px 16px;
            margin: 8px 0 16px 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="agent-heading">Agent Dashboard</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="agent-subheading">Welcome back, '
        f'{user["full_name"]}. Here is what needs your attention.</div>',
        unsafe_allow_html=True,
    )

    try:
        # Dashboard metrics from the database

        st.markdown("### Priority Tickets")
        st.markdown(
            '<div class="priority-note">'
            'Review high-priority complaints first. '
            'Resolved tickets are excluded from this active queue.'
            '</div>',
            unsafe_allow_html=True,
        )

        # Fetch tickets and keep unresolved tickets only
        all_tickets = get_agent_tickets()

        queue = [
            ticket for ticket in all_tickets
            if ticket.get("status") != "Resolved"
        ]

        # High > Medium > Low; New > In Progress; oldest first
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

        # Summary counts from the retrieved tickets
        high_count = sum(
            1 for ticket in queue
            if str(ticket.get("predicted_priority") or "").lower() == "high"
        )
        medium_count = sum(
            1 for ticket in queue
            if str(ticket.get("predicted_priority") or "").lower() == "medium"
        )
        new_count = sum(
            1 for ticket in queue if ticket.get("status") == "New"
        )
        progress_count = sum(
            1 for ticket in queue if ticket.get("status") == "In Progress"
        )

        metric_cols = st.columns(4)

        with metric_cols[0]:
            st.metric("High Priority", high_count)

        with metric_cols[1]:
            st.metric("New Tickets", new_count)

        with metric_cols[2]:
            st.metric("In Progress", progress_count)

        with metric_cols[3]:
            st.metric("Medium Priority", medium_count)

        # Priority filters for the dashboard preview
        filter_col, search_col = st.columns([1, 2])

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
                or search_term in str(
                    ticket.get("customer_name") or ""
                ).lower()
                or search_term in str(ticket.get("id") or "").lower()
            ]

        st.markdown("#### Active ticket queue")

        if filtered_queue:
            # Show the five most important matching tickets
            for ticket in filtered_queue[:5]:
                with st.container(border=True):
                    subject_col, priority_col, status_col, action_col = (
                        st.columns([4, 1.2, 1.5, 1.2])
                    )

                    with subject_col:
                        st.markdown(
                            f"**#{ticket['id']} — "
                            f"{ticket.get('subject') or 'Untitled ticket'}**"
                        )
                        st.caption(
                            f"Customer: "
                            f"{ticket.get('customer_name') or 'Unknown'}"
                        )
                        st.caption(
                            f"Category: "
                            f"{ticket.get('predicted_category') or 'Unclassified'}"
                        )

                    with priority_col:
                        priority = str(
                            ticket.get("predicted_priority") or "Unknown"
                        ).title()

                        if priority == "High":
                            st.error(f"🔴 {priority}")
                        elif priority == "Medium":
                            st.warning(f"🟠 {priority}")
                        else:
                            st.info(f"⚪ {priority}")

                    with status_col:
                        st.write("**Status**")
                        st.write(ticket.get("status", "Unknown"))

                    with action_col:
                        st.write("")
                        st.button(
                            "Review",
                            key=f"dashboard_review_{ticket['id']}",
                            on_click=open_ticket,
                            args=(ticket["id"],),
                            use_container_width=True,
                        )

            if len(filtered_queue) > 5:
                st.caption(
                    f"Showing 5 of {len(filtered_queue)} matching active "
                    "tickets. Open All Tickets to see the complete queue."
                )
        else:
            st.success("No active tickets match these filters.")

        st.divider()

        # Actual AI/model-related information from the existing tickets
        st.markdown("### AI Ticket Insights")

        insight_col1, insight_col2 = st.columns(2)

        with insight_col1:
            categories = {}
            for ticket in queue:
                category = (
                    ticket.get("predicted_category") or "Unclassified"
                )
                categories[category] = categories.get(category, 0) + 1

            if categories:
                common_category = max(
                    categories, key=categories.get
                )
                st.info(
                    f"**Most common category**\n\n"
                    f"{common_category} ({categories[common_category]} "
                    f"active tickets)"
                )
            else:
                st.info("No active tickets available for category insights.")

        with insight_col2:
            st.warning(
                f"**High-priority workload**\n\n"
                f"{high_count} high-priority active ticket(s) "
                "should be reviewed first."
            )

    except Exception:
        logger.exception("Agent dashboard failed")
        st.error("The agent dashboard could not be loaded.")

    st.button(
        "Open All Tickets",
        key="agent_dashboard_all",
        type="primary",
        on_click=go_to,
        args=("All Tickets",),
        use_container_width=True,
    )





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
