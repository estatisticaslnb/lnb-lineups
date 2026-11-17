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
    if isinstance(val, datetime.time):
        return val.hour * 60 + val.minute
    if isinstance(val, datetime.timedelta):
        total_min = int(round(val.total_seconds() / 60))
        return total_min
    if isinstance(val, (int, float)):
        total_min = int(round(val * 1440))
        return total_min
    try:
        s_val = str(val).strip()
        if " " in s_val:
            s_val = s_val.split(" ")[-1]
        parts = [int(float(x)) for x in s_val.split(":")]
        if len(parts) >= 2:
            return parts[0] * 60 + parts[1]
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
    "2 - Duplas": 2,
    "1 - Individual": 1
}
tamanho_label = st.sidebar.selectbox("Tamanho da Combinação", list(opcoes_tamanho.keys()))
tamanho_comb = opcoes_tamanho[tamanho_label]

todos_atletas = sorted({
    p.strip()
    for k in df_time["Kinteto"].dropna()
    for p in str(k).split("/")
    if p.strip()
})
atletas_sel = st.sidebar.multiselect("Filtrar por Atleta(s) em Quadra", todos_atletas)

jogos = sorted(df_time["ID"].dropna().unique())
jogos_sel = st.sidebar.multiselect("Jogos", jogos, default=jogos)

quartos = sorted(df_time["P"].dropna().unique())
quartos_sel = st.sidebar.multiselect("Períodos", quartos, default=quartos)

modo_exibicao = st.sidebar.radio(
    "Modo de Exibição",
    ["Total", "Média", "Por 100 Posses", "Advanced"]
)

col_f1, col_f2 = st.sidebar.columns(2)
min_jogos = col_f1.number_input("Mín. Jogos", min_value=1, value=1, step=1)
min_posses = col_f2.number_input("Mín. Posses", min_value=0, value=0, step=5)

# --- FILTRAGEM INICIAL ---
df_filtrado = df_time[
    (df_time["ID"].isin(jogos_sel)) &
    (df_time["P"].isin(quartos_sel))
].copy()

if df_filtrado.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

# --- EXPANSÃO DE COMBINAÇÕES ---
def gerar_combinacoes(kinteto_str, r):
    if pd.isna(kinteto_str):
        return []
    jogadores = sorted({p.strip() for p in str(kinteto_str).split("/") if p.strip()})
    if not jogadores:
        return []
    if r == 5:
        return [" / ".join(jogadores)]
    if len(jogadores) < r:
        return []
    return [" / ".join(comb) for comb in combinations(jogadores, r)]

df_filtrado["Lineup"] = df_filtrado["Kinteto"].apply(lambda x: gerar_combinacoes(x, tamanho_comb))
df_exp = df_filtrado.explode("Lineup")
df_exp = df_exp[df_exp["Lineup"].notna() & (df_exp["Lineup"] != "")]

if atletas_sel:
    mask = df_exp["Lineup"].apply(
        lambda l: all(a in [p.strip() for p in str(l).split("/")] for a in atletas_sel)
    )
    df_exp = df_exp[mask]

if df_exp.empty:
    st.warning("Nenhuma combinação encontrada para os filtros selecionados.")
    st.stop()

# --- AGREGAÇÃO POR LINEUP ---
cols_soma = [
    "DUR_S", "PTS", "2PM", "2PA", "3PM", "3PA", "FTM", "FTA",
    "OR", "DR", "REB", "AST", "TO", "STL", "BLK", "PF",
    "PTS_A", "2PM_A", "2PA_A", "3PM_A", "3PA_A", "FTM_A", "FTA_A",
    "OR_A", "DR_A", "REB_A", "AST_A", "TO_A", "STL_A", "BLK_A", "PF_A", "+/-"
]

agg = df_exp.groupby("Lineup", as_index=False).agg(
    J=("ID", "nunique"),
    **{c: (c, "sum") for c in cols_soma}
)

