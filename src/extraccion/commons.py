import pandas as pd
import datetime
from dateutil.relativedelta import relativedelta
from src.conexion.bodega import execute_query
from src.conexion.gcc import execute_query as execute_query_gcc
from src.utils.exepciones import ErrorConsultadoDemografica,ErrorConsultadoPerfil,ErrorConsultadoVista360
from src.utils.helpers import exportar, extract_files

def extract_demografica(demo_path:str) -> dict[str,pd.DataFrame]:
    
    """
    Extrae la vista demográfica desde el DWH Bodega BI para el mes anterior
    al actual. Si el período no existe, reintenta con el mes inmediatamente
    anterior (-2 meses).

    La consulta requiere dos parámetros de fecha en formato YYYY-MM-DD,
    ambos con el mismo valor (período de consulta).

    Parameters
    ----------
    demo_path : str
        Ruta al archivo SQL con la consulta de la vista demográfica.

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario con clave 'Demografica' y el DataFrame resultante.

    Raises
    ------
    ErrorConsultadoDemografica
        Si ocurre cualquier error durante la ejecución de la consulta SQL.
    """
    # --- Se define el mes de consulta -1 --- #
    
    MONTH_QUERY = (datetime.date.today().replace(day=1) - 
                   relativedelta(months=1)).strftime(format='%Y-%m-%d')
    
    try:
        print("Ejecutando Query DWH Bodega BI")
        print(f"\nExtrayendo Vista Demografica:{MONTH_QUERY[:7].replace('-','')}")
        param = [MONTH_QUERY]
        demografica = execute_query(demo_path, 
                                    params=param*2)
        
        if demografica.empty:
            print(f'El periodo:{MONTH_QUERY} no existe...')
            
            # --- Se define el mes de consulta -2--- #
            ALTER_MONTH_QUERY = (
                datetime.date.today().replace(day=1) - 
                   relativedelta(months=2)
            ).strftime(format='%Y-%m-%d')
            
            print(f"\nExtrayendo Vista Demografica:{ALTER_MONTH_QUERY[:7].replace('-','')}")
            param = [ALTER_MONTH_QUERY]
            demografica = execute_query(demo_path, 
                                        params=param*2)
        print(f'Demografica: {param[0]} consultada✅')
    except Exception as e:
        raise ErrorConsultadoDemografica(f'Error Consultado Vista Demografica: {e}') from e
    
    return {'Demografica': demografica}

def extract_perfil(perfil_path:str) -> dict[str,pd.DataFrame]:
    
    """
    Extrae el perfil de vinculación desde el DWH Bodega BI para el mes anterior
    al actual. Si el período no existe, reintenta con el mes inmediatamente
    anterior (-2 meses).

    A diferencia de la vista demográfica, esta consulta recibe un único
    parámetro de fecha en formato YYYY-MM-DD.

    Parameters
    ----------
    perfil_path : str
        Ruta al archivo SQL con la consulta del perfil de vinculación.

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario con clave 'Perfil' y el DataFrame resultante.

    Raises
    ------
    ErrorConsultadoPerfil
        Si ocurre cualquier error durante la ejecución de la consulta SQL.
    """
    
    # --- Se define el mes de consulta -1 --- #
    
    MONTH_QUERY = (datetime.date.today().replace(day=1) - 
                   relativedelta(months=1)).strftime(format='%Y-%m-%d')
    
    try:
        print("Ejecutando Query DWH Bodega BI")
        print(f"\nExtrayendo Perfil Vinculacion: {MONTH_QUERY[:7].replace('-','')}")
        param = [MONTH_QUERY]
        perfil = execute_query(perfil_path, 
                                    params=param)
        
        if perfil.empty:
            print(f'El periodo:{MONTH_QUERY} no existe...')
            
            # --- Se define el mes de consulta -2--- #
            ALTER_MONTH_QUERY = (
                datetime.date.today().replace(day=1) - 
                   relativedelta(months=2)
            ).strftime(format='%Y-%m-%d')
            
            print(f"\nExtrayendo Perfil Vinculacion:{ALTER_MONTH_QUERY[:7].replace('-','')}")
            param = [ALTER_MONTH_QUERY]
            perfil = execute_query(perfil_path, 
                                        params=param)
        print(f'Perfil Vinculación: {param[0]} consultada✅')
    except Exception as e:
        raise ErrorConsultadoPerfil(f'Error Consultando Perfil vinculación: {e}') from e
    
    return {'Perfil':perfil}

