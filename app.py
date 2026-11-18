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

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E CONSTANTES
# ==============================================================================
st.set_page_config(page_title="LNB Lineups", layout="wide")

MAPA_TIMES = {
    "BAU": "BAURU",
    "BCE": "B. CEARENSE",
    "BOT": "BOTAFOGO",
    "BRA": "BRASILIA",
    "CAP": "PAULISTANO",
    "CAX": "CAXIAS",
    "COR": "CORINTHIANS",
    "CRU": "CRUZEIRO",
    "FLA": "FLAMENGO",
    "FRA": "FRANCA",
    "MIN": "MINAS",
    "MOG": "MOGI",
    "OSA": "OSASCO",
    "PAT": "PATO",
    "PIN": "PINHEIROS",
    "SJO": "SAO JOSE",
    "UCO": "UNICO",
    "UFC": "UNIFACISA",
}

PADRAO_SIGLAS_TIMES = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in MAPA_TIMES.keys()) + r")\b"
)

OPCOES_TAMANHO = {
    "5 - Quintetos": 5,
    "4 - Quartetos": 4,
    "3 - Trios": 3,
    "2 - Duplas": 2,
    "1 - Individual": 1,
}

COLS_SOMA = [
    "DUR_S", "PTS", "2PM", "2PA", "3PM", "3PA", "FTM", "FTA",
    "OR", "DR", "REB", "AST", "TO", "STL", "BLK", "PF",
    "PTS_A", "2PM_A", "2PA_A", "3PM_A", "3PA_A", "FTM_A", "FTA_A",
    "OR_A", "DR_A", "REB_A", "AST_A", "TO_A", "STL_A", "BLK_A", "PF_A", "+/-",
]

LIMITE_PADRAO_LINHAS = 250


# ==============================================================================
# 2. FUNÇÕES AUXILIARES E FORMATAÇÃO
# ==============================================================================
def aplicar_css_global():
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
    img_path = next(
        (
            f for f in os.listdir(".")
            if f.lower().startswith(prefixo.lower())
            and f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ),
        None,
    )
    if not img_path:
        return ""

    ext = os.path.splitext(img_path)[1].lower().replace(".", "")
    ext = "jpeg" if ext == "jpg" else ext

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


def nome_completo_time(sigla):
    return MAPA_TIMES.get(str(sigla).strip().upper(), str(sigla).strip())


def identificar_mando(id_jogo, time_sigla):
    texto_id = str(id_jogo).upper()
    time_atual = str(time_sigla).strip().upper()

    encontrados = PADRAO_SIGLAS_TIMES.findall(texto_id)
    if len(encontrados) < 2:
        encontrados = re.findall(r"\b[A-Z]{3}\b", texto_id)

    if len(encontrados) >= 2:
        if time_atual == encontrados[0]:
            return "Mandante"
        if time_atual == encontrados[1]:
            return "Visitante"
    return "Indefinido"


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
        s_val = str(val).strip().split(" ")[-1]
        parts = [int(float(x)) for x in s_val.split(":")]
        if len(parts) >= 2:
            return parts[0] * 60 + parts[1]
    except Exception:
        return 0
    return 0


def chave_num_atleta(nome_str):
    m = re.search(r"\d+", str(nome_str))
    return (int(m.group()) if m else 999999, str(nome_str).strip())


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
    if not jogadores_tuple or len(jogadores_tuple) < r:
        return ()
    if r == 5:
        return (" / ".join(jogadores_tuple),)
    return tuple(" / ".join(comb) for comb in combinations(jogadores_tuple, r))


# ==============================================================================
# 3. CARREGAMENTO E MOTOR DE AGREGAÇÃO (CACHEADO)
# ==============================================================================
@st.cache_data
def load_data(planilha, mtime):
    df = pd.read_csv(planilha) if planilha.lower().endswith(".csv") else pd.read_excel(planilha)
    df["DUR_S"] = df["D"].apply(dur_to_sec)
    df["ID"] = df["ID"].apply(limpar_valor_str)
    df["P"] = df["P"].apply(limpar_valor_str)
    df["JOGADORES_TUPLE"] = df["Kinteto"].apply(normalizar_kinteto_tuple)
    df["MANDO"] = [identificar_mando(i, t) for i, t in zip(df["ID"], df["Time"])]
    return df