# --- CÁLCULO OFICIAL DE POSSES (FÓRMULA LNB: COEFICIENTE 4/9) ---
fga = agg["2PA"] + agg["3PA"]
fgm = agg["2PM"] + agg["3PM"]
fga_a = agg["2PA_A"] + agg["3PA_A"]
fgm_a = agg["2PM_A"] + agg["3PM_A"]

posses_off = fga + (4 / 9) * agg["FTA"] + agg["TO"] - agg["OR"]
posses_def = fga_a + (4 / 9) * agg["FTA_A"] + agg["TO_A"] - agg["OR_A"]
agg["POSSES"] = ((posses_off + posses_def) / 2).round().astype(int)

# --- FILTROS DE AMOSTRA MÍNIMA ---
agg = agg[(agg["J"] >= min_jogos) & (agg["POSSES"] >= min_posses)].copy()

if agg.empty:
    st.warning("Nenhum lineup atingiu o mínimo de jogos/posses selecionado.")
    st.stop()

agg = agg.sort_values(by="DUR_S", ascending=False).reset_index(drop=True)

# --- VARIÁVEIS BASE ---
fga = agg["2PA"] + agg["3PA"]
fgm = agg["2PM"] + agg["3PM"]
fga_a = agg["2PA_A"] + agg["3PA_A"]
fgm_a = agg["2PM_A"] + agg["3PM_A"]

ef = (agg["PTS"] + agg["REB"] + agg["AST"] + agg["STL"] + agg["BLK"]) - (
    (fga - fgm) + (agg["FTA"] - agg["FTM"]) + agg["TO"]
)
ef_a = (agg["PTS_A"] + agg["REB_A"] + agg["AST_A"] + agg["STL_A"] + agg["BLK_A"]) - (
    (fga_a - fgm_a) + (agg["FTA_A"] - agg["FTM_A"]) + agg["TO_A"]
)

pcts = {
    "FG%": np.where(fga > 0, (fgm / fga * 100).round(1), 0.0),
    "2P%": np.where(agg["2PA"] > 0, (agg["2PM"] / agg["2PA"] * 100).round(1), 0.0),
    "3P%": np.where(agg["3PA"] > 0, (agg["3PM"] / agg["3PA"] * 100).round(1), 0.0),
    "LL%": np.where(agg["FTA"] > 0, (agg["FTM"] / agg["FTA"] * 100).round(1), 0.0),
    "Opp FG%": np.where(fga_a > 0, (fgm_a / fga_a * 100).round(1), 0.0),
    "Opp 2P%": np.where(agg["2PA_A"] > 0, (agg["2PM_A"] / agg["2PA_A"] * 100).round(1), 0.0),
    "Opp 3P%": np.where(agg["3PA_A"] > 0, (agg["3PM_A"] / agg["3PA_A"] * 100).round(1), 0.0),
    "Opp LL%": np.where(agg["FTA_A"] > 0, (agg["FTM_A"] / agg["FTA_A"] * 100).round(1), 0.0),
}

