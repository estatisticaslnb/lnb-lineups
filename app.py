import os
import re
import base64
import datetime
from itertools import combinations
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="LNB Lineups", layout="wide")


def exibir_banner(prefixo, tipo="header"):
    arquivos = os.listdir(".")
    img_path = next(
        (
            f for f in arquivos
            if f.lower().startswith(prefixo.lower())
            and f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ),
        None,
    )
    if not img_path:
        return

    ext = os.path.splitext(img_path)[1].lower().replace(".", "")
    if ext == "jpg":
        ext = "jpeg"

    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    borda = (
        "border-bottom: 1px solid #e2e8f0; margin-bottom: 16px;"
        if tipo == "header"
        else "border-top: 1px solid #e2e8f0; margin-top: 24px;"
    )

    st.markdown(
        f"""
        <div style="background-color: #ffffff; padding: 10px 16px; text-align: center; {borda}">
            <img src="data:image/{ext};base64,{b64}" style="max-height: 80px; max-width: 100%; height: auto; display: block; margin: 0 auto;" />
        </div>
        """,
        unsafe_allow_html=True,
    )


# --- CABEÇALHO COM IMAGEM ---
exibir_banner("headerNBB", tipo="header")


MAPA_TIMES = {
    "MIN": "MINAS",
    "PIN": "PINHEIROS",
    "MOG": "MOGI",
    "FLA": "FLAMENGO",
    "FRA": "FRANCA",
    "UFC": "UNIFACISA",
    "COR": "CORINTHIANS",
    "BRA": "BRASILIA",
    "BAU": "BAURU",
    "UCO": "UNICO",
    "CRU": "CRUZEIRO",
    "SJO": "SAO JOSE",
    "CAP": "PAULISTANO",
    "BOT": "BOTAFOGO",
    "OSA": "OSASCO",
    "PAT": "PATO",
    "BCE": "B. CEARENSE",
    "CAX": "CAXIAS",
}


def nome_completo_time(sigla):
    s = str(sigla).strip().upper()
    return MAPA_TIMES.get(s, str(sigla).strip())


def dur_to_sec(val):
    if pd.isna(val):
        return 0
    if isinstance(val, datetime.time):
        return val.hour * 60 + val.minute
    if isinstance(val, datetime.timedelta):
        return int(round(val.total_seconds() / 60))
    if isinstance(val, (int, float)):
        return int(round(val * 1440))
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


def chave_num_atleta(nome_str):
    m = re.search(r"\d+", str(nome_str))
    num = int(m.group()) if m else 999999
    return (num, str(nome_str).strip())


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

modo_exibicao = st.sidebar.selectbox(
    "Modo de Exibição",
    ["Total", "Média", "Por 40 Minutos", "Por 100 Posses", "Avançadas"],
)

todos_times = sorted(df["Time"].dropna().unique(), key=nome_completo_time)
times_sel = st.sidebar.multiselect(
    "Equipe(s) (vazio = Todos os Times)",
    todos_times,
    default=[],
    format_func=nome_completo_time
)

df_time = df[df["Time"].isin(times_sel)].copy() if times_sel else df.copy()

opcoes_tamanho = {
    "5 - Quintetos": 5,
    "4 - Quartetos": 4,
    "3 - Trios": 3,
    "2 - Duplas": 2,
    "1 - Individual": 1,
}
tamanho_label = st.sidebar.selectbox("Tamanho da Combinação", list(opcoes_tamanho.keys()))
tamanho_comb = opcoes_tamanho[tamanho_label]

todos_atletas = sorted(
    {
        p.strip()
        for k in df_time["Kinteto"].dropna()
        for p in str(k).split("/")
        if p.strip()
    },
    key=chave_num_atleta,
)
atletas_sel = st.sidebar.multiselect("Filtrar por Atleta(s) em Quadra", todos_atletas)

jogos = sorted(df_time["ID"].dropna().unique())
jogos_sel = st.sidebar.multiselect("Jogos", jogos, default=jogos)

quartos = sorted(df_time["P"].dropna().unique())
quartos_sel = st.sidebar.multiselect("Períodos", quartos, default=quartos)

