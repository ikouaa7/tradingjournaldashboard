import streamlit as st
from supabase import create_client, Client
from datetime import date, datetime
import calendar

# =====================
# SUPABASE CONNECTIE
# =====================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =====================
# LOGIN CHECK
# =====================
user = supabase.auth.get_user()

if not user or not user.user:
    st.warning("Login vereist")
    st.stop()

user_id = user.user.id

# =====================
# HEADER
# =====================
col1, col2 = st.columns([6,1])

with col1:
    st.title("Trading Journal Dashboard")

with col2:
    if st.button("Logout"):
        supabase.auth.sign_out()
        st.rerun()

# =====================
# MAAND NAVIGATIE
# =====================
if "month" not in st.session_state:
    today = date.today()
    st.session_state.month = today.month
    st.session_state.year = today.year

col_prev, col_title, col_next = st.columns([1,4,1])

with col_prev:
    if st.button("⬅ Previous"):
        if st.session_state.month == 1:
            st.session_state.month = 12
            st.session_state.year -= 1
        else:
            st.session_state.month -= 1
        st.rerun()

with col_title:
    st.subheader(f"{calendar.month_name[st.session_state.month]} {st.session_state.year}")

with col_next:
    if st.button("Next ➡"):
        if st.session_state.month == 12:
            st.session_state.month = 1
            st.session_state.year += 1
        else:
            st.session_state.month += 1
        st.rerun()

# =====================
# DATA LADEN
# =====================
def load_trades():
    res = supabase.table("daily_trades") \
        .select("*") \
        .eq("user_id", user_id) \
        .execute()

    trades = {}
    if res.data:
        for row in res.data:
            trades[row["date"]] = row
    return trades

# =====================
# SAVE TRADE
# =====================
def save_trade(trade_date, pnl, trades):
    data = {
        "user_id": user_id,
        "date": str(trade_date),
        "pnl": float(pnl),
        "trades": int(trades)
    }

    res = supabase.table("daily_trades").upsert(data).execute()

    if res.data:
        st.success("Opgeslagen ✅")
    else:
        st.error("Opslaan mislukt")

# =====================
# KALENDER
# =====================
trades_data = load_trades()

year = st.session_state.year
month = st.session_state.month

month_days = calendar.monthcalendar(year, month)

weekdays = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
cols = st.columns(7)
for i, d in enumerate(weekdays):
    cols[i].markdown(f"**{d}**")

for week in month_days:
    cols = st.columns(7)
    for i, day in enumerate(week):
        if day == 0:
            continue

        day_date = date(year, month, day)
        key = str(day_date)

        pnl = None
        trades = None

        if key in trades_data:
            pnl = trades_data[key]["pnl"]
            trades = trades_data[key]["trades"]

        color = "#2f3542"
        text = f"{day}"

        if pnl is not None:
            if pnl > 0:
                color = "#2ecc71"
            elif pnl < 0:
                color = "#e74c3c"

            text = f"{day}\n${pnl}\n{trades} trades"

        cols[i].markdown(
            f"""
            <div style="
                background:{color};
                border-radius:8px;
                padding:10px;
                text-align:center;
                color:white;
                min-height:80px;
                white-space:pre-line;
            ">
            {text}
            </div>
            """,
            unsafe_allow_html=True
        )

        if cols[i].button("Edit", key=f"edit_{key}"):
            st.session_state.edit_date = day_date

# =====================
# EDIT POPUP
# =====================
if "edit_date" in st.session_state:
    d = st.session_state.edit_date

    st.divider()
    st.subheader(f"Edit {d}")

    pnl_input = st.number_input("P/L $", value=0.0)
    trades_input = st.number_input("Trades", value=0)

    if st.button("Save"):
        save_trade(d, pnl_input, trades_input)
        del st.session_state.edit_date
        st.rerun()
