import streamlit as st

# Configuração da Página Principal (Ponto de Entrada)
st.set_page_config(page_title="Works Analyzer - Portal", layout="wide")

st.title("🚀 Works Analyzer - Portal de Dashboards")
st.markdown("Bem-vindo ao sistema centralizado de análise de solicitações. Selecione um dashboard no menu lateral.")

st.sidebar.title("Navegação")
st.sidebar.info("Selecione o módulo que deseja acessar.")

# Definição das Páginas
pg = st.navigation([
    st.Page("dashboard_prazos.py", title="1. Análise de Prazos (8 Dias)", icon="📅"),
    st.Page("dashboard_ciclo.py", title="2. Ciclo de Vida (11 Dias)", icon="🔄"),
    st.Page("dashboard_produtividade.py", title="3. Produtividade Diária", icon="📈"),
    st.Page("dashboard_historico.py", title="4. Histórico de Demandas", icon="📚"),
])

pg.run()
