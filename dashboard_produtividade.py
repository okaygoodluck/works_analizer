import streamlit as st
import pandas as pd
import os
import glob
import re
import altair as alt
from ui_components import apply_modern_style, metric_card
from data_loader import load_files_in_parallel

# Configuração da página
st.set_page_config(
    page_title="Dashboard de Produtividade - Transições",
    layout="wide",
    initial_sidebar_state="expanded"
)
apply_modern_style()

# Caminho dos arquivos
BASE_PATH = r"i:\IT\ODCO\PUBLICA\Kennedy\Projetos\works_analyzer\mesao"

# --- Funções Auxiliares ---

@st.cache_data
def get_available_dates():
    """
    Lista todos os arquivos na pasta e extrai as datas disponíveis.
    Retorna um dicionário {datetime.date: filename}
    """
    all_files = glob.glob(os.path.join(BASE_PATH, "*.xlsx"))
    date_map = {}
    
    for file_path in all_files:
        filename = os.path.basename(file_path)
        
        # Padrões de data
        match1 = re.search(r"(\d{2})(\d{2})(\d{4})", filename)
        match2 = re.search(r"(\d{2})_(\d{2})_(\d{2})", filename)
        
        file_date = None
        if match1:
            file_date = pd.to_datetime(f"{match1.group(3)}-{match1.group(2)}-{match1.group(1)}").date()
        elif match2:
            file_date = pd.to_datetime(f"20{match2.group(3)}-{match2.group(2)}-{match2.group(1)}").date()
            
        if file_date:
            date_map[file_date] = file_path
            
    return date_map

def calcular_peso_row(row):
    peso = row["Peso"]
    clientes = row["Clientes"] if pd.notna(row["Clientes"]) else 0
    ple = row["PLE"]
    recursos = str(row["Recursos"]).upper() if pd.notna(row["Recursos"]) else ""
    
    # Regra 1: Se for PLE e tiver MANOBRA INFORMATIVA -> Peso 1
    if ple == "PLE" and "MANOBRA INFORMATIVA" in recursos:
        return 1
    
    # Regra 2: Se peso vazio e em PLE estiver PLE -> Peso 'PLE'
    if pd.isna(peso) and ple == "PLE":
        return "PLE"
        
    # Regra 3: Se peso for 1 mas clientes for 0 -> Peso 3
    if peso == 1 and clientes == 0:
        return 3
        
    return peso

def process_weight_logic(df):
    """Aplica a lógica de cálculo de peso e formatação de colunas."""
    if df.empty:
        return df
        
    # Garantir colunas necessárias
    cols = ["Solicitação", "Status Solicitação", "Região", "Peso", "Clientes", "PLE", "Recursos"]
    for col in cols:
        if col not in df.columns:
            df[col] = None

    # Converter Solicitação para string
    if "Solicitação" in df.columns:
        df["Solicitação"] = df["Solicitação"].astype(str)
    
    df["Peso Calculado"] = df.apply(calcular_peso_row, axis=1)
    return df

@st.cache_data
def load_data_parallel_cached(file_list):
    """Carrega arquivos em paralelo com cache do Streamlit."""
    cols_needed = ["Solicitação", "Status Solicitação", "Região", "Peso", "Clientes", "PLE", "Recursos"]
    return load_files_in_parallel(file_list, usecols=cols_needed)

def process_transitions(df_start, df_end):
    """Compara dois dataframes e identifica transições."""
    # Renomear colunas para identificar origem (Start) e destino (End)
    df_s = df_start[["Solicitação", "Status Solicitação", "Região", "Peso Calculado"]].rename(
        columns={"Status Solicitação": "Status Inicial", "Peso Calculado": "Peso Inicial"}
    )
    df_e = df_end[["Solicitação", "Status Solicitação", "Peso Calculado"]].rename(
        columns={"Status Solicitação": "Status Final", "Peso Calculado": "Peso Final"}
    )
    
    # Merge (Inner join para pegar apenas o que existe nos dois)
    merged = pd.merge(df_s, df_e, on="Solicitação", how="inner")
    
    return merged

# --- Interface Principal ---

st.title("🚀 Análise de Produtividade Diária")
st.markdown("Comparação de status entre duas datas para identificar o trabalho realizado.")

# 1. Seleção de Datas
date_map = get_available_dates()
available_dates = sorted(date_map.keys(), reverse=True)

if len(available_dates) < 2:
    st.error("É necessário ter pelo menos 2 arquivos na pasta 'mesao' para comparar.")
    st.stop()

col_date1, col_date2 = st.columns(2)

with col_date1:
    date_start = st.selectbox("Data Inicial (Ontem/Anterior):", available_dates, index=1 if len(available_dates) > 1 else 0)

