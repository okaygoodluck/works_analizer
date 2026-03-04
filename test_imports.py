
import sys
import os

# Adicionar diretório ao path
sys.path.append(r"i:\IT\ODCO\PUBLICA\Kennedy\Projetos\works_analyzer")

try:
    print("Testando imports...")
    import data_loader
    print("data_loader OK")
    import dashboard_historico
    print("dashboard_historico OK")
    import dashboard_ciclo
    print("dashboard_ciclo OK")
    import dashboard_produtividade
    print("dashboard_produtividade OK")
    print("Todos os módulos importados com sucesso (sintaxe OK).")
except Exception as e:
    print(f"Erro de importação: {e}")