@st.cache_data
def agregar_lineups(
    planilha, mtime, times_sel, tamanho_comb, atletas_sel, jogos_sel, quartos_sel, mando_sel
):
    df = load_data(planilha, mtime)
    df_sub = df[df["Time"].isin(times_sel)] if times_sel else df

    mask = pd.Series(True, index=df_sub.index)
    if mando_sel != "Todos":
        mask &= df_sub["MANDO"] == mando_sel
    if jogos_sel:
        mask &= df_sub["ID"].isin(jogos_sel)
    if quartos_sel:
        mask &= df_sub["P"].isin(quartos_sel)
    if atletas_sel:
        atletas_set = set(atletas_sel)
        mask &= df_sub["JOGADORES_TUPLE"].apply(atletas_set.issubset)

    df_filt = df_sub[mask].copy()
    if df_filt.empty:
        return pd.DataFrame()

    if tamanho_comb == 5:
        df_filt["Lineup"] = df_filt["JOGADORES_TUPLE"].apply(lambda t: " / ".join(t) if t else "")
        df_exp = df_filt[df_filt["Lineup"] != ""]
    else:
        df_filt["Lineup"] = df_filt["JOGADORES_TUPLE"].apply(
            lambda t: gerar_combinacoes_cached(t, tamanho_comb)
        )
        df_exp = df_filt.explode("Lineup")
        df_exp = df_exp[df_exp["Lineup"].notna() & (df_exp["Lineup"] != "")]

    if atletas_sel and tamanho_comb < 5:
        atletas_set = set(atletas_sel)
        df_exp = df_exp[
            df_exp["Lineup"].apply(lambda l: atletas_set.issubset(p.strip() for p in str(l).split("/")))
        ]

    if df_exp.empty:
        return pd.DataFrame()

    agg = df_exp.groupby(["Time", "Lineup"], as_index=False, sort=False).agg(
        JO=("ID", "nunique"),
        **{c: (c, "sum") for c in COLS_SOMA},
    )

    # Estatísticas derivadas base e Posses (Fórmula LNB: coeficiente 4/9)
    agg["FGA"] = agg["2PA"] + agg["3PA"]
    agg["FGM"] = agg["2PM"] + agg["3PM"]
    agg["FGA_A"] = agg["2PA_A"] + agg["3PA_A"]
    agg["FGM_A"] = agg["2PM_A"] + agg["3PM_A"]

    posses_off = agg["FGA"] + (4 / 9) * agg["FTA"] + agg["TO"] - agg["OR"]
    posses_def = agg["FGA_A"] + (4 / 9) * agg["FTA_A"] + agg["TO_A"] - agg["OR_A"]
    agg["POSSES"] = (posses_off + posses_def) / 2.0

    agg["EF"] = (agg["PTS"] + agg["REB"] + agg["AST"] + agg["STL"] + agg["BLK"]) - (
        (agg["FGA"] - agg["FGM"]) + (agg["FTA"] - agg["FTM"]) + agg["TO"]
    )
    agg["EF_A"] = (agg["PTS_A"] + agg["REB_A"] + agg["AST_A"] + agg["STL_A"] + agg["BLK_A"]) - (
        (agg["FGA_A"] - agg["FGM_A"]) + (agg["FTA_A"] - agg["FTM_A"]) + agg["TO_A"]
    )

    return agg.sort_values(by="DUR_S", ascending=False).reset_index(drop=True)


