import streamlit as st
import pandas as pd
import os
import glob
import re
import altair as alt
import numpy as np
from ui_components import apply_modern_style, metric_card
from data_loader import load_files_in_parallel

# Configuração da página
st.set_page_config(
    page_title="Dashboard de Ciclo de Vida - Manobras",
    layout="wide",
    initial_sidebar_state="expanded"
)
apply_modern_style()

# Caminho dos arquivos
BASE_PATH = r"i:\IT\ODCO\PUBLICA\Kennedy\Projetos\works_analyzer\mesao"

# --- Funções de Carregamento e Processamento ---

@st.cache_data
def load_all_history():
    """
    Carrega todos os arquivos da pasta para reconstruir o histórico de cada solicitação.
    Retorna um DataFrame contendo: Solicitação, Status, Data Arquivo, Região.
    """
    all_files = glob.glob(os.path.join(BASE_PATH, "*.xlsx"))
    
    file_list = []
    
    for file_path in all_files:
        filename = os.path.basename(file_path)
        
        # Extrair data do arquivo
        file_date = None
        match1 = re.search(r"(\d{2})(\d{2})(\d{4})", filename)
        match2 = re.search(r"(\d{2})_(\d{2})_(\d{2})", filename)
        
        if match1:
            file_date = pd.to_datetime(f"{match1.group(3)}-{match1.group(2)}-{match1.group(1)}")
        elif match2:
            file_date = pd.to_datetime(f"20{match2.group(3)}-{match2.group(2)}-{match2.group(1)}")
            
        if file_date:
            file_list.append({
                "path": file_path, 
                "Data Arquivo": file_date, 
                "Nome Arquivo": filename
            })

    # Colunas essenciais
    cols_needed = ["Solicitação", "Status Solicitação", "Região", "Executor", "Data de início"]
    
    # Carregamento paralelo
    full_df = load_files_in_parallel(file_list, usecols=cols_needed)
    
    if full_df.empty:
        return pd.DataFrame()
        
    # Status de interesse para o ciclo
    relevant_statuses = [
        "APROVADA", 
        "EM ELABORACAO", 
        "ELABORADA", 
        "ENVIADA PARA O CONDIS"
    ]
    
    # Filtrar apenas status relevantes para reduzir memória
    if "Status Solicitação" in full_df.columns:
        full_df = full_df[full_df["Status Solicitação"].isin(relevant_statuses)].copy()
    
    if full_df.empty:
        return pd.DataFrame()
    
    # Garantir tipos
    if "Solicitação" in full_df.columns:
        full_df["Solicitação"] = full_df["Solicitação"].astype(str)
    
    if "Data Arquivo" in full_df.columns:
        full_df["Data Arquivo"] = pd.to_datetime(full_df["Data Arquivo"])
        
    if "Data de início" in full_df.columns:
        full_df["Data de início"] = pd.to_datetime(full_df["Data de início"], errors='coerce')
    
    return full_df


def calculate_cycle_time(df_history):
    """
    Calcula o tempo de ciclo para cada solicitação.
    Ciclo: Data da primeira aparição como APROVADA -> Data da primeira aparição como ENVIADA PARA O CONDIS
    """
    if df_history.empty:
        return pd.DataFrame()

    # Ordenar por data
    df_history = df_history.sort_values("Data Arquivo")
    
    # Identificar a primeira data de cada status para cada solicitação
    status_dates = df_history.groupby(["Solicitação", "Status Solicitação"])["Data Arquivo"].min().reset_index()
    
    # Pivotar para ter colunas de data para cada status
    pivot_dates = status_dates.pivot(index="Solicitação", columns="Status Solicitação", values="Data Arquivo").reset_index()
    
    # Se alguma coluna não existir, criar com NaT
    for status in ["APROVADA", "EM ELABORACAO", "ELABORADA", "ENVIADA PARA O CONDIS"]:
        if status not in pivot_dates.columns:
            pivot_dates[status] = pd.NaT
            
    # Calcular tempo de ciclo total (em dias)
    pivot_dates["Ciclo Total (Dias)"] = (pivot_dates["ENVIADA PARA O CONDIS"] - pivot_dates["APROVADA"]).dt.days
    
    # Calcular tempos intermediários (Lead Time Breakdown)
    # Aprovada -> Em Elaboração
    pivot_dates["Tempo Espera (Dias)"] = (pivot_dates["EM ELABORACAO"] - pivot_dates["APROVADA"]).dt.days
    # Em Elaboração -> Elaborada
    pivot_dates["Tempo Execução (Dias)"] = (pivot_dates["ELABORADA"] - pivot_dates["EM ELABORACAO"]).dt.days
    # Elaborada -> Enviada
    pivot_dates["Tempo Envio (Dias)"] = (pivot_dates["ENVIADA PARA O CONDIS"] - pivot_dates["ELABORADA"]).dt.days
    
    # Recuperar Região e Data de Início
    # Vamos pegar a região e data de início do registro mais recente dessa solicitação
    latest_info = df_history.sort_values("Data Arquivo", ascending=False).drop_duplicates("Solicitação")[["Solicitação", "Região", "Executor", "Data de início"]]
    
    result_df = pivot_dates.merge(latest_info, on="Solicitação", how="left")
    
    # Calcular Dias Úteis de Antecedência (Aprovada -> Data de Início)
    # Importante: Data Aprovação vs Data Início Manobra
    # np.busday_count requer datetime64[D]
    
    # Função auxiliar segura para busday_count
    def calc_busdays(row):
        start = row["APROVADA"]
        end = row["Data de início"]
        
        if pd.isna(start) or pd.isna(end):
            return None
            
        try:
            d_start = start.date()
            d_end = end.date()
            if d_start > d_end:
                return -1 # Data de aprovação depois do início (erro de dado ou emergência)
            return np.busday_count(d_start, d_end)
        except:
            return None

    result_df["Dias Antecedência"] = result_df.apply(calc_busdays, axis=1)
    
    return result_df

