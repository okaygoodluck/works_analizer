import pandas as pd
import os
import glob
import re

base_path = r"i:\IT\ODCO\PUBLICA\Kennedy\Projetos\works_analyzer\mesao"

def extract_date_from_filename(filename):
    # Tenta padrões comuns: DDMMYYYY, DD_MM_YY
    match = re.search(r"(\d{2})(\d{2})(\d{4})", filename)
    if match:
        return f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
    
    match = re.search(r"(\d{2})_(\d{2})_(\d{2})", filename)
    if match:
        year = "20" + match.group(3)
        return f"{match.group(1)}/{match.group(2)}/{year}"
    return None

def check_status_and_dates():
    all_files = glob.glob(os.path.join(base_path, "*.xlsx"))
    unique_status = set()
    files_with_dates = 0
    
    # Amostra de 5 arquivos para verificar status
    for f in all_files[:5]:
        try:
            df = pd.read_excel(f, usecols=["Status Solicitação"])
            unique_status.update(df["Status Solicitação"].dropna().unique())
        except Exception as e:
            pass
            
    # Verificar extração de datas
    print("Exemplos de extração de datas:")
    for f in all_files[:5]:
        fname = os.path.basename(f)
        date = extract_date_from_filename(fname)
        files_with_dates += 1 if date else 0
        print(f"  {fname} -> {date}")

    print(f"\nStatus encontrados na amostra: {unique_status}")

if __name__ == "__main__":
    check_status_and_dates()
