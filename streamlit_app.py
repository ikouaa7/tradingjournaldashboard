import streamlit as st

st.set_page_config(page_title="Trading Journal Dashboard", page_icon="📈", layout="wide")

st.title("📈 Trading Journal Dashboard")
st.write("App draait! Voeg hier straks je trades, stats en grafieken toe.")

with st.form("trade_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        date = st.date_input("Datum")
        symbol = st.text_input("Symbol (bv. NAS100)")
    with col2:
        direction = st.selectbox("Richting", ["Long", "Short"])
        result = st.selectbox("Resultaat", ["Win", "Loss", "BE"])
    with col3:
        pnl = st.number_input("P/L (€)", value=0.0, step=1.0)

    note = st.text_area("Notities")
    submitted = st.form_submit_button("Opslaan")

if submitted:
    st.success("Opgeslagen (demo). Later koppelen we dit aan een database/CSV.")
