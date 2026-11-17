import os
import datetime
from itertools import combinations
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="LNB Lineups", layout="wide")

def dur_to_sec(val):
    if pd.isna(val):
        return 0
    if isinstance(val, datetime.timedelta):
        total = int(val.total_seconds())
        # Se o Excel interpretou MM:SS como HH:MM (ex: 5h30m = 19800s), converte de volta para min:seg
        if total >= 3600 and total % 60 == 0:
            return total // 60
        return total
    if isinstance(val, datetime.time):
        if val.hour > 0 and val.second == 0:
            return val.hour * 60 + val.minute
        return val.minute * 60 + val.second
    try:
        s_val = str(val).strip()
        if " " in s_val:
            s_val = s_val.split(" ")[-1]
        parts = [int(float(x)) for x in s_val.split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            if parts[0] == 0:
                return parts[1] * 60 + parts[2]
            if parts[2] == 0:
                return parts[0] * 60 + parts[1]
            return parts[1] * 60 + parts[2]
    except Exception:
        return 0
    return 0

def sec_to_dur(sec):
    sec = int(round(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"

@st.cache_data
def load_data():
    arquivos = os.listdir(".")
    planilha = next((f for f in arquivos if f.lower().endswith((".xlsx", ".xls", ".csv"))), None)
    
    if not planilha:
        st.error(f"Nenhuma planilha encontrada no repositório. Arquivos atuais: {arquivos}")
        st.stop()
        
    if planilha.lower().endswith(".csv"):
        df = pd.read_csv(planilha)
    else:
        df = pd.read_excel(planilha)
        
    df["DUR_S"] = df["D"].apply(dur_to_sec)
    return df

df = load_data()

st.title("LNB Lineups")

# --- BARRA LATERAL (FILTROS) ---
st.sidebar.header("Filtros")

times = sorted(df["Time"].dropna().unique())
time_sel = st.sidebar.selectbox("Equipe", times)

df_time = df[df["Time"] == time_sel].copy()

opcoes_tamanho = {
    "5 - Quintetos": 5,
    "4 - Quartetos": 4,
    "3 - Trios": 3,
    "2 -
