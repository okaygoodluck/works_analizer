import streamlit as st
import pandas as pd
import os
import glob
import re
import numpy as np
import altair as alt
from datetime import datetime
from ui_components import apply_modern_style, metric_card
from data_loader import load_files_in_parallel

# Configuração da página
st.set_page_config(
    page_title="Dashboard de Análise de Prazos - Manobras",
    layout="wide",
    initial_sidebar_state="expanded"
)
apply_modern_style()

# Caminho dos arquivos
BASE_PATH = r"i:\IT\ODCO\PUBLICA\Kennedy\Projetos\works_analyzer\mesao"

# Funções de extração e processamento
@st.cache_data
def load_data():
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
    
    if not file_list:
        return pd.DataFrame()

    # Colunas necessárias
    cols = ["Status Solicitação", "Data de início", "Solicitação", "Executor", "Região"]
    
    # Carregamento paralelo
    final_df = load_files_in_parallel(file_list, usecols=cols)
    
    if final_df.empty:
        return pd.DataFrame()

    # Filtrar apenas APROVADA
    if "Status Solicitação" in final_df.columns:
        final_df = final_df[final_df["Status Solicitação"] == "APROVADA"].copy()
    
    # Processamento de datas e cálculo de dias úteis
    final_df["Data de início"] = pd.to_datetime(final_df["Data de início"])
    
    # Calcular dias úteis entre Data Arquivo e Data de Início
    # np.busday_count conta dias úteis entre datas (exclusivo final, por isso o ajuste pode ser necessário dependendo da regra exata)
    # Regra: Se a manobra foi enviada no dia X (Data Arquivo) para início no dia Y
    
    # Converter para datetime64[D] (apenas data, sem hora) para o numpy
    dates_arquivo = final_df["Data Arquivo"].values.astype('datetime64[D]')
    dates_inicio = final_df["Data de início"].values.astype('datetime64[D]')
    
    # Calcular diferença em dias úteis
    final_df["Dias Úteis"] = np.busday_count(dates_arquivo, dates_inicio)
    
    # Classificação
    def classificar(dias):
        if dias < 8:
            return "FORA DO PRAZO"
        elif dias == 8:
            return "ALERTA"
        else:
            return "NO PRAZO"
            
    final_df["Status Prazo"] = final_df["Dias Úteis"].apply(classificar)

    # Identificar motivo do atraso
    # Ordenar por data do arquivo para garantir ordem cronológica
    final_df = final_df.sort_values("Data Arquivo")

    # Criar coluna para motivo (inicialmente vazia)
    final_df["Motivo Atraso"] = None

    # Agrupar por arquivo para processamento eficiente
    unique_files = final_df["Nome Arquivo"].unique()
    file_dates = final_df[["Nome Arquivo", "Data Arquivo"]].drop_duplicates().sort_values("Data Arquivo")
    
    # Criar um dicionário mapeando cada data de arquivo para seus 3 arquivos anteriores
    file_history = {}
    sorted_files = file_dates["Nome Arquivo"].tolist()
    
    for i, current_file in enumerate(sorted_files):
        # Pegar até 3 arquivos anteriores
        start_idx = max(0, i - 3)
        previous_files = sorted_files[start_idx:i]
        file_history[current_file] = previous_files

    # Iterar sobre as linhas que estão FORA DO PRAZO para definir o motivo
    # OBS: Isso pode ser lento se o DF for muito grande, mas para o escopo atual deve servir.
    # Otimização: Fazer isso apenas para o dia selecionado seria mais rápido, 
    # mas como precisamos carregar tudo para histórico, faremos no load_data ou sob demanda.
    # Faremos sob demanda na exibição para não travar o carregamento inicial.
    
    return final_df

