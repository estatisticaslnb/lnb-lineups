import os
import re
import base64
import datetime
from functools import lru_cache
from itertools import combinations
import streamlit as st
import pandas as pd
import numpy as np
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

st.set_page_config(page_title="LNB Lineups", layout="wide")

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 1.5rem !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
        }
        [data-testid="stSidebar"] {
            min-width: 300px !important;
            max-width: 300px !important;
        }
        [data-testid="stSidebar"] * {
            font-size: 13px !important;
        }
        [data-testid="stSidebar"] h2 {
            font-size: 18px !important;
            margin-top: 0px !important;
            padding-top: 0px !important;
        }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.55rem !important;
        }
        [data-testid="stSidebarHeader"] {
            height: 1.8rem !important;
            padding-top: 0.4rem !important;
            padding-bottom: 0rem !important;
        }
        [data-testid="stSidebarUserContent"] {
            padding-top: 0.2rem !important;
        }
        header[data-testid="stHeader"] {
            background: transparent !important;
            height: 2.2rem !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def carregar_banner_html(prefixo, tipo="header"):
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
        return ""

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

    return f"""
        <div style="background-color: #ffffff; padding: 10px 16px; text-align: center; {borda}">
            <img src="data:image/{ext};base64,{b64}" style="max-height: 80px; max-width: 100%; height: auto; display: block; margin: 0 auto;" />
        </div>
    """


def exibir_banner(prefixo, tipo="header"):
    html = carregar_banner_html(prefixo, tipo)
    if html:
        st.markdown(html, unsafe_allow_html=True)


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


def chave_num_atleta(nome_str):
    m = re.search(r"\d+", str(nome_str))
    num = int(m.group()) if m else 999999
    return (num, str(nome_str).strip())


def limpar_valor_str(val):
    if pd.isna(val):
        return np.nan
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val).strip()


def chave_ordenacao_mista(val):
    s = str(val).strip()
    m = re.search(r"\d+", s)
    if s.isdigit():
        return (0, int(s), s)
    if m:
        return (1, int(m.group()), s)
    return (2, 999999, s)


def normalizar_kinteto_tuple(kinteto_str):
    if pd.isna(kinteto_str):
        return ()
    return tuple(
        sorted(
            {p.strip() for p in str(kinteto_str).split("/") if p.strip()},
            key=chave_num_atleta,
        )
    )


def medir_largura_texto_px(texto):
    largura = 0.0
    for ch in str(texto):
        if ch in " .,-/'":
            largura += 3.6
        elif ch in "ilI1|!":
            largura += 4.2
        elif ch in "MWmw@#":
            largura += 10.2
        elif ch.isupper() or ch.isdigit():
            largura += 7.8
        else:
            largura += 6.5
    return largura


@lru_cache(maxsize=8192)
def gerar_combinacoes_cached(jogadores_tuple, r):
    if not jogadores_tuple:
        return ()
    if r == 5:
        return (" / ".join(jogadores_tuple),)
    if len(jogadores_tuple) < r:
        return ()
    return tuple(" / ".join(comb) for comb in combinations(jogadores_tuple, r))


@st.cache_data
def load_data(planilha, mtime):
    if planilha.lower().endswith(".csv"):
        df = pd.read_csv(planilha)
    else:
        df = pd.read_excel(planilha)

    df["DUR_S"] = df["D"].apply(dur_to_sec)
    df["ID"] = df["ID"].apply(limpar_valor_str)
    df["P"] = df["P"].apply(limpar_valor_str)
    df["JOGADORES_TUPLE"] = df["Kinteto"].apply(normalizar_kinteto_tuple)
    return df


arquivos = os.listdir(".")
planilha = next((f for f in arquivos if f.lower().endswith((".xlsx", ".xls", ".csv"))), None)

if not planilha:
    st.error(f"Nenhuma planilha encontrada no repositório. Arquivos atuais: {arquivos}")
    st.stop()

df = load_data(planilha, os.path.getmtime(planilha))

