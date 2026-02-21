import calendar
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st
from dateutil.relativedelta import relativedelta
from supabase import create_client


# ----------------------------
# Config
# ----------------------------
APP_TITLE = "Trading Journal Dashboard"
MIN_DATE = date(2024, 1, 1)
MAX_DATE = date(2026, 12, 31)

st.set_page_config(page_title=APP_TITLE, page_icon="📈", layout="wide")


# ----------------------------
# Styles (mooier, meer “dashboard” vibe)
# ----------------------------
st.markdown(
    """
<style>
/* algemene spacing */
.block-container { padding-top: 2rem; padding-bottom: 2rem; }
/* tabs wat strakker */
.stTabs [data-baseweb="tab-list"] { gap: 14px; }
.stTabs [data-baseweb="tab"] { padding: 8px 12px; border-radius: 10px; }
/* cards */
.card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 14px 14px;
}
.card h3 { margin: 0; font-size: 14px; color: #6b7280; font-weight: 600; }
.card .big { font-size: 26px; font-weight: 800; margin-top: 6px; }
.muted { color:#6b7280; }
.kpi-grid { display:grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
@media (max-width: 1000px){ .kpi-grid { grid-template-columns: repeat(2, 1fr);} }
.calendar-head { display:grid; grid-template-columns: repeat(7, 1fr); gap: 10px; margin-bottom: 10px;}
.calendar-head div { text-align:center; font-weight:700; color:#6b7280; }
.calendar-grid { display:grid; grid-template-columns: repeat(7, 1fr); gap: 10px; }
.daybox {
  border-radius: 14px;
  padding: 10px;
  min-height: 92px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
}
.daybox .top { display:flex; justify-content:space-between; align-items:center; }
.daybox .d { font-weight:800; }
.daybox .dow { color:#6b7280; font-size: 12px; }
.daybox .pnl { margin-top: 8px; font-weight:800; font-size: 16px; }
.daybox .tr { margin-top: 2px; color:#6b7280; font-size: 12px; }
.daybox.win { background:#dcfce7; border-color:#16a34a; }
.daybox.loss{ background:#fee2e2; border-color:#dc2626; }
.daybox.be  { background:#e0f2fe; border-color:#0284c7; }
.daybox.dim { opacity: .35; }
.smallbtn button { border-radius: 12px !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ----------------------------
# Supabase
# ----------------------------
@st.cache_resource
def sb():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])


def get_session():
    return st.session_state.get("sb_session")


def set_session(session):
    st.session_state["sb_session"] = session


def do_logout():
    try:
        sb().auth.sign_out()
    except Exception:
        pass
    st.session_state.pop("sb_session", None)
    st.rerun()


# ----------------------------
# Auth UI
# ----------------------------
def auth_screen():
    st.title(APP_TITLE)
    t1, t2 = st.tabs(["Login", "Account maken"])

    with t1:
        email = st.text_input("Email", key="login_email")
        pw = st.text_input("Wachtwoord", type="password", key="login_pw")
        if st.button("Login", use_container_width=True):
            try:
                res = sb().auth.sign_in_with_password({"email": email, "password": pw})
                set_session(res.session)
                st.success("Ingelogd!")
                st.rerun()
            except Exception as e:
                st.error(f"Login mislukt: {e}")

    with t2:
        email2 = st.text_input("Email", key="signup_email")
        pw2 = st.text_input("Wachtwoord", type="password", key="signup_pw")
        if st.button("Account maken", use_container_width=True):
            try:
                sb().auth.sign_up({"email": email2, "password": pw2})
                st.success("Account gemaakt! Ga nu naar Login.")
            except Exception as e:
                st.error(f"Signup mislukt: {e}")


# ----------------------------
# Helpers
# ----------------------------
def clamp(d: date, lo: date, hi: date) -> date:
    return max(lo, min(d, hi))


def month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def month_end(d: date) -> date:
    return (month_start(d) + relativedelta(months=1)) - timedelta(days=1)


def fmt_usd(x: float) -> str:
    return f"${x:,.2f}"


# ----------------------------
# Data access
# ----------------------------
def fetch_rows(user_id: str, start_d: date, end_d: date) -> pd.DataFrame:
    res = (
        sb()
        .table("daily_trades")
        .select("trade_date,trades_count,profit_usd,loss_usd")
        .eq("user_id", user_id)
        .gte("trade_date", start_d.isoformat())
        .lte("trade_date", end_d.isoformat())
        .execute()
    )
    rows = res.data or []
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["trade_date", "trades_count", "profit_usd", "loss_usd", "net_usd"])

    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["trades_count"] = df["trades_count"].astype(int)
    df["profit_usd"] = df["profit_usd"].astype(float)
    df["loss_usd"] = df["loss_usd"].astype(float)
    df["net_usd"] = df["profit_usd"] - df["loss_usd"]
    return df.sort_values("trade_date")


def upsert_day(user_id: str, d: date, trades_count: int, profit: float, loss: float):
    payload = {
        "user_id": user_id,
        "trade_date": d.isoformat(),
        "trades_count": int(trades_count),
        "profit_usd": float(profit),
        "loss_usd": float(loss),
        "updated_at": datetime.utcnow().isoformat(),
    }
    sb().table("daily_trades").upsert(payload, on_conflict="user_id,trade_date").execute()


# ----------------------------
# Calendar UI
# ----------------------------
def day_class(net):
    if net is None:
        return ""
    if net > 0:
        return "win"
    if net < 0:
        return "loss"
    return "be"


def render_calendar(user_id: str, cursor_month: date):
    # fetch only this month
    ms = month_start(cursor_month)
    me = clamp(month_end(cursor_month), MIN_DATE, MAX_DATE)
    df = fetch_rows(user_id, ms, me)
    mp = {r.trade_date: r for r in df.itertuples(index=False)}

    # header
    st.markdown(
        "<div class='calendar-head'>" +
        "".join([f"<div>{d}</div>" for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]]) +
        "</div>",
        unsafe_allow_html=True
    )

    # weeks
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(cursor_month.year, cursor_month.month)

    # grid
    st.markdown("<div class='calendar-grid'>", unsafe_allow_html=True)
    for w in weeks:
        for d in w:
            in_month = (d.month == cursor_month.month)
            row = mp.get(d)
            net = None if row is None else float(row.net_usd)
            trades = "" if row is None else f"{int(row.trades_count)} trades"
            pnl = "" if row is None else fmt_usd(float(row.net_usd))

            cls = f"daybox {day_class(net)}"
            if not in_month:
                cls += " dim"

            # clickable: use a button placed above the box
            # (Streamlit doesn't allow clicking raw HTML safely, so we do a small button)
            btn_disabled = not in_month or d < MIN_DATE or d > MAX_DATE
            btn_label = f"{d.day:02d}"

            st.markdown("<div>", unsafe_allow_html=True)
            colbtn = st.container()
            with colbtn:
                if st.button(btn_label, key=f"pick_{d.isoformat()}", disabled=btn_disabled, use_container_width=True):
                    st.session_state["selected_date"] = d
                    st.rerun()

            st.markdown(
                f"""
                <div class="{cls}">
                  <div class="top">
                    <div>
                      <div class="d">{d.day:02d}</div>
                      <div class="dow">{calendar.day_abbr[d.weekday()]}</div>
                    </div>
                  </div>
                  <div class="pnl">{pnl}</div>
                  <div class="tr">{trades}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    return df


# ----------------------------
# KPIs + charts
# ----------------------------
def compute_kpis(df: pd.DataFrame):
    if df.empty:
        return {
            "net": 0.0, "profit": 0.0, "loss": 0.0, "days": 0,
            "win_days": 0, "winrate": 0.0, "pf": 0.0
        }
    profit = float(df["profit_usd"].sum())
    loss = float(df["loss_usd"].sum())
    net = float(df["net_usd"].sum())
    days = int(df["trade_date"].nunique())
    win_days = int((df["net_usd"] > 0).sum())
    winrate = (win_days / days) if days else 0.0
    pf = (profit / loss) if loss > 0 else (float("inf") if profit > 0 else 0.0)
    return {
        "net": net, "profit": profit, "loss": loss, "days": days,
        "win_days": win_days, "winrate": winrate, "pf": pf
    }


def render_kpi_cards(k):
    pf_txt = "∞" if k["pf"] == float("inf") else f"{k['pf']:.2f}"
    st.markdown(
        f"""
<div class="kpi-grid">
  <div class="card"><h3>Net P/L</h3><div class="big">{fmt_usd(k["net"])}</div></div>
  <div class="card"><h3>Total Profit</h3><div class="big">{fmt_usd(k["profit"])}</div></div>
  <div class="card"><h3>Total Loss</h3><div class="big">{fmt_usd(k["loss"])}</div></div>
  <div class="card"><h3>Winrate / Profit Factor</h3><div class="big">{k["winrate"]*100:.0f}% • {pf_txt}</div></div>
</div>
""",
        unsafe_allow_html=True
    )


def render_charts(df: pd.DataFrame):
    st.subheader("📉 Grafieken")
    if df.empty:
        st.info("Nog geen data in deze periode.")
        return

    dfc = df.copy().sort_values("trade_date")
    dfc["equity"] = dfc["net_usd"].cumsum()
    chart_df = dfc.set_index("trade_date")[["net_usd", "equity"]]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Daily Net P/L**")
        st.line_chart(chart_df["net_usd"])
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Equity Curve**")
        st.line_chart(chart_df["equity"])
        st.markdown("</div>", unsafe_allow_html=True)


def render_recent_days(df: pd.DataFrame):
    st.subheader("🕒 Recent days")
    if df.empty:
        st.info("Nog geen dagen opgeslagen.")
        return

    recent = df.sort_values("trade_date", ascending=False).head(6)
    cols = st.columns(3)
    for i, row in enumerate(recent.itertuples(index=False)):
        net = float(row.net_usd)
        cls = "win" if net > 0 else ("loss" if net < 0 else "be")
        with cols[i % 3]:
            st.markdown(
                f"""
                <div class="card">
                  <div class="muted">{row.trade_date}</div>
                  <div style="font-size:22px;font-weight:900;margin-top:4px;">{fmt_usd(net)}</div>
                  <div class="muted">{int(row.trades_count)} trades • Profit {fmt_usd(float(row.profit_usd))} • Loss {fmt_usd(float(row.loss_usd))}</div>
                </div>
                """,
                unsafe_allow_html=True
            )


# ----------------------------
# Main
# ----------------------------
session = get_session()
if session is None:
    auth_screen()
    st.stop()

user_id = session.user.id
user_email = session.user.email or ""

# Sidebar navigation (TraderVue-ish)
with st.sidebar:
    st.markdown("## 📌 Menu")
    page = st.radio("Pagina", ["Dashboard", "Calendar"], label_visibility="collapsed")
    st.divider()
    st.caption(f"Ingelogd als: {user_email}")
    if st.button("Logout"):
        do_logout()

st.title("📈 Trading Journal Dashboard")

# Range filter (voor stats + charts)
with st.container():
    left, mid, right = st.columns([2, 3, 2])
    with left:
        range_mode = st.selectbox("Periode", ["30 days", "60 days", "90 days", "Custom"], index=0)
    with mid:
        if range_mode == "Custom":
            c1, c2 = st.columns(2)
            with c1:
                start_d = st.date_input("Start", value=clamp(date.today() - timedelta(days=30), MIN_DATE, MAX_DATE))
            with c2:
                end_d = st.date_input("Eind", value=clamp(date.today(), MIN_DATE, MAX_DATE))
        else:
            days = int(range_mode.split()[0])
            end_d = clamp(date.today(), MIN_DATE, MAX_DATE)
            start_d = clamp(end_d - timedelta(days=days), MIN_DATE, MAX_DATE)
        # fix order
        if start_d > end_d:
            start_d, end_d = end_d, start_d
    with right:
        st.markdown(f"<div class='card'><b>Periode</b><br><span class='muted'>{start_d} → {end_d}</span></div>", unsafe_allow_html=True)

# Month navigation (kalender)
if "month_cursor" not in st.session_state:
    st.session_state["month_cursor"] = month_start(clamp(date.today(), MIN_DATE, MAX_DATE))

mc = clamp(st.session_state["month_cursor"], month_start(MIN_DATE), month_start(MAX_DATE))
st.session_state["month_cursor"] = mc

nav1, nav2, nav3, nav4 = st.columns([1, 2, 1, 2])
with nav1:
    if st.button("◀ Prev month", use_container_width=True):
        st.session_state["month_cursor"] = clamp(month_start(mc - relativedelta(months=1)), month_start(MIN_DATE), month_start(MAX_DATE))
        st.rerun()
with nav2:
    st.markdown(f"### {calendar.month_name[mc.month]}, {mc.year}")
with nav3:
    if st.button("Next month ▶", use_container_width=True):
        st.session_state["month_cursor"] = clamp(month_start(mc + relativedelta(months=1)), month_start(MIN_DATE), month_start(MAX_DATE))
        st.rerun()
with nav4:
    if st.button("Today", use_container_width=True):
        st.session_state["month_cursor"] = month_start(clamp(date.today(), MIN_DATE, MAX_DATE))
        st.session_state["selected_date"] = clamp(date.today(), MIN_DATE, MAX_DATE)
        st.rerun()

st.divider()

# Fetch data for period KPIs/charts
df_period = fetch_rows(user_id, start_d, end_d)
kpis = compute_kpis(df_period)
render_kpi_cards(kpis)

st.divider()

# Calendar (month view)
st.subheader("🗓️ Calendar")
df_month = render_calendar(user_id, st.session_state["month_cursor"])

# Day editor
st.divider()
sel = st.session_state.get("selected_date", clamp(date.today(), MIN_DATE, MAX_DATE))
sel = clamp(sel, MIN_DATE, MAX_DATE)
st.subheader(f"✍️ Dag invoer — {sel.isoformat()}")

# load defaults from month df (or fetch single day if outside month)
row = df_month[df_month["trade_date"] == sel]
if row.empty:
    df_one = fetch_rows(user_id, sel, sel)
    row = df_one

default_trades = int(row["trades_count"].iloc[0]) if not row.empty else 0
default_profit = float(row["profit_usd"].iloc[0]) if not row.empty else 0.0
default_loss = float(row["loss_usd"].iloc[0]) if not row.empty else 0.0

with st.form("day_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        trades_count = st.number_input("Aantal trades", min_value=0, step=1, value=default_trades)
    with c2:
        profit = st.number_input("Profit (USD)", min_value=0.0, step=1.0, value=default_profit, format="%.2f")
    with c3:
        loss = st.number_input("Loss (USD)", min_value=0.0, step=1.0, value=default_loss, format="%.2f")

    net = profit - loss
    if net > 0:
        st.success(f"Net: {fmt_usd(net)} (winst → groen)")
    elif net < 0:
        st.error(f"Net: {fmt_usd(net)} (verlies → rood)")
    else:
        st.info(f"Net: {fmt_usd(net)} (break-even)")

    if st.form_submit_button("Opslaan", use_container_width=True):
        upsert_day(user_id, sel, trades_count, profit, loss)
        st.success("Opgeslagen!")
        st.rerun()

# Recent + Charts
st.divider()
render_recent_days(df_period)
st.divider()
render_charts(df_period)