@st.cache_data
def check_delay_reason(df_full, current_file_name):
    # Filtrar dados do arquivo atual
    df_current = df_full[df_full["Nome Arquivo"] == current_file_name].copy()
    
    # Se não tiver atrasos, retorna o df original
    if df_current.empty:
        return df_current

    # Identificar manobras fora do prazo
    mask_atraso = df_current["Status Prazo"] == "FORA DO PRAZO"
    
    # Obter lista de arquivos anteriores
    all_files_sorted = df_full[["Nome Arquivo", "Data Arquivo"]].drop_duplicates().sort_values("Data Arquivo")["Nome Arquivo"].tolist()
    
    try:
        curr_idx = all_files_sorted.index(current_file_name)
        start_idx = max(0, curr_idx - 3)
        prev_files = all_files_sorted[start_idx:curr_idx]
    except ValueError:
        prev_files = []
    
    if not prev_files:
        # Se não tem histórico anterior, assume envio tardio para todos os atrasos
        df_current.loc[mask_atraso, "Motivo Atraso"] = "Envio fora do Prazo"
        return df_current

    # Dados dos arquivos anteriores
    df_history = df_full[df_full["Nome Arquivo"].isin(prev_files)]
    
    # Reforço de Regra de Negócio: Considerar apenas histórico de APROVADAS
    # (Garante a integridade mesmo se o carregamento inicial mudar)
    if "Status Solicitação" in df_history.columns:
        df_history = df_history[df_history["Status Solicitação"] == "APROVADA"]
    
    # Conjunto de solicitações presentes nos arquivos anteriores
    history_solicitacoes = set(df_history["Solicitação"].astype(str))

    def identify_reason(row):
        if row["Status Prazo"] != "FORA DO PRAZO":
            return None
            
        solic_id = str(row["Solicitação"])
        
        if solic_id in history_solicitacoes:
            return "Não atendida"
        else:
            return "Envio fora do Prazo"

    df_current["Motivo Atraso"] = df_current.apply(identify_reason, axis=1)
    
    return df_current


# Título e Descrição
st.title("📊 Monitoramento de Prazos de Manobras")

# Carregar dados
with st.spinner('Carregando e processando arquivos...'):
    df = load_data()

if df.empty:
    st.warning("Nenhum dado encontrado ou nenhum arquivo processado com sucesso.")