st.markdown(
    """
    <h1 style="text-align: left; font-size: 28px; font-weight: 700; margin-top: 0px; margin-bottom: 12px;">
        NBB CAIXA 2026/2027
    </h1>
    """,
    unsafe_allow_html=True,
)

# --- BARRA LATERAL (FILTROS) ---
st.sidebar.header("Filtros")

modo_exibicao = st.sidebar.selectbox(
    "Modo de Exibição",
    ["Total", "Média", "Por 40 Minutos", "Por 100 Posses", "Avançadas"],
)

todos_times = sorted(df["Time"].dropna().unique(), key=nome_completo_time)
times_sel = st.sidebar.multiselect(
    "Time(s) (vazio = Todos)",
    todos_times,
    default=[],
    format_func=nome_completo_time,
)

df_time = df[df["Time"].isin(times_sel)] if times_sel else df

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
    {p for tup in df_time["JOGADORES_TUPLE"] for p in tup},
    key=chave_num_atleta,
)
atletas_sel = st.sidebar.multiselect("Filtrar por Atleta(s) em Quadra", todos_atletas)

jogos = sorted(df_time["ID"].dropna().unique(), key=chave_ordenacao_mista)
jogos_sel = st.sidebar.multiselect("Jogos (vazio = Todos)", jogos, default=[])

quartos = sorted(df_time["P"].dropna().unique(), key=chave_ordenacao_mista)
quartos_sel = st.sidebar.multiselect("Períodos", quartos, default=quartos)

col_f1, col_f2 = st.sidebar.columns(2)
min_jogos = col_f1.number_input("Mín. Jogos", min_value=1, value=1, step=1)
min_minutos = col_f2.number_input("Mín. Minutos", min_value=0, value=0, step=1)

# --- FILTRAGEM INICIAL (INCLUINDO ATLETAS ANTES DE EXPLODIR COMBINAÇÕES) ---
jogos_ativos = jogos_sel if jogos_sel else jogos
mask_base = (df_time["ID"].isin(jogos_ativos)) & (df_time["P"].isin(quartos_sel))

if atletas_sel:
    atletas_set = set(atletas_sel)
    mask_atletas = df_time["JOGADORES_TUPLE"].apply(atletas_set.issubset)
    mask_base = mask_base & mask_atletas

df_filtrado = df_time[mask_base].copy()

if df_filtrado.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

# --- EXPANSÃO DE COMBINAÇÕES (COM CACHE POR QUINTETO) ---
if tamanho_comb == 5:
    df_filtrado["Lineup"] = df_filtrado["JOGADORES_TUPLE"].apply(
        lambda tup: " / ".join(tup) if tup else ""
    )
    df_exp = df_filtrado[df_filtrado["Lineup"] != ""]
else:
    df_filtrado["Lineup"] = df_filtrado["JOGADORES_TUPLE"].apply(
        lambda tup: gerar_combinacoes_cached(tup, tamanho_comb)
    )
    df_exp = df_filtrado.explode("Lineup")
    df_exp = df_exp[df_exp["Lineup"].notna() & (df_exp["Lineup"] != "")]

if atletas_sel and tamanho_comb < 5:
    atletas_set = set(atletas_sel)
    mask_comb = df_exp["Lineup"].apply(
        lambda l: atletas_set.issubset(p.strip() for p in str(l).split("/"))
    )
    df_exp = df_exp[mask_comb]

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

agg = df_exp.groupby(["Time", "Lineup"], as_index=False, sort=False).agg(
    JO=("ID", "nunique"),
    **{c: (c, "sum") for c in cols_soma},
)

# --- CÁLCULO EXATO DE POSSES EM SEGUNDO PLANO (FÓRMULA LNB: COEFICIENTE 4/9) ---
fga = agg["2PA"] + agg["3PA"]
fgm = agg["2PM"] + agg["3PM"]
fga_a = agg["2PA_A"] + agg["3PA_A"]
fgm_a = agg["2PM_A"] + agg["3PM_A"]

