import pandas as pd
import pyodbc
from dotenv import dotenv_values
from pathlib import Path
from src.utils.exepciones import BodegaBiconexionError

def _bi_con() -> pyodbc.Connection:
    
    # --- Se extraen los valores del ambiente ---
    env = dotenv_values()
    if not env:
        raise FileNotFoundError("No se encontró archivo .env o está vacio")
    
    # --- Se genera la conexión --- #
    try:
        con = pyodbc.connect(env['CON_BI'])
        print(f"Conexión con BODEGA correctamente implementada")
        return con
    except Exception as e:
        raise BodegaBiconexionError(f"No se pudo establecer conexión con BI: {e}") from e
    
def execute_query(query:str,
                  params:list|None=None) -> pd.DataFrame:
    
    # --- Se genera la conexión con BI --- #
    con = _bi_con()
    
    # --- Se extrae el query ---
    
    if not Path(query).exists():
        raise FileNotFoundError(f"No existe la consulta proporcionada: {query}")
    
    query_str = Path(query).read_text(encoding="utf-8")
    
    # --- Se genera la consulta sql --- #
    try:
        if params:
            df = pd.read_sql(sql=query_str, 
                         con=con, #type: ignore
                         params=params)
        else:
            df = pd.read_sql(sql=query_str, 
                             con=con) #type: ignore
        
        print(f"Consulta realizada correctamente: {query}")
        return df
    
    except Exception as e:
        raise pyodbc.Error(f"Error consultando {query}: {e}") from e
    
    finally:
        con.close()