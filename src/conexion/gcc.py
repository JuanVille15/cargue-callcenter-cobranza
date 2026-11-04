import pandas as pd
import pyodbc
import os

from pathlib import Path
from src.utils.exepciones import GCCconexionError

def _gcc_con() -> pyodbc.Connection:
    
    """
    Abre una conexión ODBC contra GCC usando la cadena de conexión
    definida en el archivo .env (clave 'GCC_CON').

    Es una función privada (prefijo '_'): no está pensada para llamarse
    directamente desde fuera del módulo, sino como paso previo dentro
    de `execute_query`.

    Returns
    -------
    pyodbc.Connection
        Conexión abierta contra la base de datos GCC.

    Raises
    ------
    FileNotFoundError
        Si no existe el archivo .env o está vacío.
    GCCconexionError
        Si falla el intento de conexión con las credenciales provistas.
    """
    # --- Variable entorno: cadena de conexion gcc --- #
    con_str = os.environ['GCC_CON']
    
    # --- Se genera la conexión --- #
    try:
        con = pyodbc.connect(con_str)
        print(f"Conexión con GCC correctamente implementada")
        return con
    except Exception as e:
        raise GCCconexionError(f"No se pudo establecer conexión con GCC: {e}")
    
def execute_query(query:str) -> pd.DataFrame:
    
    """
    Ejecuta una consulta SQL contra GCC y retorna el resultado como DataFrame.

    Abre la conexión vía `_gcc_con`, lee el contenido del archivo `.sql`
    indicado en `query` y lo ejecuta con `pd.read_sql`. La conexión se
    cierra siempre al finalizar, tanto si la consulta fue exitosa como
    si falló.

    Parameters
    ----------
    query : str
        Ruta al archivo `.sql` con la consulta a ejecutar. El contenido
        se lee como texto plano, sin soporte de parámetros dinámicos.

    Returns
    -------
    pd.DataFrame
        DataFrame con el resultado de la consulta.

    Raises
    ------
    FileNotFoundError
        Si la ruta indicada en `query` no existe.
    pyodbc.Error
        Si ocurre un error al ejecutar la consulta contra GCC.
    """
    # --- Se genera la conexión con GCC --- #
    con = _gcc_con()
    
    # --- Se extrae el query ---
    
    if not Path(query).exists():
        raise FileNotFoundError(f"No existe la consulta proporcionada: {query}")
    
    query_str = Path(query).read_text(encoding="utf-8")
    
    # --- Se genera la consulta sql --- #
    try:
        df = pd.read_sql(sql=query_str, 
                         con=con) #type: ignore
        print(f"Consulta realizada correctamente: {query}")
        return df
    
    except Exception as e:
        raise pyodbc.Error(f"Error consultando {query}: {e}")
    
    finally:
        con.close()