def montar_box_score_agrupado(head_dict, fator_div, fator_mult, casas_decimais):
    def calc(serie):
        res = (serie / fator_div) * fator_mult
        return res.round(0).astype(int) if casas_decimais == 0 else res.round(casas_decimais)

    dados = {}
    for col_nome, valores in head_dict.items():
        dados[("", col_nome)] = valores

    # Bloco Ofensivas
    dados[("Ofensivas", "PTS")] = calc(agg["PTS"])
    dados[("Ofensivas", "FGM")] = calc(fgm)
    dados[("Ofensivas", "FGA")] = calc(fga)
    dados[("Ofensivas", "FG%")] = pcts["FG%"]
    dados[("Ofensivas", "2PC")] = calc(agg["2PM"])
    dados[("Ofensivas", "2PT")] = calc(agg["2PA"])
    dados[("Ofensivas", "2P%")] = pcts["2P%"]
    dados[("Ofensivas", "3PC")] = calc(agg["3PM"])
    dados[("Ofensivas", "3PT")] = calc(agg["3PA"])
    dados[("Ofensivas", "3P%")] = pcts["3P%"]
    dados[("Ofensivas", "LLC")] = calc(agg["FTM"])
    dados[("Ofensivas", "LLT")] = calc(agg["FTA"])
    dados[("Ofensivas", "LL%")] = pcts["LL%"]
    dados[("Ofensivas", "RO")] = calc(agg["OR"])
    dados[("Ofensivas", "RD")] = calc(agg["DR"])
    dados[("Ofensivas", "REB")] = calc(agg["REB"])
    dados[("Ofensivas", "AST")] = calc(agg["AST"])
    dados[("Ofensivas", "TOV")] = calc(agg["TO"])
    dados[("Ofensivas", "STL")] = calc(agg["STL"])
    dados[("Ofensivas", "BLK")] = calc(agg["BLK"])
    dados[("Ofensivas", "F")] = calc(agg["PF"])
    dados[("Ofensivas", "EF")] = calc(ef)

    # Coluna Neutra (+/-)
    dados[("", "+/-")] = calc(agg["+/-"])

    # Bloco Defensivas
    dados[("Defensivas", "PTS")] = calc(agg["PTS_A"])
    dados[("Defensivas", "FGM")] = calc(fgm_a)
    dados[("Defensivas", "FGA")] = calc(fga_a)
    dados[("Defensivas", "FG%")] = pcts["Opp FG%"]
    dados[("Defensivas", "2PC")] = calc(agg["2PM_A"])
    dados[("Defensivas", "2PT")] = calc(agg["2PA_A"])
    dados[("Defensivas", "2P%")] = pcts["Opp 2P%"]
    dados[("Defensivas", "3PC")] = calc(agg["3PM_A"])
    dados[("Defensivas", "3PT")] = calc(agg["3PA_A"])
    dados[("Defensivas", "3P%")] = pcts["Opp 3P%"]
    dados[("Defensivas", "LLC")] = calc(agg["FTM_A"])
    dados[("Defensivas", "LLT")] = calc(agg["FTA_A"])
    dados[("Defensivas", "LL%")] = pcts["Opp LL%"]
    dados[("Defensivas", "RO")] = calc(agg["OR_A"])
    dados[("Defensivas", "RD")] = calc(agg["DR_A"])
    dados[("Defensivas", "REB")] = calc(agg["REB_A"])
    dados[("Defensivas", "AST")] = calc(agg["AST_A"])
    dados[("Defensivas", "TOV")] = calc(agg["TO_A"])
    dados[("Defensivas", "STL")] = calc(agg["STL_A"])
    dados[("Defensivas", "BLK")] = calc(agg["BLK_A"])
    dados[("Defensivas", "F")] = calc(agg["PF_A"])
    dados[("Defensivas", "EF")] = calc(ef_a)

    df_out = pd.DataFrame(dados)
    df_out.columns = pd.MultiIndex.from_tuples(df_out.columns)
    return df_out

# --- MONTAGEM DA TABELA CONFORME O MODO ---
if modo_exibicao == "Total":
    head = {
        "Minutos": agg["DUR_S"].apply(sec_to_dur),
        "J": agg["J"],
    }
    tabela = montar_box_score_agrupado(head, 1, 1, 0)
    fmt_decimais = 0

elif modo_exibicao == "Média":
    j_div = agg["J"].replace(0, 1)
    head = {
        "Minutos": (agg["DUR_S"] / j_div).apply(sec_to_dur),
        "J": agg["J"],
    }
    tabela = montar_box_score_agrupado(head, j_div, 1, 1)
    fmt_decimais = 1

elif modo_exibicao == "Por 100 Posses":
    pos_div = agg["POSSES"].replace(0, 1)
    head = {
        "Minutos": agg["DUR_S"].apply(sec_to_dur),
        "Posses ~": agg["POSSES"],
    }
    tabela = montar_box_score_agrupado(head, pos_div, 100, 1)
    fmt_decimais = 1