posses_off = fga + (4 / 9) * agg["FTA"] + agg["TO"] - agg["OR"]
posses_def = fga_a + (4 / 9) * agg["FTA_A"] + agg["TO_A"] - agg["OR_A"]
agg["POSSES"] = (posses_off + posses_def) / 2.0

# --- FILTROS DE AMOSTRA MÍNIMA (JOGOS E MINUTOS) ---
agg = agg[(agg["JO"] >= min_jogos) & ((agg["DUR_S"] / 60.0) >= min_minutos)].copy()

if agg.empty:
    st.warning("Nenhum lineup atingiu o mínimo de jogos/minutos selecionado.")
    st.stop()

agg = agg.sort_values(by="DUR_S", ascending=False).reset_index(drop=True)

total_linhas = len(agg)
limite_padrao = 250
if total_linhas > limite_padrao:
    mostrar_tudo = st.sidebar.checkbox(
        f"Exibir todas as {total_linhas} linhas (pode deixar o navegador mais lento)",
        value=False,
    )
    if not mostrar_tudo:
        agg = agg.iloc[:limite_padrao].copy()

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

    # Bloco Defensivas (Vermelho - usa espaço invisível no nome interno para diferenciar do bloco ofensivo)
    cols_def = {
        "PTS ": calc(agg["PTS_A"]),
        "FGM ": calc(fgm_a),
        "FGA ": calc(fga_a),
        "FG% ": pcts["Opp FG%"],
        "2PC ": calc(agg["2PM_A"]),
        "2PT ": calc(agg["2PA_A"]),
        "2P% ": pcts["Opp 2P%"],
        "3PC ": calc(agg["3PM_A"]),
        "3PT ": calc(agg["3PA_A"]),
        "3P% ": pcts["Opp 3P%"],
        "LLC ": calc(agg["FTM_A"]),
        "LLT ": calc(agg["FTA_A"]),
        "LL% ": pcts["Opp LL%"],
        "RO ": calc(agg["OR_A"]),
        "RD ": calc(agg["DR_A"]),
        "REB ": calc(agg["REB_A"]),
        "AST ": calc(agg["AST_A"]),
        "TOV ": calc(agg["TO_A"]),
        "STL ": calc(agg["STL_A"]),
        "BLK ": calc(agg["BLK_A"]),
        "F ": calc(agg["PF_A"]),
        "EF ": calc(ef_a),
    }
    dados.update(cols_def)

    return pd.DataFrame(dados), list(cols_off.keys()), list(cols_def.keys())


# --- MONTAGEM DA TABELA CONFORME O MODO (MINUTOS EM SEGUNDOS NUMÉRICOS PARA ORDENAÇÃO EXATA) ---
base_head = {
    "Lineup": agg["Lineup"],
    "Time": agg["Time"],
}

if modo_exibicao == "Total":
    head = {**base_head, "Min.": agg["DUR_S"].round(0).astype(int), "JO": agg["JO"]}
    tabela, cols_verdes, cols_vermelhas = montar_box_score_simples(head, 1, 1, 0)
    fmt_decimais = 0

elif modo_exibicao == "Média":
    jo_div = agg["JO"].replace(0, 1)
    head = {**base_head, "Min.": (agg["DUR_S"] / jo_div).round(0).astype(int), "JO": agg["JO"]}
    tabela, cols_verdes, cols_vermelhas = montar_box_score_simples(head, jo_div, 1, 1)
    fmt_decimais = 1

elif modo_exibicao == "Por 40 Minutos":
    min_div = (agg["DUR_S"] / 60.0).replace(0, 1)
    head = {**base_head, "Min.": agg["DUR_S"].round(0).astype(int), "JO": agg["JO"]}
    tabela, cols_verdes, cols_vermelhas = montar_box_score_simples(head, min_div, 40, 1)
    fmt_decimais = 1

elif modo_exibicao == "Por 100 Posses":
    pos_div = agg["POSSES"].replace(0, 1)
    head = {**base_head, "Min.": agg["DUR_S"].round(0).astype(int), "JO": agg["JO"]}
    tabela, cols_verdes, cols_vermelhas = montar_box_score_simples(head, pos_div, 100, 1)
    fmt_decimais = 1