else:
    # Seletor de Arquivo/Data
    st.sidebar.header("Seleção de Arquivo")
    
    # Criar lista de opções formatadas
    df_files = df[["Nome Arquivo", "Data Arquivo"]].drop_duplicates().sort_values("Data Arquivo", ascending=False)
    file_options = df_files["Nome Arquivo"].tolist()
    
    selected_file = st.sidebar.selectbox(
        "Selecione o arquivo do dia:",
        file_options,
        format_func=lambda x: f"{x} ({df_files[df_files['Nome Arquivo'] == x]['Data Arquivo'].iloc[0].strftime('%d/%m/%Y')})"
    )
    
    # Filtrar dados para o arquivo selecionado
    df_day_raw = check_delay_reason(df, selected_file)
    
    # Filtro de Região na Sidebar
    st.sidebar.divider()
    st.sidebar.header("Filtros")
    
    all_regions = sorted(df_day_raw["Região"].dropna().unique())
    selected_regions = st.sidebar.multiselect(
        "Selecione as Regiões:",
        options=all_regions,
        default=all_regions
    )
    
    # Aplicar filtro
    if selected_regions:
        df_day = df_day_raw[df_day_raw["Região"].isin(selected_regions)]
    else:
        df_day = df_day_raw
    
    st.subheader(f"Análise do Dia: {df_day['Data Arquivo'].iloc[0].strftime('%d/%m/%Y')}")
    
    # Métricas do Dia
    total_day = len(df_day)
    fora_prazo_day = len(df_day[df_day["Status Prazo"] == "FORA DO PRAZO"])
    alerta_day = len(df_day[df_day["Status Prazo"] == "ALERTA"])
    no_prazo_day = len(df_day[df_day["Status Prazo"] == "NO PRAZO"])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Total Aprovadas", total_day)
    with col2:
        metric_card("Fora do Prazo", fora_prazo_day)
    with col3:
        metric_card("Alerta", alerta_day)
    with col4:
        metric_card("No Prazo", no_prazo_day)
    
    st.divider()
    
    # Gráficos em layout vertical (um abaixo do outro)
    st.markdown("### 🔴 Atrasos")
    df_atrasos = df_day[df_day["Status Prazo"] == "FORA DO PRAZO"]
    if not df_atrasos.empty:
        # Métricas de Motivo
        motivos = df_atrasos["Motivo Atraso"].value_counts()
        nao_atendidas = motivos.get("Não atendida", 0)
        envio_tardio = motivos.get("Envio fora do Prazo", 0)
        
        c1, c2 = st.columns(2)
        with c1:
            metric_card("Não Atendidas", nao_atendidas)
        with c2:
            metric_card("Envio Tardio", envio_tardio)
        
        st.markdown("#### Detalhamento por Região")

        # Preparar dados para Altair
        contagem_atrasos = df_atrasos.groupby(["Região", "Motivo Atraso"]).size().reset_index(name="Quantidade")

        # Dados separados
        df_nao_atendidas = contagem_atrasos[contagem_atrasos["Motivo Atraso"] == "Não atendida"]
        df_envio_fora = contagem_atrasos[contagem_atrasos["Motivo Atraso"] == "Envio fora do Prazo"]

        # Colunas para os gráficos lado a lado
        col_na, col_ef = st.columns(2)

        with col_na:
            st.markdown("### 🔴 Não Atendidas")
            if not df_nao_atendidas.empty:
                df_nao_atendidas = df_nao_atendidas.sort_values("Quantidade", ascending=False)
                
                # Top 10 e Restante
                top_10_na = df_nao_atendidas.head(10)
                restante_na = df_nao_atendidas.iloc[10:]
                
                # Layout interno: Gráfico + Tabela
                col_g_na, col_t_na = st.columns([2, 1])
                
                with col_g_na:
                    st.markdown("##### Top 10")
                    base_na = alt.Chart(top_10_na).encode(
                        x=alt.X("Região", sort="-y", axis=alt.Axis(labelAngle=0, title=None, labelFontWeight="bold"), scale=alt.Scale(padding=0.3)),
                        y=alt.Y("Quantidade", axis=None),
                        tooltip=["Região", "Quantidade"]
                    )
                    bars_na = base_na.mark_bar(cornerRadiusTopLeft=10, cornerRadiusTopRight=10, color="#ff4b4b")
                    text_na = base_na.mark_text(align='center', baseline='bottom', dy=-5, fontSize=14, fontWeight='bold', color="#ff4b4b").encode(text="Quantidade")
                    st.altair_chart((bars_na + text_na).properties(height=300).configure_view(strokeWidth=0).configure_axis(grid=False), use_container_width=True)
                
                with col_t_na:
                    st.markdown("##### Outros")
                    if not restante_na.empty:
                        st.dataframe(
                            restante_na.set_index("Região")[["Quantidade"]],
                            use_container_width=True,
                            height=300,
                            column_config={"Quantidade": st.column_config.NumberColumn("Qtd", format="%d")}
                        )
                    else:
                        st.info("Todos exibidos")
            else:
                st.success("Zero recorrências.")

        with col_ef:
            st.markdown("### 🟠 Envio Fora do Prazo")
            if not df_envio_fora.empty:
                df_envio_fora = df_envio_fora.sort_values("Quantidade", ascending=False)
                
                # Top 10 e Restante
                top_10_ef = df_envio_fora.head(10)
                restante_ef = df_envio_fora.iloc[10:]
                
                # Layout interno: Gráfico + Tabela
                col_g_ef, col_t_ef = st.columns([2, 1])
                
                with col_g_ef:
                    st.markdown("##### Top 10")
                    base_ef = alt.Chart(top_10_ef).encode(
                        x=alt.X("Região", sort="-y", axis=alt.Axis(labelAngle=0, title=None, labelFontWeight="bold"), scale=alt.Scale(padding=0.3)),
                        y=alt.Y("Quantidade", axis=None),
                        tooltip=["Região", "Quantidade"]
                    )
                    bars_ef = base_ef.mark_bar(cornerRadiusTopLeft=10, cornerRadiusTopRight=10, color="#ffa500")
                    text_ef = base_ef.mark_text(align='center', baseline='bottom', dy=-5, fontSize=14, fontWeight='bold', color="#ffa500").encode(text="Quantidade")
                    st.altair_chart((bars_ef + text_ef).properties(height=300).configure_view(strokeWidth=0).configure_axis(grid=False), use_container_width=True)
                
                with col_t_ef:
                    st.markdown("##### Outros")
                    if not restante_ef.empty:
                        st.dataframe(
                            restante_ef.set_index("Região")[["Quantidade"]],
                            use_container_width=True,
                            height=300,
                            column_config={"Quantidade": st.column_config.NumberColumn("Qtd", format="%d")}
                        )
                    else:
                        st.info("Todos exibidos")
            else:
                st.info("Nenhum envio fora do prazo.")
    else:
        st.success("Zero atrasos!")

    st.markdown("<br>", unsafe_allow_html=True) # Espaçamento extra
    st.markdown("---") # Divisor visual
    st.markdown("<br>", unsafe_allow_html=True) # Espaçamento extra

    # --- Seção de Alertas ---
    st.markdown("### 🟡 Alertas (Limite 8 dias)")
    df_alertas = df_day[df_day["Status Prazo"] == "ALERTA"]
    
    if not df_alertas.empty:
        st.metric("Total Alertas", len(df_alertas))
        
        # Agrupamento
        contagem_alertas = df_alertas.groupby("Região").size().reset_index(name="Quantidade")
        contagem_alertas = contagem_alertas.sort_values("Quantidade", ascending=False)
        
        # Top 10 para gráfico
        top_10_alertas = contagem_alertas.head(10)
        restante_alertas = contagem_alertas.iloc[10:]
        
        # Layout: Gráfico (Esq) e Tabela (Dir)
        col_graph_a, col_table_a = st.columns([3, 1])
        
        with col_graph_a:
            st.markdown("##### Top 10 Regiões")
            base_alert = alt.Chart(top_10_alertas).encode(
                x=alt.X("Região", sort="-y", axis=alt.Axis(labelAngle=0, title=None, labelFontWeight="bold"), scale=alt.Scale(padding=0.3)),
                y=alt.Y("Quantidade", axis=None),
                tooltip=["Região", "Quantidade"]
            )
            bars_alert = base_alert.mark_bar(cornerRadiusTopLeft=10, cornerRadiusTopRight=10, color="#ffd700")
            text_alert = base_alert.mark_text(align='center', baseline='bottom', dy=-5, fontSize=14, fontWeight='bold', color="#ffd700").encode(text="Quantidade")
            
            st.altair_chart((bars_alert + text_alert).properties(height=350).configure_view(strokeWidth=0).configure_axis(grid=False), use_container_width=True)
            
        with col_table_a:
            st.markdown("##### Outras Regiões")
            if not restante_alertas.empty:
                st.dataframe(
                    restante_alertas.set_index("Região"),
                    use_container_width=True,
                    height=350,
                    column_config={"Quantidade": st.column_config.NumberColumn("Qtd", format="%d")}
                )
            else:
                st.info("Todos exibidos")
    else:
        st.success("Nenhum alerta de prazo limite.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("<br>", unsafe_allow_html=True)

    # --- Seção de Demanda do Dia ---
    st.markdown("### 🔵 Demanda do Dia")
    # Filtrar apenas as categorias relevantes para a demanda (Atrasos + Alertas)
    df_demanda = df_day[df_day["Status Prazo"].isin(["FORA DO PRAZO", "ALERTA"])]
    
    if not df_demanda.empty:
        st.metric("Total Demanda Crítica", len(df_demanda))
        
        # Agrupamento
        contagem_demanda = df_demanda.groupby("Região").size().reset_index(name="Quantidade")
        contagem_demanda = contagem_demanda.sort_values("Quantidade", ascending=False)
        
        # Top 10 para gráfico
        top_10_demanda = contagem_demanda.head(10)
        restante_demanda = contagem_demanda.iloc[10:]
        
        # Layout: Gráfico (Esq) e Tabela (Dir)
        col_graph_d, col_table_d = st.columns([3, 1])
        
        with col_graph_d:
            st.markdown("##### Top 10 Regiões")
            base_demanda = alt.Chart(top_10_demanda).encode(
                x=alt.X("Região", sort="-y", axis=alt.Axis(labelAngle=0, title=None, labelFontWeight="bold"), scale=alt.Scale(padding=0.3)),
                y=alt.Y("Quantidade", axis=None),
                tooltip=["Região", "Quantidade"]
            )
            bars_demanda = base_demanda.mark_bar(cornerRadiusTopLeft=10, cornerRadiusTopRight=10, color="#1f77b4")
            text_demanda = base_demanda.mark_text(align='center', baseline='bottom', dy=-5, fontSize=14, fontWeight='bold', color="#1f77b4").encode(text="Quantidade")
            
            st.altair_chart((bars_demanda + text_demanda).properties(height=350).configure_view(strokeWidth=0).configure_axis(grid=False), use_container_width=True)
            
        with col_table_d:
            st.markdown("##### Outras Regiões")
            if not restante_demanda.empty:
                st.dataframe(
                    restante_demanda.set_index("Região"),
                    use_container_width=True,
                    height=350,
                    column_config={"Quantidade": st.column_config.NumberColumn("Qtd", format="%d")}
                )
            else:
                st.info("Todos exibidos")
    else:
        st.success("Nenhuma demanda crítica (Atrasos ou Alertas).")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("<br>", unsafe_allow_html=True)

    # --- Seção de Pesos por Região ---
    st.markdown("### ⚖️ Distribuição de Pesos das Demandas por Região")
    
    # Usar o mesmo dataframe da Demanda (Alertas + Atrasos) ou Geral?
    # O usuário disse "pesos das solicitações das demandas", geralmente referindo-se à Demanda do Dia (Crítica).
    # Vamos usar df_demanda (Atrasos + Alertas) conforme contexto visual.
    
    if not df_demanda.empty:
        # Precisamos garantir que as colunas de Peso existam. O load_data original filtra colunas.
        # Precisamos recarregar ou ajustar load_data para incluir Peso/Clientes/PLE/Recursos.
        # Ajuste estratégico: O load_data está cacheado e restrito. 
        # Vamos reprocessar o arquivo atual para pegar os pesos, já que o load_data é otimizado e não traz tudo.
        
        # Função auxiliar local para pegar detalhes de peso apenas do arquivo selecionado
        @st.cache_data
        def load_weight_details(file_name):
            try:
                # Encontrar caminho completo do arquivo
                file_path_list = [f for f in glob.glob(os.path.join(BASE_PATH, "*.xlsx")) if os.path.basename(f) == file_name]
                if not file_path_list:
                    return pd.DataFrame()
                    
                file_path = file_path_list[0]
                
                # Ler colunas necessárias
                # Nota: 'Status Solicitação' é usado para filtrar APROVADA
                # 'Solicitação' para join
                # 'Peso', 'Clientes', 'PLE', 'Tipo' (para MANOBRA INFORMATIVA que pode estar em Tipo ou Recurso, vamos pegar ambos se existirem)
                cols_to_check = ["Solicitação", "Status Solicitação", "Peso", "Clientes", "PLE", "Tipo"]
                
                # Verificar quais colunas existem no arquivo antes de ler
                xl = pd.ExcelFile(file_path)
                sheet_name = xl.sheet_names[0]
                df_cols = pd.read_excel(file_path, sheet_name=sheet_name, nrows=0).columns.tolist()
                
                # Interseção de colunas existentes
                use_cols = [c for c in cols_to_check if c in df_cols]
                
                # Se faltar colunas críticas, não prosseguir
                if "Solicitação" not in use_cols:
                    return pd.DataFrame()
                
                df_w = pd.read_excel(file_path, usecols=use_cols)
                
                # Filtrar APROVADA se a coluna existir
                if "Status Solicitação" in df_w.columns:
                    df_w = df_w[df_w["Status Solicitação"] == "APROVADA"].copy()
                
                # Garantir tipo string para Solicitação
                df_w["Solicitação"] = df_w["Solicitação"].astype(str)
                
                return df_w
            except Exception as e:
                return pd.DataFrame()

        df_weights_raw = load_weight_details(selected_file)
        
        if not df_weights_raw.empty:
            # Converter a coluna Solicitação para string em ambos os dataframes para garantir o merge
            df_demanda = df_demanda.copy()
            df_demanda["Solicitação"] = df_demanda["Solicitação"].astype(str)
            
            # Merge para pegar os dados de peso das solicitações filtradas
            # df_demanda já tem filtro de região aplicado na sidebar
            df_final_weight = pd.merge(df_demanda, df_weights_raw, on="Solicitação", how="inner", suffixes=("", "_w"))
            
            if not df_final_weight.empty:
                # Função de cálculo de peso (reutilizada da lógica de produtividade)
                def calcular_peso_prazos(row):
                    # Tentar pegar colunas com sufixo _w se existirem (do merge), senão tenta sem sufixo
                    peso = row.get("Peso", row.get("Peso_w"))
                    clientes = row.get("Clientes", row.get("Clientes_w"))
                    if pd.isna(clientes): clientes = 0
                    
                    ple = row.get("PLE", row.get("PLE_w"))
                    
                    tipo = str(row.get("Tipo", row.get("Tipo_w"))).upper()
                    
                    # Regras de Negócio
                    # 1. Se PLE for PLE e tiver MANOBRA INFORMATIVA (em Tipo), peso 1
                    if str(ple).upper() == "PLE" and "MANOBRA INFORMATIVA" in tipo:
                        return 1
                    
                    # 2. Se Peso vazio e PLE for PLE, peso "PLE"
                    if pd.isna(peso) and str(ple).upper() == "PLE":
                        return "PLE"
                    
                    # 3. Se Peso 1 e Clientes 0, considerar peso 3
                    if peso == 1 and clientes == 0:
                        return 3
                    
                    return peso

                def normalize_peso_prazos(val):
                    s_val = str(val).strip()
                    if s_val.upper() == "PLE":
                        return "PLE"
                    try:
                        f_val = float(val)
                        if f_val.is_integer():
                            return str(int(f_val))
                        return str(f_val)
                    except:
                        if s_val == "nan" or s_val == "None":
                            return "N/A"
                        return s_val

                df_final_weight["Peso Calculado"] = df_final_weight.apply(calcular_peso_prazos, axis=1)
                df_final_weight["Peso Label"] = df_final_weight["Peso Calculado"].apply(normalize_peso_prazos)
                
                # Agrupar por Região e Peso
                weight_counts = df_final_weight.groupby(["Região", "Peso Label"]).size().reset_index(name="Quantidade")
                
                # --- NOVO LAYOUT SOLICITADO ---
                # "coloque uma coluna por peso mostre 5 regioes e um check para selecionar a que eu quero ver"
                
                # Seletor de Regiões específico para este gráfico
                st.markdown("#### Seleção de Regiões para Análise de Peso")
                
                # Obter todas as regiões disponíveis nos dados de peso
                regions_available = sorted(weight_counts["Região"].unique())
                
                # Padrão: Top 5 regiões com mais volume
                top_5_regions = weight_counts.groupby("Região")["Quantidade"].sum().nlargest(5).index.tolist()
                
                # Dataframe scrollável para seleção (simulando "check para selecionar")
                # Usando st.dataframe com on_select ou st.multiselect
                # O usuário pediu "um check para selecionar", o multiselect é o mais próximo e limpo.
                # Mas ele mencionou "scroll para ficar do tamanho do grafico" em outro contexto.
                # Aqui vamos usar um multiselect limpo, pois é mais padrão para "selecionar o que eu quero ver".
                
                selected_regions_weight = st.multiselect(
                    "Filtrar Regiões (Padrão: Top 5 com mais volume)",
                    options=regions_available,
                    default=top_5_regions if top_5_regions else regions_available[:5]
                )
                
                if selected_regions_weight:
                    df_viz = weight_counts[weight_counts["Região"].isin(selected_regions_weight)]
                else:
                    df_viz = weight_counts
                
                if not df_viz.empty:
                    # Gráfico de Colunas Agrupadas (Grouped Bar Chart)
                    # "uma coluna por peso" -> x=Região, y=Qtd, color=Peso, column=Peso (ou offset)
                    # O Altair faz grouped bar automaticamente com x-offset ou column.
                    # Vamos usar xOffset para agrupar as barras de peso lado a lado dentro de cada região.
                    
                    base_chart = alt.Chart(df_viz).encode(
                        x=alt.X("Região", axis=None),
                        y=alt.Y("Quantidade", title="Qtd Demandas"),
                        color=alt.Color("Peso Label", title="Peso"),
                        tooltip=["Região", "Peso Label", "Quantidade"]
                    )
                    
                    chart_grouped = base_chart.mark_bar().encode(
                        x=alt.X("Peso Label", title=None, axis=None), # Eixo X interno (grupos)
                        column=alt.Column("Região", header=alt.Header(titleOrient="bottom", labelOrient="bottom", titleFontSize=12, labelFontSize=11)), # Colunas principais (Regiões)
                    ).properties(
                        width=alt.Step(40) # Largura de cada barra/grupo
                    ).configure_view(
                        stroke='transparent'
                    )
                    
                    # Alternativa mais robusta para Grouped Bar no Streamlit/Altair:
                    # Usar xOffset (requer Altair 5+ e Streamlit recente) ou Column Facet.
                    # Vamos tentar xOffset que é mais limpo visualmente se suportado, senão Column.
                    # A abordagem Column acima separa bem as regiões.
                    
                    st.altair_chart(chart_grouped)
                    
                    with st.expander("Ver Dados em Tabela"):
                        pivot_df = df_viz.pivot(index="Região", columns="Peso Label", values="Quantidade").fillna(0).astype(int)
                        st.dataframe(pivot_df, use_container_width=True)
                        
                else:
                    st.warning("Nenhuma região selecionada ou sem dados para as regiões escolhidas.")
                    
            else:
                 st.warning("Não foi possível cruzar os dados de peso com a demanda atual.")
        else:
            st.warning("Não foi possível carregar detalhes de peso para este arquivo.")
            
    else:
        st.info("Sem demandas críticas para análise de peso.")


# Rodapé
st.markdown("---")
st.caption("Sistema de Análise de Prazos - Versão 1.0")
