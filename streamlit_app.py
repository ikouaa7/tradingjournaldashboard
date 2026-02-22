import streamlit as st
from supabase import create_client
from datetime import date
import calendar

# =====================
# SUPABASE
# =====================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =====================
# SESSION
# =====================
if "user" not in st.session_state:
    st.session_state.user = None

# =====================
# AUTH
# =====================
def sign_up(email, password):
    try:
        supabase.auth.sign_up({"email": email, "password": password})
        st.success("Account aangemaakt")
    except:
        st.error("Signup mislukt")

def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        st.session_state.user = res.user
        st.rerun()
    except:
        st.error("Login mislukt")

def logout():
    st.session_state.user = None
    st.rerun()

# =====================
# =====================
# SAVE TRADE (WORKING)
# =====================
def save_trade(trade_date, pnl, trades):
    if st.session_state.user is None:
        st.error("Niet ingelogd")
        return

    user_id = st.session_state.user.id

    data = {
        "user_id": user_id,
        "date": trade_date.isoformat(),
        "pnl": float(pnl),
        "trades": int(trades)
    }

    res = supabase.table("daily_trades").upsert(data).execute()

    if res.data:
        st.success("Opgeslagen ✅")
    else:
        st.error("Opslaan mislukt")
        st.write(res)


# =====================
# LOAD TRADES (WORKING)
# =====================
def load_trades():
    if st.session_state.user is None:
        return {}

    user_id = st.session_state.user.id

    res = supabase.table("daily_trades").select("*").eq(
        "user_id", user_id
    ).execute()

    trades = {}
    for row in res.data:
        trades[row["date"]] = row

    return trades

# =====================
# LOGIN SCREEN
# =====================
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

# =====================
# APP
# =====================
st.title("Trading Journal Dashboard")

if st.button("Uitloggen"):
    logout()

YEAR = 2026
trades_data = load_trades()

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
.neutral {background-color:#374151;}
.month-title {font-size:22px; margin-top:25px;}
</style>
""", unsafe_allow_html=True)

# =====================
# CALENDAR
# =====================
for month in range(1, 13):

    st.markdown(
        f"<div class='month-title'>{calendar.month_name[month]} {YEAR}</div>",
        unsafe_allow_html=True
    )

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
                d = date(YEAR, month, day)

                key = str(d)

                if key in trades_data:
                    pnl = trades_data[key]["pnl"]
                    trades_count = trades_data[key]["trades"]

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

                # EDIT
                with cols[i].expander("Edit"):
                    pnl_input = st.number_input(
                        "P/L $",
                        key=f"pnl_{key}"
                    )
                    trades_input = st.number_input(
                        "Trades",
                        step=1,
                        key=f"tr_{key}"
                    )

                    if st.button("Save", key=f"save_{key}"):
                        save_trade(d, pnl_input, trades_input)
                        st.rerun()
