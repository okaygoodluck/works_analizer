import pandas as pd
import concurrent.futures
import streamlit as st
import os

def read_excel_file(file_path, usecols=None, sheet_name=0):
    """Lê um único arquivo Excel de forma segura."""
    try:
        # Se usecols for fornecido como lista, verifica se as colunas existem antes de ler
        if usecols and isinstance(usecols, list):
            # Ler apenas o cabeçalho para validar colunas
            try:
                # Engine openpyxl é necessária para xlsx
                df_cols = pd.read_excel(file_path, sheet_name=sheet_name, nrows=0, engine='openpyxl').columns.tolist()
                # Interseção de colunas desejadas com existentes
                valid_cols = [c for c in usecols if c in df_cols]
                
                if not valid_cols:
                    return pd.DataFrame()
                
                return pd.read_excel(file_path, sheet_name=sheet_name, usecols=valid_cols, engine='openpyxl')
            except Exception:
                return pd.DataFrame()
        
        # Se usecols for função ou None, ou se a verificação falhar
        return pd.read_excel(file_path, sheet_name=sheet_name, usecols=usecols, engine='openpyxl')
    except Exception:
        return pd.DataFrame()

def load_and_enrich(item, usecols=None):
    """Função auxiliar para ler e enriquecer DataFrame com metadados."""
    file_path = item.get("path")
    if not file_path:
        return None
        
    df = read_excel_file(file_path, usecols=usecols)
    
    if not df.empty:
        # Injeta metadados no DataFrame
        for key, value in item.items():
            if key != "path": 
                df[key] = value
        
        # Adiciona nome do arquivo se não existir
        if "Nome Arquivo" not in df.columns:
            df["Nome Arquivo"] = os.path.basename(file_path)
            
        return df
    return None

def load_files_in_parallel(file_list_dict, usecols=None, max_workers=4):
    """
    Lê múltiplos arquivos Excel em paralelo e retorna um DataFrame concatenado.
    
    Args:
        file_list_dict (list): Lista de dicionários, cada um deve ter a chave 'path'.
                               Ex: [{'path': 'C:/data.xlsx', 'date': '2023-01-01'}]
        usecols (list, optional): Lista de nomes de colunas a serem lidas.
        max_workers (int): Número de threads simultâneas.
        
    Returns:
        pd.DataFrame: DataFrame único contendo todos os dados concatenados.
    """
    all_dfs = []
    
    # ThreadPoolExecutor é ideal para I/O bound tasks como leitura de arquivos
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submete todas as tarefas
        futures = {executor.submit(load_and_enrich, item, usecols): item for item in file_list_dict}
        
        # Coleta resultados conforme ficam prontos
        for future in concurrent.futures.as_completed(futures):
            try:
                data = future.result()
                if data is not None and not data.empty:
                    all_dfs.append(data)
            except Exception:
                pass
                
    if not all_dfs:
        return pd.DataFrame()
        
    return pd.concat(all_dfs, ignore_index=True)