col_f1, col_f2 = st.sidebar.columns(2)
min_jogos = col_f1.number_input("Mín. Jogos", min_value=1, value=1, step=1)
min_minutos = col_f2.number_input("Mín. Minutos", min_value=0, value=0, step=1)

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
    jogadores = sorted(
        {p.strip() for p in str(kinteto_str).split("/") if p.strip()},
        key=chave_num_atleta,
    )
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

# --- AGREGAÇÃO POR TIME E LINEUP ---
cols_soma = [
    "DUR_S", "PTS", "2PM", "2PA", "3PM", "3PA", "FTM", "FTA",
    "OR", "DR", "REB", "AST", "TO", "STL", "BLK", "PF",
    "PTS_A", "2PM_A", "2PA_A", "3PM_A", "3PA_A", "FTM_A", "FTA_A",
    "OR_A", "DR_A", "REB_A", "AST_A", "TO_A", "STL_A", "BLK_A", "PF_A", "+/-",
]

agg = df_exp.groupby(["Time", "Lineup"], as_index=False).agg(
    JO=("ID", "nunique"),
    **{c: (c, "sum") for c in cols_soma},
)

# --- CÁLCULO OFICIAL DE POSSES EM SEGUNDO PLANO (FÓRMULA LNB: COEFICIENTE 4/9) ---
fga = agg["2PA"] + agg["3PA"]
fgm = agg["2PM"] + agg["3PM"]
fga_a = agg["2PA_A"] + agg["3PA_A"]
fgm_a = agg["2PM_A"] + agg["3PM_A"]

posses_off = fga + (4 / 9) * agg["FTA"] + agg["TO"] - agg["OR"]
posses_def = fga_a + (4 / 9) * agg["FTA_A"] + agg["TO_A"] - agg["OR_A"]
agg["POSSES"] = ((posses_off + posses_def) / 2).round().astype(int)

# --- FILTROS DE AMOSTRA MÍNIMA (JOGOS E MINUTOS) ---
agg = agg[(agg["JO"] >= min_jogos) & ((agg["DUR_S"] / 60.0) >= min_minutos)].copy()

if agg.empty:
    st.warning("Nenhum lineup atingiu o mínimo de jogos/minutos selecionado.")
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


def montar_box_score_simples(head_dict, fator_div, fator_mult, casas_decimais):
    def calc(serie):
        res = (serie / fator_div) * fator_mult
        return res.round(0).astype(int) if casas_decimais == 0 else res.round(casas_decimais)

    dados = {}
    for col_nome, valores in head_dict.items():
        dados[col_nome] = valores

    # Bloco Ofensivas (Verde)
    cols_off = {
        "PTS": calc(agg["PTS"]),
        "FGM": calc(fgm),
        "FGA": calc(fga),
        "FG%": pcts["FG%"],
        "2PC": calc(agg["2PM"]),
        "2PT": calc(agg["2PA"]),
        "2P%": pcts["2P%"],
        "3PC": calc(agg["3PM"]),
        "3PT": calc(agg["3PA"]),
        "3P%": pcts["3P%"],
        "LLC": calc(agg["FTM"]),
        "LLT": calc(agg["FTA"]),
        "LL%": pcts["LL%"],
        "RO": calc(agg["OR"]),
        "RD": calc(agg["DR"]),
        "REB": calc(agg["REB"]),
        "AST": calc(agg["AST"]),
        "TOV": calc(agg["TO"]),
        "STL": calc(agg["STL"]),
        "BLK": calc(agg["BLK"]),
        "F": calc(agg["PF"]),
        "EF": calc(ef),
    }
    dados.update(cols_off)

    # Coluna Neutra (+/-)
    dados["+/-"] = calc(agg["+/-"])

    # Bloco Defensivas (Vermelho)
    cols_def = {
        "Opp PTS": calc(agg["PTS_A"]),
        "Opp FGM": calc(fgm_a),
        "Opp FGA": calc(fga_a),
        "Opp FG%": pcts["Opp FG%"],
        "Opp 2PC": calc(agg["2PM_A"]),
        "Opp 2PT": calc(agg["2PA_A"]),
        "Opp 2P%": pcts["Opp 2P%"],
        "Opp 3PC": calc(agg["3PM_A"]),
        "Opp 3PT": calc(agg["3PA_A"]),
        "Opp 3P%": pcts["Opp 3P%"],
        "Opp LLC": calc(agg["FTM_A"]),
        "Opp LLT": calc(agg["FTA_A"]),
        "Opp LL%": pcts["Opp LL%"],
        "Opp RO": calc(agg["OR_A"]),
        "Opp RD": calc(agg["DR_A"]),
        "Opp REB": calc(agg["REB_A"]),
        "Opp AST": calc(agg["AST_A"]),
        "Opp TOV": calc(agg["TO_A"]),
        "Opp STL": calc(agg["STL_A"]),
        "Opp BLK": calc(agg["BLK_A"]),
        "Opp F": calc(agg["PF_A"]),
        "Opp EF": calc(ef_a),
    }
    dados.update(cols_def)

    return pd.DataFrame(dados), list(cols_off.keys()), list(cols_def.keys())


