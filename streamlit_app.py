import streamlit as st
from supabase import create_client
from datetime import date, datetime
import calendar

# =========================
# SUPABASE CONNECT
# =========================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# SESSION STATE
# =========================
if "user" not in st.session_state:
    st.session_state.user = None

# =========================
# AUTH FUNCTIONS
# =========================
def sign_up(email, password):
    try:
        supabase.auth.sign_up({"email": email, "password": password})
        st.success("Account aangemaakt! Je kunt nu inloggen.")
    except Exception as e:
        st.error("Signup mislukt")

def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        st.session_state.user = res.user
        st.rerun()
    except:
        st.error("Login mislukt")

def logout():
    st.session_state.user = None
    st.rerun()

# =========================
# LOGIN UI
# =========================
if st.session_state.user is None:
    st.title("Trading Journal Dashboard")

    tab1, tab2 = st.tabs(["Login", "Account maken"])

    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Wachtwoord", type="password")
        if st.button("Login"):
            login(email, password)

    with tab2:
        email2 = st.text_input("Email ", key="signup_email")
        password2 = st.text_input("Wachtwoord ", type="password", key="signup_pw")
        if st.button("Account maken"):
            sign_up(email2, password2)

    st.stop()

# =========================
# USER INFO
# =========================
user_id = st.session_state.user.id

st.title("Trading Journal Dashboard")

if st.button("Uitloggen"):
    logout()

# =========================
# LOAD TRADES FROM DB
# =========================
def load_trades():
    data = supabase.table("daily_trades").select("*").eq("user_id", user_id).execute()
    trades = {}
    for row in data.data:
        trades[row["trade_date"]] = row
    return trades

def save_trade(date, pnl, trades):
    user = supabase.auth.get_user()
    
    if user is None or user.user is None:
        st.error("Niet ingelogd")
        return
    
    user_id = user.user.id

    supabase.table("daily_trades").insert({
        "user_id": user_id,
        "date": date,
        "pnl": pnl,
        "trades": trades
    }).execute()
trades_data = load_trades()

# =========================
# YEAR SELECT
# =========================
YEAR = 2026

# =========================
# CALENDAR STYLE
# =========================
st.markdown("""
<style>
.day-box {
    padding:10px;
    border-radius:8px;
    height:90px;
    color:white;
    font-size:14px;
}
.win {background-color:#16a34a;}
.loss {background-color:#dc2626;}
.neutral {background-color:#1f2937;}
.month-title {font-size:22px; margin-top:25px;}
</style>
""", unsafe_allow_html=True)

# =========================
# CALENDAR GRID
# =========================
for month in range(1, 13):

    st.markdown(f"<div class='month-title'>{calendar.month_name[month]} {YEAR}</div>", unsafe_allow_html=True)

    cal = calendar.monthcalendar(YEAR, month)

    cols = st.columns(7)
    for i, d in enumerate(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]):
        cols[i].markdown(f"**{d}**")

    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                cols[i].write("")
            else:
                d = date(YEAR, month, day).isoformat()

                if d in trades_data:
                    pnl = trades_data[d]["pnl"]
                    trades_count = trades_data[d]["trades"]

                    if pnl > 0:
                        cls = "win"
                    elif pnl < 0:
                        cls = "loss"
                    else:
                        cls = "neutral"

                    cols[i].markdown(
                        f"<div class='day-box {cls}'>{day}<br>${pnl}<br>{trades_count} trades</div>",
                        unsafe_allow_html=True
                    )
                else:
                    cols[i].markdown(
                        f"<div class='day-box neutral'>{day}</div>",
                        unsafe_allow_html=True
                    )

                # INPUT
                with cols[i].expander("Edit"):
                    pnl_input = st.number_input("P/L $", key=f"pnl_{d}")
                    trades_input = st.number_input("Trades", step=1, key=f"tr_{d}")

                    if st.button("Save", key=f"save_{d}"):
                        save_trade(d, pnl_input, trades_input)
                        st.rerun()