elif modo_exibicao == "Avançadas":
    pos_div = agg["POSSES"].replace(0, 1)
    min_float = agg["DUR_S"] / 60.0

    efg_off = np.where(fga > 0, ((fgm + 0.5 * agg["3PM"]) / fga * 100).round(1), 0.0)
    tov_denom_off = fga + (4 / 9) * agg["FTA"] + agg["TO"]
    tov_off = np.where(tov_denom_off > 0, (agg["TO"] / tov_denom_off * 100).round(1), 0.0)
    orb_denom_off = agg["OR"] + agg["DR_A"]
    orb_off = np.where(orb_denom_off > 0, (agg["OR"] / orb_denom_off * 100).round(1), 0.0)
    fta_rate_off = np.where(fga > 0, (agg["FTA"] / fga).round(3), 0.0)
    off_rtg = ((agg["PTS"] / pos_div) * 100).round(1)

    efg_def = np.where(fga_a > 0, ((fgm_a + 0.5 * agg["3PM_A"]) / fga_a * 100).round(1), 0.0)
    tov_denom_def = fga_a + (4 / 9) * agg["FTA_A"] + agg["TO_A"]
    tov_def = np.where(tov_denom_def > 0, (agg["TO_A"] / tov_denom_def * 100).round(1), 0.0)
    orb_denom_def = agg["OR_A"] + agg["DR"]
    orb_def = np.where(orb_denom_def > 0, (agg["OR_A"] / orb_denom_def * 100).round(1), 0.0)
    fta_rate_def = np.where(fga_a > 0, (agg["FTA_A"] / fga_a).round(3), 0.0)
    def_rtg = ((agg["PTS_A"] / pos_div) * 100).round(1)

    pace = np.where(min_float > 0, ((agg["POSSES"] / min_float) * 40).round(1), 0.0)

    dados_adv = {
        **base_head,
        "Min.": agg["DUR_S"].round(0).astype(int),
        "JO": agg["JO"],
        "PACE": pace,
        "eFG%": efg_off,
        "TOV%": tov_off,
        "ORB%": orb_off,
        "FTA Rate": fta_rate_off,
        "OFFRTG": off_rtg,
        "eFG% ": efg_def,
        "TOV% ": tov_def,
        "ORB% ": orb_def,
        "FTA Rate ": fta_rate_def,
        "DEFRTG": def_rtg,
        "NETRTG": (off_rtg - def_rtg).round(1),
    }
    tabela = pd.DataFrame(dados_adv)
    cols_verdes = ["eFG%", "TOV%", "ORB%", "FTA Rate", "OFFRTG"]
    cols_vermelhas = ["eFG% ", "TOV% ", "ORB% ", "FTA Rate ", "DEFRTG"]
    fmt_decimais = 1


# --- LEGENDA DE CORES ACIMA DA TABELA ---
legenda_extra = (
    f'<span style="color: #64748b; margin-left: auto;">Exibindo Top {len(agg)} de {total_linhas} combinações (ordenadas por minutos totais)</span>'
    if total_linhas > len(agg)
    else ""
)

st.markdown(
    f"""
    <div style="display: flex; gap: 18px; align-items: center; margin-bottom: 8px; font-size: 13px; flex-wrap: wrap;">
        <span style="display: inline-flex; align-items: center; gap: 6px;">
            <span style="width: 14px; height: 14px; background-color: rgba(46, 204, 113, 0.28); border: 1px solid rgba(46, 204, 113, 0.6); border-radius: 3px; display: inline-block;"></span>
            <strong>Ofensivas</strong>
        </span>
        <span style="display: inline-flex; align-items: center; gap: 6px;">
            <span style="width: 14px; height: 14px; background-color: rgba(231, 76, 60, 0.28); border: 1px solid rgba(231, 76, 60, 0.6); border-radius: 3px; display: inline-block;"></span>
            <strong>Defensivas</strong>
        </span>
        {legenda_extra}
    </div>
    """,
    unsafe_allow_html=True,
)


