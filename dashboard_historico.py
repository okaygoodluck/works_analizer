import streamlit as st
import pandas as pd
import os
import glob
import re
import altair as alt
from ui_components import apply_modern_style, metric_card

# Configuração da página
st.set_page_config(page_title="Histórico de Demandas APROVADAS", layout="wide")
apply_modern_style()

BASE_PATH = r"i:\IT\ODCO\PUBLICA\Kennedy\Projetos\works_analyzer\mesao"


# --- Funções de Carga e Processamento ---

def normalize_peso(val):
    s_val = str(val).strip()
    if s_val.upper() == "PLE":
        return "PLE"
    try:
        f_val = float(val)
        if f_val.is_integer():
            return str(int(f_val))
        return str(f_val)
    except (ValueError, TypeError):
        return s_val

def calcular_peso_ajustado(row):
    peso = row["Peso"]
    clientes = row["Clientes"] if pd.notna(row["Clientes"]) else 0
    ple = row["PLE"]
    recursos = str(row["Recursos"]).upper() if pd.notna(row["Recursos"]) else ""
    
    if ple == "PLE" and "MANOBRA INFORMATIVA" in recursos:
        return 1
    if pd.isna(peso) and ple == "PLE":
        return "PLE"
    if peso == 1 and clientes == 0:
        return 3
    return peso

@st.cache_data
def load_historical_data():
    all_files = glob.glob(os.path.join(BASE_PATH, "*.xlsx"))
    all_data = []
    
    # Lista de arquivos ordenados por data para processamento sequencial
    file_map = []
    
    for file_path in all_files:
        filename = os.path.basename(file_path)
        match1 = re.search(r"(\d{2})(\d{2})(\d{4})", filename)
        match2 = re.search(r"(\d{2})_(\d{2})_(\d{2})", filename)
        
        file_date = None
        if match1:
            file_date = pd.to_datetime(f"{match1.group(3)}-{match1.group(2)}-{match1.group(1)}").date()
        elif match2:
            file_date = pd.to_datetime(f"20{match2.group(3)}-{match2.group(2)}-{match2.group(1)}").date()
            
        if file_date:
            file_map.append({"date": file_date, "path": file_path})
            
    # Ordenar por data
    file_map.sort(key=lambda x: x["date"])
    
    seen_solicitacoes_aprovadas = set()
    seen_solicitacoes_cadastradas = set()
    
    for item in file_map:
        file_date = item["date"]
        file_path = item["path"]
        
        try:
            # Ler colunas necessárias
            cols_needed = ["Solicitação", "Status Solicitação", "Região", "Peso", "Clientes", "PLE", "Recursos"]
            
            # Verificar colunas antes de ler para evitar erro
            xl = pd.ExcelFile(file_path)
            sheet_name = xl.sheet_names[0]
            df_cols = pd.read_excel(file_path, sheet_name=sheet_name, nrows=0).columns.tolist()
            use_cols = [c for c in cols_needed if c in df_cols]
            
            if "Solicitação" not in use_cols:
                continue
                
            df = pd.read_excel(file_path, usecols=use_cols)
            df["Solicitação"] = df["Solicitação"].astype(str)
            
            # --- 1. Processar Cadastradas (Primeira aparição no sistema) ---
            current_ids = set(df["Solicitação"].unique())
            new_cadastros = current_ids - seen_solicitacoes_cadastradas
            seen_solicitacoes_cadastradas.update(new_cadastros)
            
            df_new_cad = df[df["Solicitação"].isin(new_cadastros)].copy()
            
            if not df_new_cad.empty:
                df_new_cad["Data Referência"] = file_date
                df_new_cad["Tipo Evento"] = "Cadastro"
                # Aplicar regra de peso
                df_new_cad["Peso Calculado"] = df_new_cad.apply(calcular_peso_ajustado, axis=1)
                df_new_cad["Peso Label"] = df_new_cad["Peso Calculado"].apply(normalize_peso)
                
                cols_final = ["Solicitação", "Região", "Peso Label", "Data Referência", "Tipo Evento"]
                # Garantir que colunas existem
                for c in cols_final:
                    if c not in df_new_cad.columns:
                        df_new_cad[c] = None
                        
                all_data.append(df_new_cad[cols_final])

            # --- 2. Processar Aprovadas (Primeira vez como APROVADA) ---
            if "Status Solicitação" in df.columns:
                df_aprov = df[df["Status Solicitação"] == "APROVADA"].copy()
                
                if not df_aprov.empty:
                    current_aprov_ids = set(df_aprov["Solicitação"].unique())
                    new_aprov = current_aprov_ids - seen_solicitacoes_aprovadas
                    seen_solicitacoes_aprovadas.update(new_aprov)
                    
                    df_new_aprov = df_aprov[df_aprov["Solicitação"].isin(new_aprov)].copy()
                    
                    if not df_new_aprov.empty:
                        df_new_aprov["Data Referência"] = file_date
                        df_new_aprov["Tipo Evento"] = "Aprovação"
                        # Aplicar regra de peso
                        df_new_aprov["Peso Calculado"] = df_new_aprov.apply(calcular_peso_ajustado, axis=1)
                        df_new_aprov["Peso Label"] = df_new_aprov["Peso Calculado"].apply(normalize_peso)
                        
                        cols_final = ["Solicitação", "Região", "Peso Label", "Data Referência", "Tipo Evento"]
                        # Garantir que colunas existem
                        for c in cols_final:
                            if c not in df_new_aprov.columns:
                                df_new_aprov[c] = None
                                
                        all_data.append(df_new_aprov[cols_final])
                    
        except Exception as e:
            # st.warning(f"Erro ao carregar {os.path.basename(file_path)}: {e}")
            pass
            
    if not all_data:
        return pd.DataFrame()
        
    return pd.concat(all_data, ignore_index=True)

