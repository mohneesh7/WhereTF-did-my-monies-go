"""Streamlit frontend – interactive dashboard + chat for the money manager."""

import calendar
from datetime import datetime

import httpx
import streamlit as st

# ── Config ───────────────────────────────────────────────────────

API_BASE = "http://localhost:8000/api"

st.set_page_config(
    page_title="WhereTF Did My Monies Go 💸",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Helpers ──────────────────────────────────────────────────────


def api_get(path: str, params: dict | None = None):
    """GET from the FastAPI backend."""
    try:
        r = httpx.get(f"{API_BASE}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, json_data: dict | None = None, files: dict | None = None):
    """POST to the FastAPI backend."""
    try:
        r = httpx.post(f"{API_BASE}{path}", json=json_data, files=files, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_delete(path: str):
    """DELETE against the FastAPI backend."""
    try:
        r = httpx.delete(f"{API_BASE}{path}", timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def format_inr(amount: float) -> str:
    """Format as INR currency."""
    sign = "-" if amount < 0 else ""
    return f"{sign}₹{abs(amount):,.2f}"


# ── Sidebar Navigation ──────────────────────────────────────────

st.sidebar.title("💸 Money Manager")
page = st.sidebar.radio(
    "Navigate",
    ["📊 Dashboard", "🔍 Transactions", "📤 Upload", "💬 Chat"],
    label_visibility="collapsed",
)

now = datetime.now()
selected_year = st.sidebar.number_input("Year", min_value=2020, max_value=2030, value=now.year)
selected_month = st.sidebar.selectbox(
    "Month",
    range(1, 13),
    index=now.month - 1,
    format_func=lambda m: calendar.month_name[m],
)

st.sidebar.markdown("---")
health = api_get("/health")
if health:
    st.sidebar.caption(f"🟢 API: {health['status']}  |  DB: {health['db']}  |  LLM: {health['llm']}")
else:
    st.sidebar.caption("🔴 API unreachable – is FastAPI running?")


# ── Page: Dashboard ──────────────────────────────────────────────

if page == "📊 Dashboard":
    st.title(f"📊 Dashboard – {calendar.month_name[selected_month]} {selected_year}")

    # Cashflow summary
    cashflow = api_get(f"/analytics/cashflow/{selected_year}/{selected_month}")
    if cashflow:
        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Income", format_inr(cashflow["income"]))
        col2.metric("💸 Expenses", format_inr(cashflow["expenses"]))
        col3.metric(
            "📈 Net",
            format_inr(cashflow["net"]),
            delta=f"{format_inr(cashflow['net'])}",
            delta_color="normal" if cashflow["net"] >= 0 else "inverse",
        )

    st.markdown("---")

    col_left, col_right = st.columns(2)

    # Category breakdown
    with col_left:
        st.subheader("🏷️ Spending by Category")
        categories = api_get(f"/analytics/categories/{selected_year}/{selected_month}")
        if categories and len(categories) > 0:
            import pandas as pd

            df = pd.DataFrame(categories)
            df["total_amount"] = df["total_amount"].abs()
            st.bar_chart(df.set_index("category")["total_amount"])
        else:
            st.info("No spending data for this month.")

    # Top merchants
    with col_right:
        st.subheader("🏪 Top Merchants")
        merchants = api_get(f"/analytics/merchants/{selected_year}/{selected_month}")
        if merchants and len(merchants) > 0:
            import pandas as pd

            df = pd.DataFrame(merchants)
            df["total_spend"] = df["total_spend"].abs()
            st.bar_chart(df.set_index("merchant")["total_spend"])
        else:
            st.info("No merchant data for this month.")


# ── Page: Transactions ───────────────────────────────────────────

elif page == "🔍 Transactions":
    st.title("🔍 Transactions")

    search = st.text_input("🔎 Search by description or merchant")

    txns = api_get("/transactions")
    if txns:
        import pandas as pd

        df = pd.DataFrame(txns)
        if not df.empty:
            if search:
                mask = (
                    df["description"].str.contains(search, case=False, na=False)
                    | df["merchant"].fillna("").str.contains(search, case=False, na=False)
                )
                df = df[mask]

            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp", ascending=False)

            # Display
            st.dataframe(
                df[["timestamp", "description", "merchant", "category", "amount", "currency"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "timestamp": st.column_config.DatetimeColumn("Date", format="YYYY-MM-DD"),
                    "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
                },
            )
            st.caption(f"Showing {len(df)} transactions")
        else:
            st.info("No transactions found.")
    else:
        st.info("No transactions found. Upload a statement first!")

    # ── Manage / Delete Transactions ─────────────────────────────
    st.markdown("---")
    st.subheader("🗑️ Manage Transactions")

    col_del_n, col_del_all = st.columns(2)

    with col_del_n:
        st.markdown("**Delete last N transactions**")
        n_to_delete = st.number_input(
            "Number of recent transactions to delete",
            min_value=1, max_value=100000, value=100, step=50,
        )
        if st.button(f"🗑️ Delete last {n_to_delete}", key="delete_last_n"):
            result = api_delete(f"/transactions/last/{n_to_delete}")
            if result:
                st.success(f"✅ Deleted {result['deleted']} transactions.")
                st.rerun()

    with col_del_all:
        st.markdown("**Delete ALL transactions**")
        st.warning("⚠️ This cannot be undone!")
        confirm = st.checkbox("I understand, delete everything", key="confirm_delete_all")
        if st.button("🗑️ Delete All Transactions", key="delete_all", disabled=not confirm, type="primary"):
            result = api_delete("/transactions")
            if result:
                st.success(f"✅ Deleted {result['deleted']} transactions.")
                st.rerun()


# ── Page: Upload ─────────────────────────────────────────────────

elif page == "📤 Upload":
    st.title("📤 Upload Bank Statement")
    st.markdown("Upload a **PDF** bank statement to extract and categorize transactions.")

    uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])
    account_id = st.text_input("Account ID (optional – leave blank to auto-generate)")
    pdf_password = st.text_input("PDF Password (if encrypted)", type="password")

    if uploaded_file and st.button("🚀 Process Statement", type="primary"):
        with st.spinner("Processing... (extracting → LLM parsing → validating → saving)"):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
            params = {}
            if account_id:
                params["account_id"] = account_id
            if pdf_password:
                params["password"] = pdf_password

            # Pass params as query strings
            query_str = "&".join(f"{k}={v}" for k, v in params.items())
            endpoint = f"/ingest?{query_str}" if query_str else "/ingest"
            result = api_post(endpoint, files=files)

            if result:
                st.success(
                    f"✅ Ingested **{result.get('valid_count', 0)}** transactions "
                    f"from {result.get('source', 'file')}"
                )
                if result.get("rejected_count", 0) > 0:
                    with st.expander(f"⚠️ {result['rejected_count']} rejected rows"):
                        st.json(result["rejected_rows"])
                st.balloons()


# ── Page: Chat ───────────────────────────────────────────────────

elif page == "💬 Chat":
    st.title("💬 Chat with Your Finances")
    st.markdown("Ask questions about your spending, savings, and financial patterns.")

    # Session state for chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask me about your finances..."):
        # Add user message
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get agent response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = api_post("/chat", json_data={"message": prompt})
                if response:
                    reply = response.get("reply", "Sorry, I couldn't process that.")
                else:
                    reply = "⚠️ Could not reach the API. Make sure the FastAPI server is running."

                st.markdown(reply)
                st.session_state.chat_history.append({"role": "assistant", "content": reply})