# --- CONFIGURAÇÃO DO AG-GRID (TODOS OS CABEÇALHOS CENTRALIZADOS E LINEUP À ESQUERDA NO CORPO) ---
gb = GridOptionsBuilder.from_dataframe(tabela)
gb.configure_default_column(
    sortable=True,
    resizable=True,
    filter=False,
    suppressMenu=True,
    suppressHeaderMenuButton=True,
    suppressHeaderFilterButton=True,
    cellStyle={"textAlign": "center", "borderRight": "1px solid #94a3b8"},
)

# 1. Coluna Lineup congelada (cabeçalho centralizado via CSS global; células alinhadas à esquerda)
max_px_lineup = float(agg["Lineup"].apply(medir_largura_texto_px).max()) if not agg.empty else 110.0
largura_lineup = max(int(np.ceil(max_px_lineup)) + 16, 95)
gb.configure_column(
    "Lineup",
    headerName="LINEUP",
    pinned="left",
    width=largura_lineup,
    minWidth=largura_lineup,
    cellStyle={
        "textAlign": "left",
        "fontWeight": "500",
        "borderRight": "1px solid #94a3b8",
    },
)

# 2. Coluna Time congelada
gb.configure_column(
    "Time",
    headerName="Time",
    pinned="left",
    width=44,
    minWidth=44,
    cellStyle={
        "textAlign": "center",
        "borderRight": "2px solid #475569",
    },
)

# Formatadores JS para números, minutos (MM:SS), percentuais e +/-
fmt_dur = JsCode(
    "function(p) { if (p.value == null) return ''; var s = Math.round(Number(p.value)); var m = Math.floor(s / 60); var r = s % 60; return (m < 10 ? '0' + m : m) + ':' + (r < 10 ? '0' + r : r); }"
)
fmt_int = JsCode("function(p) { return p.value == null ? '' : Math.round(p.value).toString(); }")
fmt_dec1 = JsCode("function(p) { return p.value == null ? '' : Number(p.value).toFixed(1); }")
fmt_dec3 = JsCode("function(p) { return p.value == null ? '' : Number(p.value).toFixed(3); }")
fmt_pct = JsCode("function(p) { return p.value == null ? '' : Number(p.value).toFixed(1) + '%'; }")
fmt_pm_int = JsCode(
    "function(p) { if (p.value == null) return ''; var v = Math.round(p.value); return v > 0 ? '+' + v : v.toString(); }"
)
fmt_pm_dec = JsCode(
    "function(p) { if (p.value == null) return ''; var v = Number(p.value); if (Math.abs(v) < 0.05) return '0.0'; return v > 0 ? '+' + v.toFixed(1) : v.toFixed(1); }"
)

for col in tabela.columns:
    if col in ["Lineup", "Time"]:
        continue

    titulo_visivel = col.strip()
    estilo_celula = {
        "textAlign": "center",
        "borderRight": "1px solid #94a3b8",
    }
    if col in cols_verdes:
        estilo_celula["backgroundColor"] = "rgba(46, 204, 113, 0.16)"
    elif col in cols_vermelhas:
        estilo_celula["backgroundColor"] = "rgba(231, 76, 60, 0.16)"

    largura_col = 40 if len(titulo_visivel) <= 3 else (46 if len(titulo_visivel) <= 5 else 56)

    kwargs_col = {
        "headerName": titulo_visivel,
        "cellStyle": estilo_celula,
        "width": largura_col,
        "minWidth": largura_col,
    }

    if titulo_visivel in ["+/-", "NETRTG"]:
        kwargs_col["valueFormatter"] = fmt_pm_int if fmt_decimais == 0 else fmt_pm_dec
        kwargs_col["width"] = 48
        kwargs_col["minWidth"] = 48
    elif titulo_visivel == "JO":
        kwargs_col["valueFormatter"] = fmt_int
        kwargs_col["width"] = 36
        kwargs_col["minWidth"] = 36
    elif "FTA Rate" in titulo_visivel:
        kwargs_col["valueFormatter"] = fmt_dec3
        kwargs_col["width"] = 58
        kwargs_col["minWidth"] = 58
    elif "%" in titulo_visivel:
        kwargs_col["valueFormatter"] = fmt_pct
        kwargs_col["width"] = 48
        kwargs_col["minWidth"] = 48
    elif titulo_visivel in ["PACE", "OFFRTG", "DEFRTG"]:
        kwargs_col["valueFormatter"] = fmt_dec1
        kwargs_col["width"] = 52
        kwargs_col["minWidth"] = 52
    elif titulo_visivel == "Min.":
        kwargs_col["valueFormatter"] = fmt_dur
        kwargs_col["width"] = 48
        kwargs_col["minWidth"] = 48
    else:
        kwargs_col["valueFormatter"] = fmt_int if fmt_decimais == 0 else fmt_dec1

    gb.configure_column(col, **kwargs_col)

