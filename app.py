import datetime
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="LNB Lineups", layout="wide")

def dur_to_sec(val):
    if pd.isna(val):
        return 0
    if isinstance(val, datetime.time):
        # Caso o Excel interprete MM:SS como HH:MM (ex: 05:28 -> 5h 28m)
        if val.hour > 0 and val.second == 0:
            return val.hour * 60 + val.minute
        return val.hour * 3600 + val.minute * 60 + val.second
    try:
        parts = [int(x) for x in str(val).strip().split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 60 + parts[1] if parts[2] == 0 else parts[0] * 3600 + parts[1] * 60 + parts[2]
    except Exception:
        return 0
    return 0

def sec_to_dur(sec):
    sec = int(round(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"

@st.cache_data
def load_data():
    df = pd.read_excel("NBB19 LineuPs.xlsx")
    df["DUR_S"] = df["D"].apply(dur_to_sec)
    return df

df = load_data()

st.title("LNB Lineups")

# --- BARRA LATERAL (FILTROS) ---
st.sidebar.header("Filtros")

times = sorted(df["Time"].dropna().unique())
time_sel = st.sidebar.selectbox("Equipe", times)

df_time = df[df["Time"] == time_sel]

jogos = sorted(df_time["ID"].dropna().unique())
jogos_sel = st.sidebar.multiselect("Jogos", jogos, default=jogos)

quartos = sorted(df_time["P"].dropna().unique())
quartos_sel = st.sidebar.multiselect("Períodos", quartos, default=quartos)

modo_exibicao = st.sidebar.radio(
    "Modo de Exibição",
    ["Totais", "Por 100 Posses"]
)

min_posses = st.sidebar.slider("Mínimo de Posses", min_value=1, max_value=100, value=1)

# --- FILTRAGEM ---
df_filtrado = df_time[
    (df_time["ID"].isin(jogos_sel)) &
    (df_time["P"].isin(quartos_sel))
]

if df_filtrado.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

# --- AGREGAÇÃO POR KINTETO (SOMA DOS CONTADORES BRUTOS) ---
cols_soma = [
    "DUR_S", "PTS", "2PM", "2PA", "3PM", "3PA", "FTM", "FTA",
    "OR", "DR", "REB", "AST", "TO", "STL", "BLK", "PF",
    "PTS_A", "2PM_A", "2PA_A", "3PM_A", "3PA_A", "FTM_A", "FTA_A",
    "OR_A", "DR_A", "REB_A", "AST_A", "TO_A", "STL_A", "BLK_A", "PF_A", "+/-"
]

agg = df_filtrado.groupby("Kinteto", as_index=False)[cols_soma].sum()

# --- CÁLCULO DE POSSES NO MONTANTE TOTAL ---
fga_raw = agg["2PA"] + agg["3PA"]
fga_a_raw = agg["2PA_A"] + agg["3PA_A"]

posses_off = fga_raw - agg["OR"] + agg["TO"] + (0.44 * agg["FTA"])
posses_def = fga_a_raw - agg["OR_A"] + agg["TO_A"] + (0.44 * agg["FTA_A"])

agg["POSSES"] = ((posses_off + posses_def) / 2).round().astype(int)

# Filtro de amostra mínima
agg = agg[agg["POSSES"] >= min_posses].copy()
pos_div = agg["POSSES"].replace(0, 1)
fga = agg["2PA"] + agg["3PA"]

# --- MÉTRICAS AVANÇADAS E PERCENTUAIS ---
agg["MIN"] = agg["DUR_S"].apply(sec_to_dur)
agg["ORtg"] = ((agg["PTS"] / pos_div) * 100).round(1)
agg["DRtg"] = ((agg["PTS_A"] / pos_div) * 100).round(1)
agg["NetRtg"] = (agg["ORtg"] - agg["DRtg"]).round(1)

agg["FG%"] = np.where(fga > 0, ((agg["2PM"] + agg["3PM"]) / fga * 100).round(1), 0.0)
agg["3P%"] = np.where(agg["3PA"] > 0, (agg["3PM"] / agg["3PA"] * 100).round(1), 0.0)
agg["eFG%"] = np.where(fga > 0, ((agg["2PM"] + 1.5 * agg["3PM"]) / fga * 100).round(1), 0.0)
agg["ORB%"] = np.where((agg["OR"] + agg["DR_A"]) > 0, (agg["OR"] / (agg["OR"] + agg["DR_A"]) * 100).round(1), 0.0)
agg["DRB%"] = np.where((agg["DR"] + agg["OR_A"]) > 0, (agg["DR"] / (agg["DR"] + agg["OR_A"]) * 100).round(1), 0.0)

# --- MONTAGEM DA TABELA FINAL ---
if modo_exibicao == "Totais":
    tabela = agg[[
        "Kinteto", "MIN", "POSSES", "+/-", "ORtg", "DRtg", "NetRtg",
        "PTS", "PTS_A", "FG%", "3P%", "eFG%", "REB", "REB_A", "ORB%", "DRB%",
        "AST", "TO", "STL", "BLK", "PF"
    ]].sort_values(by="DUR_S", ascending=False)
else:
    tabela = pd.DataFrame({
        "Kinteto": agg["Kinteto"],
        "MIN": agg["MIN"],
        "POSSES": agg["POSSES"],
        "ORtg": agg["ORtg"],
        "DRtg": agg["DRtg"],
        "NetRtg": agg["NetRtg"],
        "PTS/100": agg["ORtg"],
        "PTS_A/100": agg["DRtg"],
        "FG%": agg["FG%"],
        "3P%": agg["3P%"],
        "eFG%": agg["eFG%"],
        "REB/100": ((agg["REB"] / pos_div) * 100).round(1),
        "REB_A/100": ((agg["REB_A"] / pos_div) * 100).round(1),
        "ORB%": agg["ORB%"],
        "DRB%": agg["DRB%"],
        "AST/100": ((agg["AST"] / pos_div) * 100).round(1),
        "TO/100": ((agg["TO"] / pos_div) * 100).round(1),
        "STL/100": ((agg["STL"] / pos_div) * 100).round(1),
        "BLK/100": ((agg["BLK"] / pos_div) * 100).round(1),
    }).loc[agg.sort_values(by="POSSES", ascending=False).index]

st.dataframe(tabela, use_container_width=True, hide_index=True)