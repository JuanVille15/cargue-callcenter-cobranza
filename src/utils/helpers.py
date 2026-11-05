import pandas as pd
import datetime
import os
from pathlib import Path
import yaml

def print_step(mensaje: str) -> None:
    ancho = 50
    print(f"\n{'=' * ancho}")
    print(f"  {mensaje}")
    print(f"{'=' * ancho}")
    
def load_config() -> dict:
    
    config_path = os.path.join(Path.cwd(),'config','config.yaml')
    
    if  not Path(config_path).exists():
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {config_path}")
        
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)

    return config

def _archivo_mas_reciente(directorio:str|Path,
                          patron:str = '*.xlsx') -> Path:

    """
    Busca el archivo más reciente (por fecha de modificación) dentro de
    un directorio, según un patrón de nombre.

    Parameters
    ----------
    directorio : str | Path
        Carpeta donde buscar.
    patron : str
        Patrón glob para filtrar archivos (por defecto '*.xlsx').

    Returns
    -------
    Path
        Ruta al archivo más reciente encontrado.

    Raises
    ------
    FileNotFoundError
        Si no hay archivos que coincidan con el patrón en el directorio.
    """
    directorio = Path(directorio)
    archivos = list(directorio.glob(patron))

    if not archivos:
        raise FileNotFoundError(f"No se encontraron archivos '{patron}' en {directorio}")

    return max(archivos, key=lambda f: f.stat().st_mtime)

def _carpeta_mas_reciente(directorio:str|Path) -> str:
    
    """ Busca la carpeta mas recien dentro de un directorio dado.
    Por fecha de creacion, y retorna el nombre de la carpeta."""
    
    directorio = Path(directorio)
    
    if not directorio.is_dir():
        raise NotADirectoryError(f"{directorio} no es un directorio válido.")

    carpetas = [d for d in directorio.iterdir() if d.is_dir()]
    
    if not carpetas:
        raise FileNotFoundError(f"No se encontraron carpetas en {directorio}")
    
    return max(carpetas, key=lambda d: d.stat().st_birthtime).name

def extract_files(configs:dict[str,dict]) -> dict[str,pd.DataFrame]:

    """
    Lee un conjunto de archivos Excel de forma genérica, a partir de una
    configuración declarativa por archivo.

    Es la función compartida de lectura de insumos Excel para todos los
    procesos del proyecto (MT, Inactivos, Créditos), reemplazando las
    versiones puntuales que existían antes en cada módulo de extracción.

    Cada entrada de `configs` acepta:
        - 'ruta'   : str, ruta a un .xlsx puntual O a una carpeta.
        - 'hoja'   : str | None, hoja a leer (None = primera hoja).
        - 'patron' : str, patrón glob para elegir el archivo más reciente
          cuando 'ruta' es una carpeta (default '*.xlsx').

    Si 'ruta' es una carpeta (`Path.is_dir()`), se resuelve automáticamente
    al archivo más reciente que matchee 'patron' (ver `_archivo_mas_reciente`).
    Si es un archivo puntual, se lee directamente.

    Parameters
    ----------
    configs : dict[str, dict]
        Diccionario nombre_logico -> config del archivo.

    Returns
    -------
    dict[str, pd.DataFrame]
        Diccionario con los DataFrames leídos, indexados igual que `configs`.

    Raises
    ------
    Exception
        Cualquier error de lectura (carpeta vacía, hoja inexistente,
        archivo no encontrado, etc.) detiene el proceso completo.
    """
    files = {}

    for nombre, cfg in configs.items():
        print(f"\nExtrayendo: {nombre}")
        try:
            ruta = Path(cfg['ruta'])
            if ruta.is_dir():
                if nombre == 'scoring':
                    # --- Si es scoring, buscamos la carpeta mas reciente --- #
                    carpeta_reciente = _carpeta_mas_reciente(ruta)
                    ruta = ruta / carpeta_reciente
                
                file_path = _archivo_mas_reciente(ruta, cfg.get('patron', '*.xlsx'))

            files[nombre] = pd.read_excel(file_path, sheet_name=cfg.get('hoja') or 0)
            print(f"{nombre}: Consultado✅ ({ruta.name})")
        except Exception as e:
            print(f"Error Extrayendo: {nombre} - {e}")
            raise

    return files