refresh_rank_js = JsCode(
    "function(params) { params.api.refreshCells({columns: ['rank_col'], force: true}); }"
)

gb.configure_grid_options(
    domLayout="normal",
    rowHeight=29,
    headerHeight=33,
    suppressMovableColumns=True,
    animateRows=False,
    onSortChanged=refresh_rank_js,
    onFilterChanged=refresh_rank_js,
)

grid_options = gb.build()

# Insere a coluna # puramente dinâmica na primeira posição sem depender de campo fixo da linha
rank_col_def = {
    "colId": "rank_col",
    "headerName": "#",
    "pinned": "left",
    "sortable": False,
    "resizable": False,
    "filter": False,
    "suppressMenu": True,
    "suppressHeaderMenuButton": True,
    "width": 36,
    "minWidth": 36,
    "maxWidth": 42,
    "valueGetter": JsCode("function(params) { return params.node.rowIndex + 1; }"),
    "cellStyle": {
        "textAlign": "center",
        "fontWeight": "600",
        "color": "#334155",
        "borderRight": "1px solid #94a3b8",
    },
}
grid_options["columnDefs"].insert(0, rank_col_def)

custom_css = {
    ".ag-header-cell": {
        "padding-left": "2px !important",
        "padding-right": "2px !important",
        "border-right": "1px solid #94a3b8 !important",
        "font-size": "12.5px !important",
    },
    ".ag-cell": {
        "padding-left": "2px !important",
        "padding-right": "2px !important",
        "border-right": "1px solid #94a3b8 !important",
        "border-bottom": "1px solid #cbd5e1 !important",
        "font-size": "12.5px !important",
    },
    ".ag-pinned-left-cols-container .ag-cell[col-id='Time'], .ag-pinned-left-header .ag-header-cell[col-id='Time']": {
        "border-right": "2px solid #475569 !important",
    },
    ".ag-header-cell-comp-wrapper": {
        "width": "100% !important",
        "display": "flex !important",
        "justify-content": "center !important",
    },
    ".ag-header-cell-label": {
        "flex-direction": "row !important",
        "justify-content": "center !important",
        "align-items": "center !important",
        "width": "100% !important",
    },
    ".ag-header-cell-text": {
        "text-align": "center !important",
    },
    ".ag-pinned-left-cols-container .ag-cell[col-id='Lineup']": {
        "padding-left": "6px !important",
    },
    ".ag-header-cell-menu-button, .ag-header-cell-filter-button": {
        "display": "none !important",
    },
}

altura_tabela = min(max(len(tabela) * 29 + 37, 180), 520)

AgGrid(
    tabela,
    gridOptions=grid_options,
    height=altura_tabela,
    theme="alpine",
    allow_unsafe_jscode=True,
    custom_css=custom_css,
    fit_columns_on_grid_load=False,
    reload_data=True,
)

# --- RODAPÉ COM IMAGEM ---
exibir_banner("footerNBB", tipo="footer")
