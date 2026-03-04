import pandas as pd
import os
import glob

BASE_PATH = r"i:\IT\ODCO\PUBLICA\Kennedy\Projetos\works_analyzer\mesao"
# Pegar o arquivo mais recente
all_files = glob.glob(os.path.join(BASE_PATH, "*.xlsx"))
latest_file = max(all_files, key=os.path.getmtime)

print(f"Lendo arquivo: {os.path.basename(latest_file)}")

df = pd.read_excel(latest_file, nrows=5)
print("\nColunas encontradas:")
for col in df.columns:
    print(f"- {col}")

print("\nExemplo de dados (primeira linha):")
print(df.iloc[0].to_dict())