def construir_tabela_exibicao(agg, modo_exibicao):
    fga, fgm = agg["FGA"], agg["FGM"]
    fga_a, fgm_a = agg["FGA_A"], agg["FGM_A"]

    pct = lambda num, den: np.where(den > 0, (num / den * 100).round(1), 0.0)

    if modo_exibicao == "Avançadas":
        pos_div = agg["POSSES"].replace(0, 1)
        min_float = agg["DUR_S"] / 60.0

        tov_off_den = fga + (4 / 9) * agg["FTA"] + agg["TO"]
        tov_def_den = fga_a + (4 / 9) * agg["FTA_A"] + agg["TO_A"]
        off_rtg = ((agg["PTS"] / pos_div) * 100).round(1)
        def_rtg = ((agg["PTS_A"] / pos_div) * 100).round(1)

        dados = {
            "Lineup": agg["Lineup"],
            "Time": agg["Time"],
            "Min.": agg["DUR_S"].round(0).astype(int),
            "JO": agg["JO"],
            "PACE": np.where(min_float > 0, ((agg["POSSES"] / min_float) * 40).round(1), 0.0),
            "eFG%": pct(fgm + 0.5 * agg["3PM"], fga),
            "TOV%": pct(agg["TO"], tov_off_den),
            "ORB%": pct(agg["OR"], agg["OR"] + agg["DR_A"]),
            "FTA Rate": np.where(fga > 0, (agg["FTA"] / fga).round(3), 0.0),
            "OFFRTG": off_rtg,
            "eFG% ": pct(fgm_a + 0.5 * agg["3PM_A"], fga_a),
            "TOV% ": pct(agg["TO_A"], tov_def_den),
            "ORB% ": pct(agg["OR_A"], agg["OR_A"] + agg["DR"]),
            "FTA Rate ": np.where(fga_a > 0, (agg["FTA_A"] / fga_a).round(3), 0.0),
            "DEFRTG": def_rtg,
            "NETRTG": (off_rtg - def_rtg).round(1),
        }
        cols_verdes = ["eFG%", "TOV%", "ORB%", "FTA Rate", "OFFRTG"]
        cols_vermelhas = ["eFG% ", "TOV% ", "ORB% ", "FTA Rate ", "DEFRTG"]
        return pd.DataFrame(dados), cols_verdes, cols_vermelhas, 1

    # Modos Box Score (Total, Média, Por 40 Minutos, Por 100 Posses ~)
    if modo_exibicao == "Total":
        fator_div, fator_mult, decimais = 1, 1, 0
        min_col = agg["DUR_S"].round(0).astype(int)
    elif modo_exibicao == "Média":
        fator_div = agg["JO"].replace(0, 1)
        fator_mult, decimais = 1, 1
        min_col = (agg["DUR_S"] / fator_div).round(0).astype(int)
    elif modo_exibicao == "Por 40 Minutos":
        fator_div = (agg["DUR_S"] / 60.0).replace(0, 1)
        fator_mult, decimais = 40, 1
        min_col = agg["DUR_S"].round(0).astype(int)
    else:  # Por 100 Posses ~
        fator_div = agg["POSSES"].replace(0, 1)
        fator_mult, decimais = 100, 1
        min_col = agg["DUR_S"].round(0).astype(int)

    def calc(serie):
        res = (serie / fator_div) * fator_mult
        return res.round(0).astype(int) if decimais == 0 else res.round(decimais)

    cols_off = {
        "PTS": calc(agg["PTS"]),
        "FGM": calc(fgm),
        "FGA": calc(fga),
        "FG%": pct(fgm, fga),
        "2PC": calc(agg["2PM"]),
        "2PT": calc(agg["2PA"]),
        "2P%": pct(agg["2PM"], agg["2PA"]),
        "3PC": calc(agg["3PM"]),
        "3PT": calc(agg["3PA"]),
        "3P%": pct(agg["3PM"], agg["3PA"]),
        "LLC": calc(agg["FTM"]),
        "LLT": calc(agg["FTA"]),
        "LL%": pct(agg["FTM"], agg["FTA"]),
        "RO": calc(agg["OR"]),
        "RD": calc(agg["DR"]),
        "REB": calc(agg["REB"]),
        "AST": calc(agg["AST"]),
        "TOV": calc(agg["TO"]),
        "STL": calc(agg["STL"]),
        "BLK": calc(agg["BLK"]),
        "F": calc(agg["PF"]),
        "EF": calc(agg["EF"]),
    }

    cols_def = {
        "PTS ": calc(agg["PTS_A"]),
        "FGM ": calc(fgm_a),
        "FGA ": calc(fga_a),
        "FG% ": pct(fgm_a, fga_a),
        "2PC ": calc(agg["2PM_A"]),
        "2PT ": calc(agg["2PA_A"]),
        "2P% ": pct(agg["2PM_A"], agg["2PA_A"]),
        "3PC ": calc(agg["3PM_A"]),
        "3PT ": calc(agg["3PA_A"]),
        "3P% ": pct(agg["3PM_A"], agg["3PA_A"]),
        "LLC ": calc(agg["FTM_A"]),
        "LLT ": calc(agg["FTA_A"]),
        "LL% ": pct(agg["FTM_A"], agg["FTA_A"]),
        "RO ": calc(agg["OR_A"]),
        "RD ": calc(agg["DR_A"]),
        "REB ": calc(agg["REB_A"]),
        "AST ": calc(agg["AST_A"]),
        "TOV ": calc(agg["TO_A"]),
        "STL ": calc(agg["STL_A"]),
        "BLK ": calc(agg["BLK_A"]),
        "F ": calc(agg["PF_A"]),
        "EF ": calc(agg["EF_A"]),
    }

    dados = {
        "Lineup": agg["Lineup"],
        "Time": agg["Time"],
        "Min.": min_col,
        "JO": agg["JO"],
        **cols_off,
        "+/-": calc(agg["+/-"]),
        **cols_def,
    }
    return pd.DataFrame(dados), list(cols_off.keys()), list(cols_def.keys()), decimais