# --- MONTAGEM DA TABELA CONFORME O MODO ---
if modo_exibicao == "Total":
    head = {
        "Time": agg["Time"],
        "Minutos": agg["DUR_S"].apply(sec_to_dur),
        "JO": agg["JO"],
    }
    tabela, cols_verdes, cols_vermelhas = montar_box_score_simples(head, 1, 1, 0)
    fmt_decimais = 0

elif modo_exibicao == "Média":
    jo_div = agg["JO"].replace(0, 1)
    head = {
        "Time": agg["Time"],
        "Minutos": (agg["DUR_S"] / jo_div).apply(sec_to_dur),
        "JO": agg["JO"],
    }
    tabela, cols_verdes, cols_vermelhas = montar_box_score_simples(head, jo_div, 1, 1)
    fmt_decimais = 1

elif modo_exibicao == "Por 40 Minutos":
    min_div = (agg["DUR_S"] / 60.0).replace(0, 1)
    head = {
        "Time": agg["Time"],
        "Minutos": agg["DUR_S"].apply(sec_to_dur),
        "JO": agg["JO"],
    }
    tabela, cols_verdes, cols_vermelhas = montar_box_score_simples(head, min_div, 40, 1)
    fmt_decimais = 1

elif modo_exibicao == "Por 100 Posses":
    pos_div = agg["POSSES"].replace(0, 1)
    head = {
        "Time": agg["Time"],
        "Minutos": agg["DUR_S"].apply(sec_to_dur),
        "JO": agg["JO"],
    }
    tabela, cols_verdes, cols_vermelhas = montar_box_score_simples(head, pos_div, 100, 1)
    fmt_decimais = 1

elif modo_exibicao == "Avançadas":
    pos_div = agg["POSSES"].replace(0, 1)
    min_float = agg["DUR_S"] / 60.0

    efg_off = np.where(fga > 0, ((fgm + 0.5 * agg["3PM"]) / fga * 100).round(1), 0.0)
    tov_denom_off = (fga + (4 / 9) * agg["FTA"] + agg["TO"]).round(0)
    tov_off = np.where(tov_denom_off > 0, (agg["TO"] / tov_denom_off * 100).round(1), 0.0)
    orb_denom_off = agg["OR"] + agg["DR_A"]
    orb_off = np.where(orb_denom_off > 0, (agg["OR"] / orb_denom_off * 100).round(1), 0.0)
    fta_rate_off = np.where(fga > 0, (agg["FTA"] / fga).round(3), 0.0)
    off_rtg = ((agg["PTS"] / pos_div) * 100).round(1)

    efg_def = np.where(fga_a > 0, ((fgm_a + 0.5 * agg["3PM_A"]) / fga_a * 100).round(1), 0.0)
    tov_denom_def = (fga_a + (4 / 9) * agg["FTA_A"] + agg["TO_A"]).round(0)
    tov_def = np.where(tov_denom_def > 0, (agg["TO_A"] / tov_denom_def * 100).round(1), 0.0)
    orb_denom_def = agg["OR_A"] + agg["DR"]
    orb_def = np.where(orb_denom_def > 0, (agg["OR_A"] / orb_denom_def * 100).round(1), 0.0)
    fta_rate_def = np.where(fga_a > 0, (agg["FTA_A"] / fga_a).round(3), 0.0)
    def_rtg = ((agg["PTS_A"] / pos_div) * 100).round(1)

    pace = np.where(min_float > 0, ((agg["POSSES"] / min_float) * 40).round(1), 0.0)

    dados_adv = {
        "Time": agg["Time"],
        "Minutos": agg["DUR_S"].apply(sec_to_dur),
        "JO": agg["JO"],
        "PACE": pace,
        "eFG%": efg_off,
        "TOV%": tov_off,
        "ORB%": orb_off,
        "FTA Rate": fta_rate_off,
        "OFFRTG": off_rtg,
        "Opp eFG%": efg_def,
        "Opp TOV%": tov_def,
        "Opp ORB%": orb_def,
        "Opp FTA Rate": fta_rate_def,
        "DEFRTG": def_rtg,
        "NETRTG": (off_rtg - def_rtg).round(1),
    }
    tabela = pd.DataFrame(dados_adv)
    cols_verdes = ["eFG%", "TOV%", "ORB%", "FTA Rate", "OFFRTG"]
    cols_vermelhas = ["Opp eFG%", "Opp TOV%", "Opp ORB%", "Opp FTA Rate", "DEFRTG"]
    fmt_decimais = 1