# --- Interface Principal ---

st.title("⏱️ Análise de Ciclo de Vida (Lead Time)")
st.markdown("Monitoramento do tempo entre **APROVADA** e **ENVIADA PARA O CONDIS**.")
st.caption("Filtro Ativo: Apenas solicitações com **até 11 dias úteis** de antecedência (Aprovada -> Início).")

with st.spinner("Analisando histórico completo dos arquivos..."):
    # Carregar dados brutos
    df_raw_history = load_all_history()

if df_raw_history.empty:
    st.error("Não foi possível carregar dados. Verifique o diretório 'mesao'.")
else:
    # Processar Ciclos
    # Identificar range de datas do dataset
    min_date_avail = df_raw_history["Data Arquivo"].min().date()
    max_date_avail = df_raw_history["Data Arquivo"].max().date()
    
    # --- Sidebar com Filtros ---
    st.sidebar.header("Filtros")
    
    # Filtro de Período
    selected_dates = st.sidebar.date_input(
        "Selecione o Período:",
        value=(min_date_avail, max_date_avail),
        min_value=min_date_avail,
        max_value=max_date_avail
    )
    
    # Aplicar filtro de datas no dataframe bruto antes de calcular ciclos
    # Se o usuário selecionar apenas uma data, o date_input retorna um objeto date, não tupla
    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        start_date, end_date = selected_dates
        df_raw_history = df_raw_history[
            (df_raw_history["Data Arquivo"].dt.date >= start_date) & 
            (df_raw_history["Data Arquivo"].dt.date <= end_date)
        ]
        st.markdown(f"**Período Analisado:** {start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')}")
    else:
        st.warning("Selecione uma data inicial e final.")
        st.markdown(f"**Período Disponível:** {min_date_avail.strftime('%d/%m/%Y')} até {max_date_avail.strftime('%d/%m/%Y')}")

    df_cycles = calculate_cycle_time(df_raw_history)
    
    # Filtrar apenas os que completaram o ciclo TOTAL (têm data de início e fim)
    completed_cycles = df_cycles.dropna(subset=["Ciclo Total (Dias)"]).copy()
    
    # Filtrar ciclos negativos (inconsistências de dados)
    completed_cycles = completed_cycles[completed_cycles["Ciclo Total (Dias)"] >= 0]
    
    # --- NOVO FILTRO: Apenas <= 11 dias úteis de antecedência ---
    # Garantir que temos a coluna e filtrar
    if "Dias Antecedência" in completed_cycles.columns:
        total_antes_filtro = len(completed_cycles)
        # Filtrar antecedência <= 11 dias E >= 0 (para remover erros de data futura)
        completed_cycles = completed_cycles[
            (completed_cycles["Dias Antecedência"] <= 11) & 
            (completed_cycles["Dias Antecedência"] >= 0)
        ]
        filtrados_count = total_antes_filtro - len(completed_cycles)
        if filtrados_count > 0:
            st.info(f"Ocultadas {filtrados_count} solicitações com antecedência superior a 11 dias úteis.")
    
    # Lista de todas as regiões disponíveis
    all_regions = sorted(df_cycles["Região"].dropna().unique())
    
    selected_regions = st.sidebar.multiselect(
        "Selecione as Regiões:",
        options=all_regions,
        default=all_regions
    )
    
    # Aplicar filtro de Região
    if selected_regions:
        # Filtrar tanto os ciclos concluídos quanto os dados gerais
        df_cycles = df_cycles[df_cycles["Região"].isin(selected_regions)]
        completed_cycles = completed_cycles[completed_cycles["Região"].isin(selected_regions)]
    else:
        st.warning("Selecione ao menos uma região.")
        
    # --- Métricas Principais ---
    st.divider()
    
    col1, col2, col3, col4 = st.columns(4)
    
    if not completed_cycles.empty:
        avg_cycle = completed_cycles["Ciclo Total (Dias)"].mean()
        median_cycle = completed_cycles["Ciclo Total (Dias)"].median()
        total_completed = len(completed_cycles)
        
        # Breakdown médio
        avg_wait = completed_cycles["Tempo Espera (Dias)"].mean()
        avg_exec = completed_cycles["Tempo Execução (Dias)"].mean()
        avg_send = completed_cycles["Tempo Envio (Dias)"].mean()
    else:
        avg_cycle = 0
        median_cycle = 0
        total_completed = 0
        avg_wait = 0
        avg_exec = 0
        avg_send = 0
    
    # Solicitações em andamento (Aprovadas mas não enviadas)
    in_progress = df_cycles[df_cycles["APROVADA"].notna() & df_cycles["ENVIADA PARA O CONDIS"].isna()]
    total_in_progress = len(in_progress)

    with col1:
        metric_card("Tempo Médio Total", f"{avg_cycle:.1f}", suffix=" dias")
    with col2:
        metric_card("Mediana do Ciclo", f"{median_cycle:.0f}", suffix=" dias")
    with col3:
        metric_card("Ciclos Concluídos", total_completed)
    with col4:
        metric_card("Em Andamento", total_in_progress)
    
    st.divider()
    
    # --- Visualizações ---
    
    st.markdown("### 📊 Comparativo por Região")
    
    if not completed_cycles.empty:
        # Calcular média por região
        region_comparison = completed_cycles.groupby("Região")["Ciclo Total (Dias)"].mean().reset_index()
        region_comparison = region_comparison.sort_values("Ciclo Total (Dias)", ascending=False)
        
        # Gráfico de barras comparativo
        chart_regions = alt.Chart(region_comparison).mark_bar().encode(
            x=alt.X("Região", sort="-y", title=None),
            y=alt.Y("Ciclo Total (Dias)", title="Média de Dias"),
            color=alt.condition(
                alt.datum["Ciclo Total (Dias)"] > avg_cycle,
                alt.value("#ff4b4b"),  # Vermelho se acima da média geral
                alt.value("#1f77b4")   # Azul se abaixo
            ),
            tooltip=["Região", alt.Tooltip("Ciclo Total (Dias)", format=".1f")]
        ).properties(height=400)
        
        # Linha de média geral
        rule = alt.Chart(pd.DataFrame({'y': [avg_cycle]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y')
        
        st.altair_chart((chart_regions + rule), use_container_width=True)
        st.caption("🔴 Barras vermelhas indicam regiões com tempo acima da média geral.")
    else:
        st.info("Sem dados para comparação regional.")

    st.divider()
    
    # --- GRÁFICO 1: Tempo por Etapa (Geral) ---
    st.markdown("### ⏳ Tempo por Etapa (Média Geral)")
    
    # Criar dataframe para o gráfico de etapas
    stages_data = pd.DataFrame({
        "Etapa": ["Análise", "Elaboração", "Envio"],
        "Descrição": [
            "Aprovada → Em Elaboração", 
            "Em Elaboração → Elaborada", 
            "Elaborada → Enviada"
        ],
        "Dias": [avg_wait, avg_exec, avg_send],
        "Ordem": [1, 2, 3]
    })
    
    # Gráfico de Barras para mostrar o tempo médio
    bar_stages = alt.Chart(stages_data).mark_bar().encode(
        x=alt.X("Etapa", sort=["Análise", "Elaboração", "Envio"], title=None),
        y=alt.Y("Dias", title="Média de Dias"),
        color=alt.Color("Etapa", legend=None),
        tooltip=["Etapa", "Descrição", alt.Tooltip("Dias", format=".1f")]
    ).properties(height=350)
    
    st.altair_chart(bar_stages, use_container_width=True)
    
    # Legenda explicativa manual
    st.caption("**Entenda as etapas:**")
    st.markdown("""
    - **Análise:** Tempo entre *Aprovada* e começar a fazer (*Em Elaboração*).
    - **Elaboração:** Tempo fazendo (*Em Elaboração* até *Elaborada*).
    - **Envio:** Tempo entre terminar (*Elaborada*) e enviar (*Enviada p/ Condis*).
    """)

    st.divider()

    # --- GRÁFICO 2: Detalhamento por Região com Seletor ---
    st.markdown("### 📊 Detalhamento de Etapas por Região")
    
    if not completed_cycles.empty:
        # Calcular médias das 3 etapas por região
        metrics_by_region = completed_cycles.groupby("Região")[
            ["Tempo Espera (Dias)", "Tempo Execução (Dias)", "Tempo Envio (Dias)"]
        ].mean().reset_index()
        
        # Renomear colunas
        metrics_by_region = metrics_by_region.rename(columns={
            "Tempo Espera (Dias)": "Análise",
            "Tempo Execução (Dias)": "Elaboração",
            "Tempo Envio (Dias)": "Envio"
        })

        # Layout: Coluna de Checkboxes (Direita) e Gráfico (Esquerda)
        # O usuário pediu "ao lado um painel", vamos fazer 3 colunas: Gráfico (2) | Espaço (0.2) | Seletor (1)
        col_graph, col_spacer, col_select = st.columns([3, 0.2, 1])

        with col_select:
            st.markdown("#### Regiões")
            
            # Lista de regiões disponíveis neste dataset filtrado
            avail_regions = sorted(metrics_by_region["Região"].unique())
            
            # Criar dataframe para o seletor (necessário para st.dataframe com seleção)
            df_selector = pd.DataFrame({"Região": avail_regions})
            
            # Definir padrão: top 5 regiões (se houver)
            # st.dataframe com on_select retorna os índices das linhas selecionadas
            # Precisamos pré-selecionar as 5 primeiras linhas
            default_indices = list(range(min(5, len(avail_regions))))
            
            # Configuração do dataframe interativo
            # A partir do Streamlit 1.35+, on_select retorna um objeto SelectionState
            event = st.dataframe(
                df_selector,
                use_container_width=True,
                hide_index=True,
                height=350, # Altura fixa para scroll (alinhar com gráfico)
                on_select="rerun", # Atualiza automaticamente
                selection_mode="multi-row",
                key="region_selection"
            )
            
            # Recuperar regiões selecionadas
            try:
                selected_indices = event.selection.rows
            except AttributeError:
                 # Fallback para versões antigas ou se o objeto não tiver o atributo esperado
                 selected_indices = []

            # Se nada selecionado pelo usuário, usar o default (primeira carga ou deseleção total)
            # O comportamento do st.dataframe é iniciar vazio se não tiver default especificado?
            # Infelizmente st.dataframe não tem parâmetro 'default_selection' direto para linhas.
            # Workaround: Se a seleção estiver vazia, assumimos as top 5 para não quebrar o gráfico.
            # Mas se o usuário quiser limpar tudo? Vamos assumir que vazio = top 5 para garantir usabilidade.
            
            if not selected_indices:
                 selected_regions_chart = [avail_regions[i] for i in default_indices]
                 st.caption("Mostrando top 5 padrão. Selecione na lista para personalizar.")
            else:
                 selected_regions_chart = df_selector.iloc[selected_indices]["Região"].tolist()

        with col_graph:
            if selected_regions_chart:
                # Filtrar o dataframe
                filtered_metrics = metrics_by_region[metrics_by_region["Região"].isin(selected_regions_chart)]
                
                # Derreter (melt)
                melted_metrics = filtered_metrics.melt(
                    id_vars="Região", 
                    var_name="Etapa", 
                    value_name="Dias"
                )
                
                # Gráfico
                chart_grouped = alt.Chart(melted_metrics).mark_bar().encode(
                    x=alt.X("Etapa", axis=None, sort=["Análise", "Elaboração", "Envio"]), 
                    y=alt.Y("Dias", title="Média de Dias"),
                    color=alt.Color("Etapa", title="Fase"),
                    column=alt.Column("Região", header=alt.Header(titleOrient="bottom", labelOrient="bottom")),
                    tooltip=["Região", "Etapa", alt.Tooltip("Dias", format=".1f")]
                ).properties(width=60) # Um pouco mais largo
                
                st.altair_chart(chart_grouped)
            else:
                st.info("Nenhuma região selecionada.")

    else:
        st.info("Sem dados suficientes para o gráfico.")

    # --- Detalhamento ---
    st.markdown("### 📋 Detalhes das Solicitações Concluídas")
    
    if not completed_cycles.empty:
        st.dataframe(
            completed_cycles[["Solicitação", "Região", "Executor", "APROVADA", "ENVIADA PARA O CONDIS", "Ciclo Total (Dias)"]]
            .sort_values("Ciclo Total (Dias)", ascending=False),
            use_container_width=True,
            column_config={
                "APROVADA": st.column_config.DateColumn("Data Aprovação", format="DD/MM/YYYY"),
                "ENVIADA PARA O CONDIS": st.column_config.DateColumn("Data Envio", format="DD/MM/YYYY"),
                "Ciclo Total (Dias)": st.column_config.NumberColumn("Dias Totais", format="%.0f"),
            }
        )
