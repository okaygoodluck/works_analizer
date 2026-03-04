import streamlit as st

def apply_modern_style():
    st.markdown("""
    <style>
        /* Fonte global */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        
        html, body, [class*="css"]  {
            font-family: 'Inter', sans-serif;
        }

        /* Fundo e cores principais */
        .stApp {
            background-color: #f8f9fa;
        }

        /* Sidebar moderna */
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e9ecef;
        }

        /* Títulos */
        h1, h2, h3 {
            color: #1e293b;
            font-weight: 700;
        }

        /* Cards de Métricas */
        .metric-card {
            background-color: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            text-align: center;
            border: 1px solid #e2e8f0;
        }
        .metric-value {
            font-size: 32px;
            font-weight: 700;
            color: #2563eb;
            margin: 0;
        }
        .metric-label {
            font-size: 14px;
            color: #64748b;
            margin-bottom: 5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        /* Botões e Inputs */
        .stButton button {
            background-color: #2563eb;
            color: white;
            border-radius: 8px;
            border: none;
            padding: 0.5rem 1rem;
            transition: all 0.2s;
        }
        .stButton button:hover {
            background-color: #1d4ed8;
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
            color: #64748b;
            font-weight: 600;
        }
        .stTabs [aria-selected="true"] {
            background-color: transparent;
            color: #2563eb;
            border-bottom: 2px solid #2563eb;
        }

        /* Gráficos e Containers */
        [data-testid="stAltairChart"] {
            background-color: white;
            padding: 15px;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
            border: 1px solid #f1f5f9;
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