def extract_vista360(vista_path:str) -> dict[str, pd.DataFrame]:
    
    """
    Extrae la Vista 360 desde el DWH Bodega BI para el mes anterior
    al actual. Si el período no existe, reintenta con el mes inmediatamente
    anterior (-2 meses).

    Sigue el mismo patrón de reintento que `extract_demografica` y
    `extract_perfil`: un único parámetro de fecha en formato YYYY-MM-DD.

    Parameters
    ----------
    vista_path : str
        Ruta al archivo SQL con la consulta de la Vista 360.

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario con clave 'vista_360' y el DataFrame resultante.

    Raises
    ------
    ErrorConsultadoVista360
        Si ocurre cualquier error durante la ejecución de la consulta SQL.
    """
    # --- Se define el mes de consulta -1 --- #
    
    MONTH_QUERY = (datetime.date.today().replace(day=1) - 
                   relativedelta(months=1)).strftime(format='%Y-%m-%d')
    
    try:
        print("Ejecutando Query DWH Bodega BI")
        print(f"\nExtrayendo Vista360: {MONTH_QUERY[:7].replace('-','')}")
        param = [MONTH_QUERY]
        vista_360 = execute_query(
            query=vista_path, 
            params=param*2
        )
        
        if vista_360.empty:
            print(f'El periodo:{MONTH_QUERY} no existe...')
            
            # --- Se define el mes de consulta -2--- #
            ALTER_MONTH_QUERY = (
                datetime.date.today().replace(day=1) - 
                   relativedelta(months=2)
            ).strftime(format='%Y-%m-%d')
            
            print(f"\nExtrayendo Vista360:{ALTER_MONTH_QUERY[:7].replace('-','')}")
            param = [ALTER_MONTH_QUERY]
            vista_360 = execute_query(vista_path, 
                                        params=param*2)
        print(f'Vista 360: {param[0]} consultada✅')
    except Exception as e:
        raise ErrorConsultadoVista360(f'Error consultando vista 360: {e}') from e

    return {'vista_360':vista_360}
        
def extract_r10(r10_sql_path:str) -> dict[str,pd.DataFrame]:

    """
    Extrae la población R10 desde el DWH GCC.

    Es un insumo común a los procesos que necesitan cartera R10
    (Moras Tempranas e Inactivos), por lo que se extrae una sola vez acá
    en lugar de que cada pipeline la solicite por separado contra GCC.

    Parameters
    ----------
    r10_sql_path : str
        Ruta al archivo SQL con la consulta de la población R10.

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario con clave 'r10' y el DataFrame resultante.
    """
    print("\nExtrayendo poblacion r10")
    r10 = execute_query_gcc(query=r10_sql_path)
    print("R10 consultada✅")

    return {'r10': r10}

def extract_commons(demo_path:str,
                    perfil_path:str,
                    r10_sql_path:str,
                    vista_path:str,
                    common_paths:dict[str,dict]) -> dict[str,pd.DataFrame]:

    """
    Orquesta la extracción de todos los insumos comunes a los procesos del proyecto.

    Ejecuta en secuencia:
        1. Extracción de la vista demográfica desde el DWH Bodega BI.
        2. Extracción del perfil de vinculación desde el DWH Bodega BI.
        3. Extracción de la Vista 360 desde el DWH Bodega BI.
        4. Extracción de la población R10 desde el DWH GCC.
        5. Lectura de archivos Excel comunes desde rutas locales.

    Una vez consolidados, persiste todos los insumos en la capa raw del mes
    en curso bajo `data/raw/YYYYMM/` y retorna el diccionario completo para
    continuar el pipeline en memoria.

    Parameters
    ----------
    demo_path : str
        Ruta al archivo SQL con la consulta de la vista demográfica.
    perfil_path : str
        Ruta al archivo SQL con la consulta del perfil de vinculación.
    r10_sql_path : str
        Ruta al archivo SQL con la consulta de la población R10.
    vista_path : str
        Ruta al archivo SQL con la consulta de la Vista 360.
    common_paths : dict[str, dict]
        Diccionario con la configuración de cada archivo Excel común
        (ver `extract_files` en `src.utils.helpers`).

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario consolidado con todos los insumos comunes indexados
        por nombre, listo para ser consumido por los pipelines de cada proceso.

    Raises
    ------
    ErrorConsultadoDemografica
        Si falla la extracción de la vista demográfica.
    ErrorConsultadoPerfil
        Si falla la extracción del perfil de vinculación o de la Vista 360.
    Exception
        Si falla la lectura de algún archivo Excel o la exportación a disco.
    """
    # --- Se instancia el diccionario recopilador --- #
    common_files = {}
    # --- Se extrae la vista demografica --- #
    common_files.update(extract_demografica(demo_path))
    # --- Se extrae el perfil de vinculacion --- #
    common_files.update(extract_perfil(perfil_path))
    # --- Se extrae la vista 360 --- #
    common_files.update(extract_vista360(vista_path))
    # --- Se extrae la poblacion r10 --- #
    common_files.update(extract_r10(r10_sql_path))
    # --- Se extrae archivos sueltos --- #
    common_files.update(extract_files(common_paths))
    
    # --- Se persisten los archivos en memoria --- #
    common_files = exportar(
        fac=None,
        files=common_files
    )
    return common_files