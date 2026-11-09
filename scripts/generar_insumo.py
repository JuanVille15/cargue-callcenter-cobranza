import os
import pandas as pd
import pyodbc

from pathlib import Path
from datetime import date
from dotenv import load_dotenv
from src.utils.helpers import load_yaml, extract_files
from azure.storage.blob import BlobServiceClient, ContainerClient

import warnings
warnings.filterwarnings("ignore")

CARPETA_SQL = Path(__file__).parents[1] / "sql" / "ingesta"
YAML_INSUMOS = Path(__file__).parents[1] / "config" / "insumos_locales.yaml"

def obtener_contenedor():
    
    #1. Conectarse a la cuenta (en local: azurite) #
    servicio = BlobServiceClient.from_connection_string(
        os.environ["DATA_STORAGE_CONNECTION_STRING"]
    )
    
    #2. Tomar el contenedor de la cuenta #
    return servicio.get_container_client(os.environ["DATA_CONTAINER"])

def subir_df(
    contenedor: ContainerClient, 
    df: pd.DataFrame, 
    nombre_archivo: str, 
    fecha:str,
    extension:str = ".csv" 
) -> None:
    
    #1. Se crea la ruta del blob (archivo) en el contenedor #
    ruta = f"alivio/ingesta/fecha={fecha}/{nombre_archivo}{extension}"
    
    #2. Se sube el DataFrame al contenedor como un blob #
    datos = df.to_csv(index=False, sep=",").encode("utf-8")
    contenedor.upload_blob(name=ruta, data=datos, overwrite=True)
    print(f"Archivo {nombre_archivo}{extension} subido a la ruta {ruta} - contendor: {contenedor.container_name}")
    
if __name__ == "__main__":
    load_dotenv()
    contenedor = obtener_contenedor()
    fecha = date.today().strftime("%Y-%m-%d")
    
    # ===========
    # SQL QUERYS
    # ===========
    
    sql_files = [f for f in CARPETA_SQL.iterdir() if f.suffix == ".sql"]
    
    for sql_file in sql_files:
        
        # 0. Se obtiene el tipo de bodega a usar (en el nombre) #
        bodega = sql_file.stem.split("_")[0]
        
        if bodega == "gcc":
            con = pyodbc.connect(os.environ["GCC_CON"])
        else:
            con = pyodbc.connect(os.environ["CON_BI"])
        
        if bodega == 'bi':
            particion = ((date.today() - pd.DateOffset(months=2)).replace(day=1)).strftime("%Y-%m-%d")
            
        #1. Se lee el archivo SQL y se ejecuta la consulta para obtener un DataFrame #
        sql_query = sql_file.read_text(encoding="utf-8")
        print(f"Ejecutando consulta: {sql_file.name} - Bodega: {bodega} - Fecha particion: {particion if bodega == 'bi' else 'N/A'}")
        sql_query = sql_query.replace("?", particion) if bodega == 'bi' else sql_query
        df = pd.read_sql(sql_query, con) #type: ignore
        print(f"Consulta ejecutada: {sql_file.name} - Filas obtenidas: {len(df)}")
        con.close()
        
        #2. Nombre del archivo a subir al contenedor #
        nombre_archivo = sql_file.stem.split("_", 1)[1].upper() # se toma todo lo que esta despues del primer guion bajo
        
        #3. Se sube el DataFrame al contenedor #
        subir_df(contenedor, df, nombre_archivo, fecha)
        print(f"Archivo {nombre_archivo} subido al contenedor {contenedor.container_name}")
    
    # ============
    # FLAT FILES
    # ============
    
    insumos = load_yaml(YAML_INSUMOS)["archivos_planos"]
    files = extract_files(insumos)
    
    # 4. Se suben los archivos planos al contenedor #
    for nombre_archivo, df in files.items():
        subir_df(contenedor, df, nombre_archivo.upper(), fecha)
        print(f"Archivo {nombre_archivo.upper()} subido al contenedor {contenedor.container_name}")