# ==============================================================================
# 4. INTERFACE E FILTROS
# ==============================================================================
aplicar_css_global()
exibir_banner("headerNBB", tipo="header")

arquivos = os.listdir(".")
planilha = next((f for f in arquivos if f.lower().endswith((".xlsx", ".xls", ".csv"))), None)
if not planilha:
    st.error(f"Nenhuma planilha encontrada no repositório. Arquivos atuais: {arquivos}")
    st.stop()

mtime_planilha = os.path.getmtime(planilha)
df_raw = load_data(planilha, mtime_planilha)

st.markdown(
    """
    <h1 style="text-align: left; font-size: 28px; font-weight: 700; margin-top: 0px; margin-bottom: 12px;">
        NBB CAIXA 2026/2027
    </h1>
    """,
    unsafe_allow_html=True,
)

# Sidebar
st.sidebar.header("Filtros")

modo_exibicao = st.sidebar.selectbox(
    "Modo de Exibição",
    ["Total", "Média", "Por 40 Minutos", "Por 100 Posses ~", "Avançadas"],
)

todos_times = sorted(df_raw["Time"].dropna().unique(), key=nome_completo_time)
times_sel = st.sidebar.multiselect(
    "Time(s) (vazio = todos)",
    todos_times,
    default=[],
    format_func=nome_completo_time,
)

df_opcoes = df_raw[df_raw["Time"].isin(times_sel)] if times_sel else df_raw

tamanho_label = st.sidebar.selectbox("Tamanho da Combinação", list(OPCOES_TAMANHO.keys()))
tamanho_comb = OPCOES_TAMANHO[tamanho_label]

todos_atletas = sorted({p for tup in df_opcoes["JOGADORES_TUPLE"] for p in tup}, key=chave_num_atleta)
atletas_sel = st.sidebar.multiselect("Filtrar por Atleta(s) em Quadra", todos_atletas)

mando_sel = st.sidebar.selectbox("Mando de Quadra", ["Todos", "Mandante", "Visitante"])

df_opcoes_mando = df_opcoes[df_opcoes["MANDO"] == mando_sel] if mando_sel != "Todos" else df_opcoes

jogos = sorted(df_opcoes_mando["ID"].dropna().unique(), key=chave_ordenacao_mista)
jogos_sel = st.sidebar.multiselect("Jogos (vazio = todos)", jogos, default=[])

quartos = sorted(df_opcoes_mando["P"].dropna().unique(), key=chave_ordenacao_mista)
quartos_sel = st.sidebar.multiselect("Períodos (vazio = todos)", quartos, default=[])

col_f1, col_f2 = st.sidebar.columns(2)
min_jogos = col_f1.number_input("Mín. Jogos", min_value=1, value=1, step=1)
min_minutos = col_f2.number_input("Mín. Minutos", min_value=0, value=0, step=1)

# Execução da agregação cacheada (sempre ordenada por minutos totais acumulados)
agg = agregar_lineups(
    planilha,
    mtime_planilha,
    tuple(times_sel),
    tamanho_comb,
    tuple(atletas_sel),
    tuple(jogos_sel),
    tuple(quartos_sel),
    mando_sel,
)

if agg.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

agg = agg[(agg["JO"] >= min_jogos) & ((agg["DUR_S"] / 60.0) >= min_minutos)].reset_index(drop=True)
if agg.empty:
    st.warning("Nenhum lineup atingiu o mínimo de jogos/minutos selecionado.")
    st.stop()

total_linhas = len(agg)
if total_linhas > LIMITE_PADRAO_LINHAS:
    mostrar_tudo = st.sidebar.checkbox(
        f"Exibir todas as {total_linhas} linhas (pode deixar o navegador mais lento)",
        value=False,
    )
    if not mostrar_tudo:
        agg = agg.iloc[:LIMITE_PADRAO_LINHAS].copy()

if modo_exibicao == "Média":
    agg = (
        agg.assign(_DUR_MEDIA=agg["DUR_S"] / agg["JO"].replace(0, 1))
        .sort_values(by=["_DUR_MEDIA", "DUR_S"], ascending=[False, False])
        .drop(columns=["_DUR_MEDIA"])
        .reset_index(drop=True)
    )

tabela, cols_verdes, cols_vermelhas, fmt_decimais = construir_tabela_exibicao(agg, modo_exibicao)