with col_date2:
    date_end = st.selectbox("Data Final (Hoje/Atual):", available_dates, index=0)

if date_start == date_end:
    st.warning("Selecione datas diferentes para comparação.")
    st.stop()

if date_start > date_end:
    st.error("A Data Inicial deve ser anterior à Data Final.")
    st.stop()

# 2. Carregamento e Processamento
file_start = date_map[date_start]
file_end = date_map[date_end]

with st.spinner("Carregando e processando arquivos em paralelo..."):
    # Preparar lista para carga paralela
    file_list = [
        {"path": file_start, "type": "start"},
        {"path": file_end, "type": "end"}
    ]
    cols_needed = ["Solicitação", "Status Solicitação", "Região", "Peso", "Clientes", "PLE", "Recursos"]
    
    # Carregar ambos de uma vez
    df_all = load_files_in_parallel(file_list, usecols=cols_needed)
    
    if df_all.empty:
        st.error("Falha ao carregar dados.")
        st.stop()
        
    # Separar os dataframes
    # O data_loader injeta metadados, então podemos filtrar por 'path' ou 'type'
    df_start_raw = df_all[df_all["type"] == "start"].copy()
    df_end_raw = df_all[df_all["type"] == "end"].copy()
    
    # Processar lógica de peso individualmente
    df_start = process_weight_logic(df_start_raw)
    df_end = process_weight_logic(df_end_raw)
    
    if df_start.empty or df_end.empty:
        st.error("Falha ao processar dados de um dos arquivos.")
        st.stop()
        
    df_transitions = process_transitions(df_start, df_end)

# 3. Definição das Transições de Interesse
target_transitions = [
    ("APROVADA", "EM ELABORACAO"),
    ("APROVADA", "ELABORADA"), # Pulo de etapa?
    ("APROVADA", "ENVIADA PARA O CONDIS"), # Pulo duplo
    ("APROVADA", "REPROVADA"), # Nova
    ("EM ELABORACAO", "ELABORADA"),
    ("EM ELABORACAO", "ENVIADA PARA O CONDIS"), # Pulo
    ("EM ELABORACAO", "REPROVADA"), # Nova
    ("ELABORADA", "ENVIADA PARA O CONDIS"),
    ("ELABORADA", "REPROVADA") # Nova
]

# Criar coluna de Transição legível
df_transitions["Transição"] = df_transitions["Status Inicial"] + " -> " + df_transitions["Status Final"]

# Filtrar apenas as transições de interesse
# Criar lista de strings "DE -> PARA" baseada na tupla target_transitions
valid_transitions_str = [f"{t[0]} -> {t[1]}" for t in target_transitions]
df_filtered = df_transitions[df_transitions["Transição"].isin(valid_transitions_str)].copy()

# --- Aplicar Categorização Personalizada ---
def categorizar_transicao(row):
    status_final = row["Status Final"]
    
    if status_final == "REPROVADA":
        return "Reprovadas"
    elif status_final == "ENVIADA PARA O CONDIS":
        return "Enviadas"
    elif status_final in ["EM ELABORACAO", "ELABORADA"]:
        return "Clicadas"
    
    return "Outros"

def normalize_peso(val):
    if pd.isna(val) or val == "":
        return "N/A"
    try:
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val)
    except:
        return str(val)

df_filtered["Categoria Transição"] = df_filtered.apply(categorizar_transicao, axis=1)

if df_filtered.empty:
    st.info("Nenhuma transição de interesse encontrada neste período.")
    st.stop()

# --- Visualizações ---

st.divider()

# KPI Totais
total_movimentacoes = len(df_filtered)
metric_card("Total de Movimentações (Status de Interesse)", total_movimentacoes)

# --- Análise Unificada (Região e Peso) ---
st.subheader("📊 Análise de Produtividade")

# Layout: Gráfico Região (Esq) | Gráfico Peso (Dir)
# Removida coluna dedicada ao seletor para ganhar espaço
# O seletor agora é um multiselect no topo

# Preparação dos dados
grouped_region = df_filtered.groupby(["Região", "Categoria Transição"]).size().reset_index(name="Quantidade")
df_filtered["Peso Label"] = df_filtered["Peso Final"].apply(normalize_peso)
grouped_weight = df_filtered.groupby(["Região", "Peso Label", "Categoria Transição"]).size().reset_index(name="Quantidade")

# 1. Seletor de Regiões (Estilo Multiselect)
avail_regions = sorted(grouped_region["Região"].unique())
default_regions = avail_regions[:5] if len(avail_regions) >= 5 else avail_regions

selected_regions = st.multiselect(
    "Filtrar Regiões para os Gráficos:",
    options=avail_regions,
    default=default_regions,
    key="chart_region_filter"
)