# --- Interface ---

st.title("📊 Histórico de Demandas")
st.info("Monitoramento de Novas Entradas (Cadastradas) e Novas Aprovações.")

df_hist = load_historical_data()

if df_hist.empty:
    st.error("Nenhum dado encontrado nos arquivos.")
    st.stop()

# Filtros Globais
st.sidebar.header("Filtros")
date_range = st.sidebar.date_input(
    "Período de Análise:",
    [df_hist["Data Referência"].min(), df_hist["Data Referência"].max()]
)

# Aplicar filtro de data
if len(date_range) == 2:
    df_filtered_all = df_hist[(df_hist["Data Referência"] >= date_range[0]) & (df_hist["Data Referência"] <= date_range[1])]
else:
    df_filtered_all = df_hist

# Abas para separar as visões
tab_aprov, tab_cad = st.tabs(["✅ Aprovadas", "🆕 Cadastradas"])

def render_dashboard_tab(df_tab, title_prefix):
    if df_tab.empty:
        st.warning(f"Nenhum dado de {title_prefix} no período selecionado.")
        return

    # --- Seção 1: Volume Diário e KPIs ---
    
    # KPIs Rápidos
    total_vol = len(df_tab)
    unique_regs = df_tab["Região"].nunique()
    
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1:
        metric_card(f"Total de {title_prefix}", total_vol, suffix=" itens")
    with col_kpi2:
        metric_card("Regiões Ativas", unique_regs)
    with col_kpi3:
        last_date = df_tab["Data Referência"].max().strftime("%d/%m/%Y")
        metric_card("Última Atualização", last_date)
        
    st.divider()
    
    st.subheader(f"📈 Evolução Diária ({title_prefix})")

    # Agrupar por data e região
    daily_vol = df_tab.groupby(["Data Referência", "Região"]).size().reset_index(name="Quantidade")

    # Seletor de Regiões para o Gráfico de Linha (Unique key para não conflitar entre abas)
    avail_regs = sorted(daily_vol["Região"].unique())
    key_suffix = title_prefix.replace(" ", "_").lower()
    
    sel_regs = st.multiselect(
        "Filtrar Regiões:", 
        avail_regs, 
        default=avail_regs[:5] if len(avail_regs) > 5 else avail_regs,
        key=f"reg_sel_{key_suffix}"
    )

    if sel_regs:
        daily_vol_filtered = daily_vol[daily_vol["Região"].isin(sel_regs)]
        
        # Cores mais modernas (Paleta de azuis/roxos)
        base = alt.Chart(daily_vol_filtered).encode(
            x=alt.X("Data Referência:T", title="Data", axis=alt.Axis(format="%d/%m", labelAngle=0)),
            y=alt.Y("Quantidade:Q", title="Volume"),
            color=alt.Color("Região:N", scale=alt.Scale(scheme="category20b"), legend=alt.Legend(title="Região", orient="bottom")),
            tooltip=["Data Referência", "Região", "Quantidade"]
        )

        chart_line = base.mark_line(point=True, interpolate="monotone").properties(height=350)
        
        st.altair_chart(chart_line, use_container_width=True)
    else:
        st.info("Selecione ao menos uma região para visualizar o gráfico de linhas.")

    # --- Seção 2: Distribuição de Pesos por Região ---
    st.divider()
    st.subheader(f"⚖️ Distribuição de Pesos ({title_prefix})")

    # Agrupar por Região e Peso
    weight_dist = df_tab.groupby(["Região", "Peso Label"]).size().reset_index(name="Quantidade")

    # Layout de Colunas para o Gráfico de Pesos
    col_graph, col_select = st.columns([3, 1])

    with col_select:
        st.markdown("#### Selecionar Regiões")
        df_sel_weight = pd.DataFrame({"Região": avail_regs})
        
        event_w = st.dataframe(
            df_sel_weight,
            use_container_width=True,
            hide_index=True,
            height=350,
            on_select="rerun",
            selection_mode="multi-row",
            key=f"weight_reg_sel_{key_suffix}"
        )
        
        try:
            sel_idx = event_w.selection.rows
        except AttributeError:
            sel_idx = []

        if not sel_idx:
            sel_regs_w = avail_regs[:5] if len(avail_regs) > 5 else avail_regs
            st.caption("Mostrando top 5 padrão.")
        else:
            sel_regs_w = df_sel_weight.iloc[sel_idx]["Região"].tolist()

    with col_graph:
        if sel_regs_w:
            weight_dist_filt = weight_dist[weight_dist["Região"].isin(sel_regs_w)]
            
            # Gráfico de Colunas Agrupadas Moderno
            chart_weight = alt.Chart(weight_dist_filt).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X("Peso Label:N", title="Peso", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Quantidade:Q", title="Volume"),
                color=alt.Color("Peso Label:N", legend=None, scale=alt.Scale(scheme="viridis")),
                column=alt.Column("Região:N", header=alt.Header(titleOrient="bottom", labelOrient="bottom", titleFontSize=14, labelFontSize=12)),
                tooltip=["Região", "Peso Label", "Quantidade"]
            ).properties(width=120, height=250)
            
            st.altair_chart(chart_weight)
        else:
            st.info("Nenhuma região selecionada para análise de peso.")

    # --- Tabela Resumo ---
    st.divider()
    st.subheader("📋 Resumo Consolidado")
    
    pivot_summary = weight_dist.pivot(index="Região", columns="Peso Label", values="Quantidade").fillna(0).astype(int)
    pivot_summary["Total"] = pivot_summary.sum(axis=1)
    
    # Filtro de Regiões para o Resumo
    all_regs_summary = sorted(pivot_summary.index.unique())
    sel_regs_summary = st.multiselect(
        "Filtrar Regiões na Tabela:",
        all_regs_summary,
        default=all_regs_summary,
        key=f"summary_reg_sel_{key_suffix}"
    )
    
    if sel_regs_summary:
        pivot_summary_filtered = pivot_summary[pivot_summary.index.isin(sel_regs_summary)]
        st.dataframe(pivot_summary_filtered.sort_values("Total", ascending=False), use_container_width=True)
    else:
        st.info("Selecione ao menos uma região para visualizar a tabela.")


with tab_aprov:
    df_aprovada_filtered = df_filtered_all[df_filtered_all["Tipo Evento"] == "Aprovação"]
    render_dashboard_tab(df_aprovada_filtered, "Aprovadas")

with tab_cad:
    df_cadastrada_filtered = df_filtered_all[df_filtered_all["Tipo Evento"] == "Cadastro"]
    render_dashboard_tab(df_cadastrada_filtered, "Cadastradas")