def exportar(fac:pd.DataFrame|None,
             files:dict[str,pd.DataFrame]) -> dict[str,pd.DataFrame]:
    
    """
    Consolida todos los DataFrames del proceso, los persiste en disco y retorna
    el diccionario completo para continuar el pipeline en memoria.

    Es una función genérica, reutilizable por cualquier módulo de extracción
    (MT, Inactivos, etc.) que necesite volcar sus insumos a la capa raw.

    Si se recibe `fac`, se incorpora al diccionario `files` antes de exportar,
    de modo que quede centralizado junto a los demás insumos. `fac` es opcional
    porque no todos los procesos que reutilicen esta función van a tener un
    DataFrame de facturación — se puede omitir pasando None.

    El formato de exportación se decide por volumen, no por nombre de clave:
    cualquier DataFrame con más de 1_000_000 de filas se exporta como Parquet
    (Excel tiene un límite duro de 1_048_576 filas por hoja); el resto se
    exporta como Excel.

    La carpeta de destino se construye dinámicamente con el formato `YYYYMM`
    bajo `<raiz_proyecto>/data/raw/`. Si no existe, se crea automáticamente.

    Parameters
    ----------
    fac : pd.DataFrame | None
        DataFrame con la facturación de clientes estatutarios, si el proceso
        que llama a esta función lo produce. Si es None, no se agrega nada
        adicional a `files`.
    files : dict[str, pd.DataFrame]
        Diccionario con los insumos del proceso a exportar, donde cada clave
        se usa como nombre del archivo de salida.

    Returns
    -------
    dict[str, pd.DataFrame]
        El mismo diccionario `files`, enriquecido con `fac` si fue provisto,
        para ser usado directamente por la siguiente etapa del pipeline sin
        necesidad de leer desde disco.

    Raises
    ------
    Exception
        Cualquier error producido durante la escritura de un archivo detiene
        el proceso completo.
    """
    # --- unamos en files, la factura --- #

    if fac is not None:
        files['fac'] = fac
    
    # --- Generamos un ciclo de exportación --- #
    
    BASE_PATH = Path(__file__).parents[2].resolve()
    MONTH = datetime.date.today().strftime(format='%Y%m')
    PATH_OUT = BASE_PATH / "data" /"raw" / MONTH
    
    if not PATH_OUT.exists():
        print(f"\nCreando carpeta salida: {MONTH}")
        PATH_OUT.mkdir(parents=True, 
                       exist_ok=True)
    else:
        print(f"\nEl directorio de salida ya existe...")
        
    for k,v in files.items():
        print(f"\nExportando: {k}")
        try:
            if int(len(v)) > 1_000_000:
                v.to_parquet(f"{PATH_OUT}/{k}.parquet", 
                       index=False, 
                       engine='pyarrow')
            else:
                v.to_excel(f"{PATH_OUT}/{k}.xlsx", 
                        index=False)
                print(f"\n{k} correctamente exportado...")
        except Exception as e:
            print(f"Error Inesperado exportando: {e}")
            raise
    
    return files

def winsorizar(
    df:pd.DataFrame, 
    columna:str, 
) -> pd.DataFrame:
    
    """
    Winsoriza una columna numérica, acotando los valores atípicos a los
    límites del rango intercuartílico (IQR).

    Calcula Q1, Q3 y el IQR de la columna, y recorta (`clip`) los valores
    por fuera de [Q1 - 1.5*IQR, Q3 + 1.5*IQR] a esos mismos límites, en
    vez de eliminarlos — así ningún registro se pierde, solo se atenúa
    su valor extremo.

    Trabaja sobre una copia de `df`, sin mutar el DataFrame original.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame que contiene la columna a winsorizar.
    columna : str
        Nombre de la columna numérica a acotar.

    Returns
    -------
    pd.DataFrame
        Copia de `df` con la columna `columna` winsorizada.
    """
    # --- Se calculan los limites --- #
    q1 = df[columna].quantile(0.25)
    q3 = df[columna].quantile(0.75)
    iqr = q3 - q1
    
    limite_inferior = q1 - 1.5*iqr
    limite_superior = q3 + 1.5*iqr
    
    # --- Se genera el clipeo de la columna --- #
    df = df.copy()
    df[columna] = (
        df[columna]
        .clip(
            lower=limite_inferior, 
            upper=limite_superior, 
        )
    )
    
    return df