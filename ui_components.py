import streamlit as st

def apply_modern_style():
    # Dica de tema na sidebar (discreto)
    with st.sidebar:
        st.markdown("---")
        st.caption("🎨 **Tema**: Para alternar entre Claro/Escuro, acesse o menu superior direito (⋮) > Settings > Theme.")
        
    st.markdown("""
    <style>
        /* Fonte global */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        
        html, body, [class*="css"]  {
            font-family: 'Inter', sans-serif;
        }

        /* Fundo e cores principais */
        .stApp {
            background-color: var(--background-color);
        }

        /* Sidebar moderna */
        [data-testid="stSidebar"] {
            background-color: var(--secondary-background-color);
            border-right: 1px solid var(--text-color-20);
        }

        /* Títulos */
        h1, h2, h3 {
            color: var(--text-color);
            font-weight: 700;
        }

        /* Cards de Métricas */
        .metric-card {
            background-color: var(--secondary-background-color);
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            text-align: center;
            border: 1px solid rgba(128, 128, 128, 0.1);
        }
        .metric-value {
            font-size: 32px;
            font-weight: 700;
            color: var(--primary-color);
            margin: 0;
        }
        .metric-label {
            font-size: 14px;
            color: var(--text-color);
            margin-bottom: 5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            opacity: 0.8;
        }

        /* Botões e Inputs */
        .stButton button {
            background-color: var(--primary-color);
            color: white;
            border-radius: 8px;
            border: none;
            padding: 0.5rem 1rem;
            transition: all 0.2s;
        }
        .stButton button:hover {
            opacity: 0.9;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: transparent;
            border-radius: 4px;
            color: var(--text-color);
            font-weight: 600;
            opacity: 0.7;
        }
        .stTabs [aria-selected="true"] {
            background-color: transparent;
            color: var(--primary-color);
            border-bottom: 2px solid var(--primary-color);
            opacity: 1;
        }

        /* Gráficos e Containers */
        [data-testid="stAltairChart"] {
            background-color: var(--secondary-background-color);
            padding: 15px;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
            border: 1px solid rgba(128, 128, 128, 0.1);
        }
        
    </style>
    """, unsafe_allow_html=True)

def metric_card(label, value, prefix="", suffix=""):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{prefix}{value}{suffix}</div>
    </div>
    """, unsafe_allow_html=True)
