import streamlit as st
from supabase import create_client
from datetime import date, datetime
import calendar
import pandas as pd

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Trading Journal Dashboard", layout="wide")

YEAR = 2026
YEAR_START = date(YEAR, 1, 1)
YEAR_END = date(YEAR, 12, 31)

# =========================
# SUPABASE
# =========================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def set_session_if_exists():
    """Restore supabase session from Streamlit session_state (so RLS/auth works)."""
    sess = st.session_state.get("sb_session")
    if not sess:
        return
    try:
        supabase.auth.set_session(sess["access_token"], sess["refresh_token"])
    except Exception:
        # If set_session isn't available in your supabase-py version, ignore.
        pass


def get_user_id():
    """Return logged-in user id or None."""
    try:
        u = supabase.auth.get_user()
        if u and getattr(u, "user", None) and getattr(u.user, "id", None):
            return u.user.id
    except Exception:
        pass
    return None


def login_ui():
    st.title("Trading Journal Dashboard")

    tab1, tab2 = st.tabs(["Login", "Account maken"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Wachtwoord", type="password", key="login_pw")
        if st.button("Login"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                # Store tokens so we keep login on refresh
                st.session_state["sb_session"] = {
                    "access_token": res.session.access_token,
                    "refresh_token": res.session.refresh_token,
                }
                st.success("Ingelogd ✅")
                st.rerun()
            except Exception as e:
                st.error("Login mislukt ❌")
                st.write(e)

    with tab2:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Wachtwoord", type="password", key="signup_pw")
        if st.button("Account maken"):
            try:
                supabase.auth.sign_up({"email": email, "password": password})
                st.success("Account aangemaakt ✅ (check je mail als confirm aan staat)")
            except Exception as e:
                st.error("Signup mislukt ❌")
                st.write(e)


def logout_button():
    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("Logout"):
            try:
                supabase.auth.sign_out()
            except Exception:
                pass
            st.session_state.pop("sb_session", None)
            st.session_state.pop("current_month", None)
            st.session_state.pop("edit_date", None)
            st.rerun()
    with col2:
        st.caption("Je data is per account (Supabase).")


# =========================
# DATA: LOAD/SAVE
# =========================
def load_trades_for_range(user_id: str, start_d: date, end_d: date) -> dict:
    """Returns dict keyed by ISO date string: {'2026-02-19': {'pnl':..., 'trades':...}}"""
    res = (
        supabase.table("daily_trades")
        .select("date,pnl,trades")
        .eq("user_id", user_id)
        .gte("date", start_d.isoformat())
        .lte("date", end_d.isoformat())
        .execute()
    )

    out = {}
    for r in (res.data or []):
        # r["date"] is 'YYYY-MM-DD'
        out[str(r["date"])] = {"pnl": float(r.get("pnl", 0) or 0), "trades": int(r.get("trades", 0) or 0)}
    return out


def save_trade(user_id: str, trade_date: date, pnl: float, trades: int):
    """Upsert a trade row for (user_id, date). Works with unique(user_id,date)."""
    data = {
        "user_id": user_id,
        "date": trade_date.isoformat(),
        "pnl": float(pnl),
        "trades": int(trades),
    }

    # Try upsert with on_conflict, else fallback update->insert
    try:
        res = supabase.table("daily_trades").upsert(data, on_conflict="user_id,date").execute()
        return res
    except Exception:
        # fallback: try update first
        try:
            u = (
                supabase.table("daily_trades")
                .update({"pnl": float(pnl), "trades": int(trades)})
                .eq("user_id", user_id)
                .eq("date", trade_date.isoformat())
                .execute()
            )
            if u.data:
                return u
        except Exception:
            pass
        # else insert
        return supabase.table("daily_trades").insert(data).execute()


# =========================
# UI: MONTH NAV (ONLY BY BUTTONS)
# =========================
def month_start_end(y: int, m: int):
    start = date(y, m, 1)
    last_day = calendar.monthrange(y, m)[1]
    end = date(y, m, last_day)
    return start, end


def init_current_month():
    """Default = current real month if in YEAR else Jan YEAR."""
    today = date.today()
    if today.year == YEAR:
        st.session_state["current_month"] = (YEAR, today.month)
    else:
        st.session_state["current_month"] = (YEAR, 1)


def clamp_month(y: int, m: int):
    if y < YEAR:
        return (YEAR, 1)
    if y > YEAR:
        return (YEAR, 12)
    if m < 1:
        return (YEAR, 1)
    if m > 12:
        return (YEAR, 12)
    return (y, m)


def prev_month(y: int, m: int):
    if m == 1:
        return (y, 1)
    return (y, m - 1)


def next_month(y: int, m: int):
    if m == 12:
        return (y, 12)
    return (y, m + 1)


# =========================
# UI: CALENDAR GRID
# =========================
def pnl_color(pnl: float):
    if pnl > 0:
        return "#16a34a"  # green
    if pnl < 0:
        return "#dc2626"  # red
    return "#374151"      # gray


def render_month_calendar(user_id: str, y: int, m: int):
    start_d, end_d = month_start_end(y, m)
    trades = load_trades_for_range(user_id, start_d, end_d)

    cal = calendar.Calendar(firstweekday=0)  # Monday=0
    weeks = cal.monthdayscalendar(y, m)

    # Header row Mon..Sun
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    head_cols = st.columns(7)
    for i, dname in enumerate(days):
        head_cols[i].markdown(f"**{dname}**")

    st.write("")

    for w in weeks:
        cols = st.columns(7)
        for i, day_num in enumerate(w):
            with cols[i]:
                if day_num == 0:
                    st.write("")
                    continue

                d = date(y, m, day_num)
                key = d.isoformat()
                info = trades.get(key)
                pnl = info["pnl"] if info else 0.0
                tcount = info["trades"] if info else 0

                bg = pnl_color(pnl) if info else "#374151"

                # Card
                st.markdown(
                    f"""
                    <div style="
                        background:{bg};
                        border-radius:10px;
                        padding:10px;
                        height:90px;
                        color:white;
                        font-weight:600;
                        display:flex;
                        flex-direction:column;
                        justify-content:space-between;
                    ">
                      <div style="font-size:14px;">{day_num}</div>
                      <div style="font-size:14px;">
                        {"$" + str(round(pnl, 2)) if info else ""}
                      </div>
                      <div style="font-size:12px; opacity:0.9;">
                        {str(tcount) + " trades" if info else ""}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if st.button("Edit", key=f"edit-{key}"):
                    st.session_state["edit_date"] = d

    # Edit panel (below calendar)
    edit_d = st.session_state.get("edit_date")
    if edit_d and edit_d.year == y and edit_d.month == m:
        st.divider()
        st.subheader(f"Edit: {edit_d.isoformat()}")

        existing = trades.get(edit_d.isoformat(), {"pnl": 0.0, "trades": 0})
        pnl_input = st.number_input("P/L ($)", value=float(existing["pnl"]), step=1.0, key=f"pnl-{edit_d}")
        trades_input = st.number_input("Trades", value=int(existing["trades"]), step=1, min_value=0, key=f"tr-{edit_d}")

        c1, c2 = st.columns([1, 5])
        with c1:
            if st.button("Save", key=f"save-{edit_d}"):
                try:
                    save_trade(user_id, edit_d, pnl_input, trades_input)
                    st.success("Opgeslagen ✅")
                    st.session_state["edit_date"] = None
                    st.rerun()
                except Exception as e:
                    st.error("Opslaan mislukt ❌")
                    st.write(e)
        with c2:
            if st.button("Cancel", key=f"cancel-{edit_d}"):
                st.session_state["edit_date"] = None
                st.rerun()


# =========================
# STATS + EQUITY
# =========================
def render_stats(user_id: str, y: int, m: int):
    m_start, m_end = month_start_end(y, m)
    trades_m = load_trades_for_range(user_id, m_start, m_end)
    trades_y = load_trades_for_range(user_id, YEAR_START, YEAR_END)

    def stats_from_dict(dct: dict):
        pnls = [v["pnl"] for v in dct.values()]
        trades = [v["trades"] for v in dct.values()]
        if not pnls:
            return {
                "days": 0, "total": 0.0, "avg_day": 0.0,
                "wins": 0, "losses": 0, "winrate": 0.0,
                "total_trades": 0
            }
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p < 0)
        days = len(pnls)
        total = sum(pnls)
        avg_day = total / days if days else 0.0
        winrate = (wins / (wins + losses) * 100) if (wins + losses) else 0.0
        total_trades = sum(trades)
        return {
            "days": days, "total": total, "avg_day": avg_day,
            "wins": wins, "losses": losses, "winrate": winrate,
            "total_trades": total_trades
        }

    sm = stats_from_dict(trades_m)
    sy = stats_from_dict(trades_y)

    st.subheader("Stats (selected month)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total P/L", f"${sm['total']:.2f}")
    c2.metric("Days logged", f"{sm['days']}")
    c3.metric("Winrate", f"{sm['winrate']:.1f}%")
    c4.metric("Trades", f"{sm['total_trades']}")

    st.subheader("Stats (Year 2026)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total P/L", f"${sy['total']:.2f}")
    c2.metric("Days logged", f"{sy['days']}")
    c3.metric("Winrate", f"{sy['winrate']:.1f}%")
    c4.metric("Trades", f"{sy['total_trades']}")

    # Simple bar chart by day for month
    if trades_m:
        df = pd.DataFrame(
            [{"date": k, "pnl": v["pnl"], "trades": v["trades"]} for k, v in trades_m.items()]
        )
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        st.subheader("Daily P/L (month)")
        st.bar_chart(df.set_index("date")[["pnl"]])


def render_equity(user_id: str):
    trades_y = load_trades_for_range(user_id, YEAR_START, YEAR_END)
    st.subheader("Equity curve (2026)")

    if not trades_y:
        st.info("Nog geen data in 2026.")
        return

    df = pd.DataFrame(
        [{"date": k, "pnl": v["pnl"], "trades": v["trades"]} for k, v in trades_y.items()]
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df["equity"] = df["pnl"].cumsum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total P/L", f"${df['pnl'].sum():.2f}")
    c2.metric("Max day", f"${df['pnl'].max():.2f}")
    c3.metric("Min day", f"${df['pnl'].min():.2f}")

    st.line_chart(df.set_index("date")[["equity"]])
    st.subheader("Daily P/L (year)")
    st.bar_chart(df.set_index("date")[["pnl"]])


# =========================
# MAIN
# =========================
set_session_if_exists()
uid = get_user_id()

if not uid:
    login_ui()
    st.stop()

logout_button()

if "current_month" not in st.session_state:
    init_current_month()

y, m = st.session_state["current_month"]
y, m = clamp_month(y, m)
st.session_state["current_month"] = (y, m)

# Month navigation (ONLY with buttons)
title_col, prev_col, next_col = st.columns([6, 1, 1])

with title_col:
    st.title("Trading Journal Dashboard")
    st.caption("Alleen 2026. Gebruik Previous/Next om te navigeren.")

with prev_col:
    if st.button("Previous month", disabled=(m == 1)):
        st.session_state["current_month"] = prev_month(y, m)
        st.session_state["edit_date"] = None
        st.rerun()

with next_col:
    if st.button("Next month", disabled=(m == 12)):
        st.session_state["current_month"] = next_month(y, m)
        st.session_state["edit_date"] = None
        st.rerun()

st.subheader(f"{calendar.month_name[m]} {y}")

tabA, tabB, tabC = st.tabs(["Kalender", "Stats", "Equity curve"])

with tabA:
    render_month_calendar(uid, y, m)

with tabB:
    render_stats(uid, y, m)

with tabC:
    render_equity(uid)