# ==============================================================================
# 5. LEGENDA E RENDERIZAÇÃO DO AG-GRID
# ==============================================================================
legenda_extra = (
    f'<span style="color: #64748b; margin-left: auto;">Exibindo o Top {len(agg)} de {total_linhas} combinações (com mais minutos totais acumulados)</span>'
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

# Formatadores JS
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

gb = GridOptionsBuilder.from_dataframe(tabela)
gb.configure_default_column(
    sortable=True,
    resizable=True,
    filter=False,
    suppressMenu=True,
    suppressHeaderMenuButton=True,
    suppressHeaderFilterButton=True,
    cellStyle={"textAlign": "center"},
)

largura_lineup = max(int(np.ceil(float(agg["Lineup"].apply(medir_largura_texto_px).max()))) + 16, 95)
gb.configure_column(
    "Lineup",
    headerName="LINEUP",
    pinned="left",
    width=largura_lineup,
    minWidth=largura_lineup,
    cellStyle={"textAlign": "left", "fontWeight": "500"},
)

gb.configure_column(
    "Time",
    headerName="Time",
    pinned="left",
    width=48,
    minWidth=48,
    cellStyle={
        "textAlign": "center",
        "fontFamily": "Consolas, 'Courier New', monospace",
        "fontSize": "13px",
    },
)

for col in tabela.columns:
    if col in ("Lineup", "Time"):
        continue

    titulo = col.strip()
    estilo = {"textAlign": "center"}
    if col in cols_verdes:
        estilo["backgroundColor"] = "rgba(46, 204, 113, 0.16)"
    elif col in cols_vermelhas:
        estilo["backgroundColor"] = "rgba(231, 76, 60, 0.16)"

    largura = 40 if len(titulo) <= 3 else (46 if len(titulo) <= 5 else 56)
    fmt = fmt_int if fmt_decimais == 0 else fmt_dec1

    if titulo in ("+/-", "NETRTG"):
        fmt, largura = (fmt_pm_int if fmt_decimais == 0 else fmt_pm_dec), 48
    elif titulo == "JO":
        fmt, largura = fmt_int, 36
    elif "FTA Rate" in titulo:
        fmt, largura = fmt_dec3, 58
    elif "%" in titulo:
        fmt, largura = fmt_pct, 48
    elif titulo in ("PACE", "OFFRTG", "DEFRTG"):
        fmt, largura = fmt_dec1, 52
    elif titulo == "Min.":
        fmt, largura = fmt_dur, 48

    gb.configure_column(
        col,
        headerName=titulo,
        cellStyle=estilo,
        valueFormatter=fmt,
        width=largura,
        minWidth=largura,
    )

refresh_rank_js = JsCode("function(params) { params.api.refreshCells({columns: ['rank_col'], force: true}); }")

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
grid_options["columnDefs"].insert(
    0,
    {
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
        "cellStyle": {"textAlign": "center", "fontWeight": "600", "color": "#334155"},
    },
)

custom_css = {
    ".ag-root-wrapper": {
        "border": "1px solid #94a3b8 !important",
        "border-radius": "6px !important",
    },
    ".ag-header": {
        "border-bottom": "1px solid #cbd5e1 !important",
    },
    ".ag-row": {
        "border-bottom": "none !important",
    },
    ".ag-header-cell, .ag-cell": {
        "padding-left": "2px !important",
        "padding-right": "2px !important",
        "border-right": "1px solid #cbd5e1 !important",
        "font-size": "12.5px !important",
    },
    ".ag-cell": {
        "border-bottom": "1px solid #cbd5e1 !important",
    },
    ".ag-pinned-left-cols-container, .ag-pinned-left-header": {
        "border-right": "none !important",
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
    ".ag-pinned-left-cols-container .ag-cell[col-id='Time']": {
        "font-size": "13px !important",
    },
    ".ag-header-cell-menu-button, .ag-header-cell-filter-button": {
        "display": "none !important",
    },
}

altura_tabela = min(max(len(tabela) * 29 + 37, 180), 520)
grid_key = f"grid_{modo_exibicao}_{tamanho_comb}_{mando_sel}_{len(agg)}_{agg['DUR_S'].sum()}"

AgGrid(
    tabela,
    key=grid_key,
    gridOptions=grid_options,
    height=altura_tabela,
    theme="alpine",
    allow_unsafe_jscode=True,
    custom_css=custom_css,
    fit_columns_on_grid_load=False,
)

exibir_banner("footerNBB", tipo="footer")