elif modo_exibicao == "Advanced":
    pos_div = agg["POSSES"].replace(0, 1)
    min_float = agg["DUR_S"] / 60.0

    efg_off = np.where(fga > 0, ((fgm + 0.5 * agg["3PM"]) / fga * 100).round(1), 0.0)
    tov_denom_off = fga + (4 / 9) * agg["FTA"] + agg["TO"]
    tov_off = np.where(tov_denom_off > 0, (agg["TO"] / tov_denom_off * 100).round(1), 0.0)
    orb_denom_off = agg["OR"] + agg["DR_A"]
    orb_off = np.where(orb_denom_off > 0, (agg["OR"] / orb_denom_off * 100).round(1), 0.0)
    fta_rate_off = np.where(fga > 0, (agg["FTA"] / fga * 100).round(1), 0.0)
    off_rtg = ((agg["PTS"] / pos_div) * 100).round(1)

    efg_def = np.where(fga_a > 0, ((fgm_a + 0.5 * agg["3PM_A"]) / fga_a * 100).round(1), 0.0)
    tov_denom_def = fga_a + (4 / 9) * agg["FTA_A"] + agg["TO_A"]
    tov_def = np.where(tov_denom_def > 0, (agg["TO_A"] / tov_denom_def * 100).round(1), 0.0)
    orb_denom_def = agg["OR_A"] + agg["DR"]
    orb_def = np.where(orb_denom_def > 0, (agg["OR_A"] / orb_denom_def * 100).round(1), 0.0)
    fta_rate_def = np.where(fga_a > 0, (agg["FTA_A"] / fga_a * 100).round(1), 0.0)
    def_rtg = ((agg["PTS_A"] / pos_div) * 100).round(1)

    pace = np.where(min_float > 0, ((agg["POSSES"] / min_float) * 40).round(1), 0.0)

    dados_adv = {
        ("", "Minutos"): agg["DUR_S"].apply(sec_to_dur),
        ("", "Posses ~"): agg["POSSES"],
        ("", "PACE"): pace,
        ("Ofensivas", "eFG%"): efg_off,
        ("Ofensivas", "TOV%"): tov_off,
        ("Ofensivas", "ORB%"): orb_off,
        ("Ofensivas", "FTA Rate"): fta_rate_off,
        ("Ofensivas", "OFFRTG"): off_rtg,
        ("Defensivas", "eFG%"): efg_def,
        ("Defensivas", "TOV%"): tov_def,
        ("Defensivas", "ORB%"): orb_def,
        ("Defensivas", "FTA Rate"): fta_rate_def,
        ("Defensivas", "DEFRTG"): def_rtg,
        ("", "NETRTG"): (off_rtg - def_rtg).round(1),
    }
    tabela = pd.DataFrame(dados_adv)
    tabela.columns = pd.MultiIndex.from_tuples(tabela.columns)
    fmt_decimais = 1

# --- CONGELA A COLUNA LINEUP COMO ÍNDICE SIMPLES E CENTRALIZA DADOS ---
tabela.index = pd.Index(agg["Lineup"].values, name="Lineup")

formatos = {}
for col in tabela.columns:
    sub_nome = col[1]
    if sub_nome in ["J", "Posses ~"]:
        formatos[col] = "{:.0f}"
    elif "%" in sub_nome or sub_nome in ["PACE", "FTA Rate", "OFFRTG", "DEFRTG", "NETRTG"]:
        formatos[col] = "{:.1f}"
    elif sub_nome != "Minutos":
        formatos[col] = "{:.0f}" if fmt_decimais == 0 else "{:.1f}"

tabela_estilizada = (
    tabela.style
    .format(formatos)
    .set_properties(**{"text-align": "center"})
    .set_table_styles([{"selector": "th", "props": [("text-align", "center")]}])
)

st.dataframe(tabela_estilizada, use_container_width=True)