# --- CONGELA A COLUNA LINEUP COMO ÍNDICE SIMPLES ---
tabela.index = pd.Index(agg["Lineup"].values, name="Lineup")


# --- LEGENDA DE CORES ACIMA DA TABELA ---
st.markdown(
    """
    <div style="display: flex; gap: 18px; align-items: center; margin-bottom: 8px; font-size: 13px;">
        <span style="display: inline-flex; align-items: center; gap: 6px;">
            <span style="width: 14px; height: 14px; background-color: rgba(46, 204, 113, 0.28); border: 1px solid rgba(46, 204, 113, 0.6); border-radius: 3px; display: inline-block;"></span>
            <strong>Ofensivas</strong>
        </span>
        <span style="display: inline-flex; align-items: center; gap: 6px;">
            <span style="width: 14px; height: 14px; background-color: rgba(231, 76, 60, 0.28); border: 1px solid rgba(231, 76, 60, 0.6); border-radius: 3px; display: inline-block;"></span>
            <strong>Defensivas</strong>
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)


# --- FORMATAÇÃO VISUAL, CENTRALIZAÇÃO E CORES POR BLOCO ---
def fmt_plus_minus(val):
    if pd.isna(val):
        return ""
    if fmt_decimais == 0:
        v = int(round(val))
        return f"+{v}" if v > 0 else ("0" if v == 0 else f"{v}")
    else:
        v = round(float(val), 1)
        if v == 0:
            return "0.0"
        return f"+{v:.1f}" if v > 0 else f"{v:.1f}"


formatos = {}
col_config = {
    "_index": st.column_config.TextColumn("Lineup", alignment="left")
}

for col in tabela.columns:
    if col == "+/-":
        formatos[col] = fmt_plus_minus
        col_config[col] = st.column_config.NumberColumn(col, alignment="center")
    elif col == "JO":
        formatos[col] = "{:.0f}"
        col_config[col] = st.column_config.NumberColumn(col, alignment="center")
    elif "FTA Rate" in col:
        formatos[col] = "{:.3f}"
        col_config[col] = st.column_config.NumberColumn(col, alignment="center")
    elif "%" in col:
        formatos[col] = "{:.1f}%"
        col_config[col] = st.column_config.NumberColumn(col, alignment="center")
    elif col in ["PACE", "OFFRTG", "DEFRTG", "NETRTG"]:
        formatos[col] = "{:.1f}"
        col_config[col] = st.column_config.NumberColumn(col, alignment="center")
    elif col in ["Time", "Minutos"]:
        col_config[col] = st.column_config.TextColumn(col, alignment="center")
    else:
        formatos[col] = "{:.0f}" if fmt_decimais == 0 else "{:.1f}"
        col_config[col] = st.column_config.NumberColumn(col, alignment="center")

tabela_estilizada = (
    tabela.style
    .format(formatos)
    .set_properties(subset=cols_verdes, **{"background-color": "rgba(46, 204, 113, 0.16)"})
    .set_properties(subset=cols_vermelhas, **{"background-color": "rgba(231, 76, 60, 0.16)"})
)

altura_tabela = min(max(len(tabela) * 35 + 42, 180), 560)
st.dataframe(tabela_estilizada, column_config=col_config, height=altura_tabela, use_container_width=True)

# --- RODAPÉ COM IMAGEM ---
exibir_banner("footerNBB", tipo="footer")