# 2. Gráficos Lado a Lado
col_graph_reg, col_graph_weight = st.columns(2)

with col_graph_reg:
    st.markdown("##### Por Região")
    if selected_regions:
        grouped_region_filtered = grouped_region[grouped_region["Região"].isin(selected_regions)]
        
        # Gráfico compacto sem faceting para economizar espaço
        chart_region = alt.Chart(grouped_region_filtered).mark_bar(size=25).encode(
            x=alt.X("Região:N", title="Região", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Quantidade:Q", title="Qtd"),
            color=alt.Color("Categoria Transição:N", 
                            title="Status",
                            scale=alt.Scale(domain=["Clicadas", "Enviadas", "Reprovadas"], range=["#1f77b4", "#2ca02c", "#d62728"])),
            tooltip=["Região", "Categoria Transição", "Quantidade"]
        ).properties(height=300)
        
        st.altair_chart(chart_region, use_container_width=True)
    else:
        st.info("Selecione regiões.")

with col_graph_weight:
    st.markdown("##### Por Peso")
    if selected_regions:
        grouped_weight_filtered = grouped_weight[grouped_weight["Região"].isin(selected_regions)]

        # Gráfico de peso compacto (Agrupado por Peso, empilhado por Status)
        # Removemos o faceting por região aqui para caber na coluna lateral
        # Se quiser ver por região, o usuário usa o filtro
        grouped_weight_agg = grouped_weight_filtered.groupby(["Peso Label", "Categoria Transição"]).sum().reset_index()

        chart_weight = alt.Chart(grouped_weight_agg).mark_bar(size=25).encode(
            x=alt.X("Peso Label:N", title="Peso"),
            y=alt.Y("Quantidade:Q", title=""),
            color=alt.Color("Categoria Transição:N", title="Status"),
            tooltip=["Peso Label", "Categoria Transição", "Quantidade"]
        ).properties(height=300)

        st.altair_chart(chart_weight, use_container_width=True)
    else:
        st.info("Selecione regiões.")

# Tabelas Detalhadas (Abaixo dos gráficos)
col_det1, col_det2 = st.columns(2)

with col_det1:
    with st.expander("Ver dados detalhados por Região"):
        pivot_region = grouped_region.pivot(index="Região", columns="Categoria Transição", values="Quantidade").fillna(0)
        st.dataframe(pivot_region, use_container_width=True)

with col_det2:
    with st.expander("Ver detalhamento de Pesos por Categoria"):
        pivot_weight = grouped_weight.pivot_table(
            index=["Região", "Peso Label"], 
            columns="Categoria Transição", 
            values="Quantidade", 
            fill_value=0
        ).astype(int)
        pivot_weight["Total"] = pivot_weight.sum(axis=1)
        st.dataframe(pivot_weight, use_container_width=True)

# --- Lista de Solicitações ---
st.divider()
st.subheader("📋 Listagem das Solicitações Movimentadas")

# Filtro global de Região
col_f1, col_f2 = st.columns([1, 2])
with col_f1:
    filter_reg_list = st.multiselect("Filtrar Região para as Listas:", options=sorted(df_filtered["Região"].dropna().unique()), key="list_reg_filter")

# Separar DataFrames por categoria
df_clicadas = df_filtered[df_filtered["Categoria Transição"] == "Clicadas"].copy()
df_enviadas = df_filtered[df_filtered["Categoria Transição"] == "Enviadas"].copy()
df_reprovadas = df_filtered[df_filtered["Categoria Transição"] == "Reprovadas"].copy()

# Aplicar filtro de região se houver
if filter_reg_list:
    df_clicadas = df_clicadas[df_clicadas["Região"].isin(filter_reg_list)]
    df_enviadas = df_enviadas[df_enviadas["Região"].isin(filter_reg_list)]
    df_reprovadas = df_reprovadas[df_reprovadas["Região"].isin(filter_reg_list)]

# Criar Abas
tab_clicadas, tab_enviadas, tab_reprovadas = st.tabs(["🔵 Clicadas", "🟢 Enviadas", "🔴 Reprovadas"])

cols_to_show = ["Solicitação", "Região", "Transição", "Peso Final"]

with tab_clicadas:
    st.markdown(f"**Total: {len(df_clicadas)}**")
    st.dataframe(
        df_clicadas[cols_to_show],
        use_container_width=True,
        hide_index=True
    )

with tab_enviadas:
    st.markdown(f"**Total: {len(df_enviadas)}**")
    st.dataframe(
        df_enviadas[cols_to_show],
        use_container_width=True,
        hide_index=True
    )

with tab_reprovadas:
    st.markdown(f"**Total: {len(df_reprovadas)}**")
    st.dataframe(
        df_reprovadas[cols_to_show],
        use_container_width=True,
        hide_index=True
    )
