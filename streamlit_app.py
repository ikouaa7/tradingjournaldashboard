import calendar
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

import pandas as pd
import streamlit as st
from supabase import create_client


# ----------------------------
# Supabase
# ----------------------------
@st.cache_resource
def supabase_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)


def get_session():
    return st.session_state.get("sb_session")


def set_session(session):
    st.session_state["sb_session"] = session


def logout():
    sb = supabase_client()
    session = get_session()
    if session:
        try:
            sb.auth.sign_out()
        except Exception:
            pass
    st.session_state.pop("sb_session", None)
    st.rerun()


# ----------------------------
# Auth UI
# ----------------------------
def auth_block():
    st.title("Trading Journal Dashboard")

    tab1, tab2 = st.tabs(["Login", "Account maken"])
    sb = supabase_client()

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Wachtwoord", type="password", key="login_pw")
        if st.button("Login", use_container_width=True):
            try:
                res = sb.auth.sign_in_with_password({"email": email, "password": password})
                set_session(res.session)
                st.success("Ingelogd!")
                st.rerun()
            except Exception as e:
                st.error("Login mislukt")

    with tab2:
        email2 = st.text_input("Email", key="signup_email")
        password2 = st.text_input("Wachtwoord", type="password", key="signup_pw")
        if st.button("Account maken", use_container_width=True):
            try:
                sb.auth.sign_up({"email": email2, "password": password2})
                st.success("Account gemaakt — je kan nu inloggen")
            except Exception:
                st.error("Signup mislukt")


# ----------------------------
# Data
# ----------------------------
def fetch_month_rows(user_id: str, month_start: date, month_end: date) -> pd.DataFrame:
    sb = supabase_client()

    res = (
        sb.table("daily_trades")
        .select("trade_date,trades_count,profit_usd,loss_usd")
        .eq("user_id", user_id)
        .gte("trade_date", month_start.isoformat())
        .lte("trade_date", month_end.isoformat())
        .execute()
    )

    rows = res.data or []
    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame(columns=["trade_date", "trades_count", "profit_usd", "loss_usd", "net_usd"])

    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["profit_usd"] = df["profit_usd"].astype(float)
    df["loss_usd"] = df["loss_usd"].astype(float)
    df["trades_count"] = df["trades_count"].astype(int)
    df["net_usd"] = df["profit_usd"] - df["loss_usd"]

    return df


def upsert_day(user_id: str, d: date, trades_count: int, profit: float, loss: float):
    sb = supabase_client()

    payload = {
        "user_id": user_id,
        "trade_date": d.isoformat(),
        "trades_count": trades_count,
        "profit_usd": profit,
        "loss_usd": loss,
        "updated_at": datetime.utcnow().isoformat(),
    }

    sb.table("daily_trades").upsert(payload, on_conflict="user_id,trade_date").execute()


# ----------------------------
# Calendar
# ----------------------------
def day_style(net):
    if net is None:
        return "background:#f3f4f6;border:1px solid #e5e7eb;border-radius:12px;padding:10px;"
    if net > 0:
        return "background:#dcfce7;border:1px solid #16a34a;border-radius:12px;padding:10px;"
    if net < 0:
        return "background:#fee2e2;border:1px solid #dc2626;border-radius:12px;padding:10px;"
    return "background:#e0f2fe;border:1px solid #0284c7;border-radius:12px;padding:10px;"


def calendar_grid(year, month, df):
    stats = {row.trade_date: row for row in df.itertuples(index=False)}
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)

    for w in weeks:
        cols = st.columns(7)
        for i, d in enumerate(w):
            row = stats.get(d)
            net = None if row is None else row.net_usd

            with cols[i]:
                if st.button(f"{d.day}", key=f"day_{d}"):
                    st.session_state["selected_date"] = d

                style = day_style(net)
                pnl = "" if row is None else f"${row.net_usd:,.2f}"

                st.markdown(
                    f"<div style='{style}'>{pnl}</div>",
                    unsafe_allow_html=True
                )


# ----------------------------
# App
# ----------------------------
st.set_page_config(page_title="Trading Journal", layout="wide")

session = get_session()

if session is None:
    auth_block()
    st.stop()

user_id = session.user.id

st.title("Trading Journal Dashboard")

today = date.today()

if "month_cursor" not in st.session_state:
    st.session_state["month_cursor"] = date(today.year, today.month, 1)

month_start = st.session_state["month_cursor"]
month_end = (month_start + relativedelta(months=1)) - relativedelta(days=1)

df_month = fetch_month_rows(user_id, month_start, month_end)

calendar_grid(month_start.year, month_start.month, df_month)

selected = st.session_state.get("selected_date", today)

st.subheader(f"Dag invoer: {selected}")

row = df_month[df_month["trade_date"] == selected]

default_trades = int(row["trades_count"].iloc[0]) if not row.empty else 0
default_profit = float(row["profit_usd"].iloc[0]) if not row.empty else 0.0
default_loss = float(row["loss_usd"].iloc[0]) if not row.empty else 0.0

with st.form("day_form"):
    c1, c2, c3 = st.columns(3)

    with c1:
        trades_count = st.number_input("Aantal trades", min_value=0, value=default_trades)

    with c2:
        profit = st.number_input("Profit USD", min_value=0.0, value=default_profit)

    with c3:
        loss = st.number_input("Loss USD", min_value=0.0, value=default_loss)

    if st.form_submit_button("Opslaan"):
        upsert_day(user_id, selected, trades_count, profit, loss)
        st.success("Opgeslagen")
        st.rerun()

if st.button("Logout"):
    logout()
