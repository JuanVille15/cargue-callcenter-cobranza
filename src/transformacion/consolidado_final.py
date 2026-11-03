import pandas as pd
import numpy as np
import json
import datetime

from pathlib import Path
from typing import TypedDict
from src.utils.exepciones import ColNecesariasError, AliviosCruzadosError, ErrorExportando

class PayloadConfig(TypedDict):
    TOTAL_CAMPOS: list[str]
    CAMPOS_FIJOS: dict[str, str]
    MAPEO_CAMPOS: dict[str, str]
    

# =======================
# CONSOLIDACION OFERTAS
# =======================

def consolidar_ofertas(
    outputs:dict[str,pd.DataFrame],
    cols:dict[str,list],
) -> pd.DataFrame:

    """
    Consolida las ofertas finales de los 3 procesos del proyecto
    (Moras, Inactivos, Creditos) en una sola base, lista para armar el
    payload de envío.

    Pasos aplicados:
        - Valida que cada DataFrame de `outputs` tenga las columnas
          indicadas en `cols` para esa misma clave; si falta alguna,
          detiene el proceso (`ColNecesariasError`).
        - Renombra columnas para poder cruzar por una clave común:
          unifica CEDULA (Inactivos) bajo ASO_IDENTIFICACION, distingue
          cada PORCENTAJE_CONDONACION con el sufijo del proceso
          (_MORAS, _INACTIVOS, _CREDITOS), y en Creditos renombra
          ASO_NOMBRE_COMPLETO -> NOMBRE_ASOCIADO y LLAVE -> PAGARE.
        - Cruza los 3 DataFrames por ASO_IDENTIFICACION con outer join,
          de forma que un asociado que solo aplique a uno de los
          procesos igual quede en el resultado (con NaN en los demás).
        - Unifica NOMBRE_ASOCIADO (que el merge duplica en _x/_y/sin
          sufijo) en una sola columna, priorizando Moras > Inactivos >
          Creditos.
        - Valida que ningún asociado tenga oferta simultánea de Moras
          e Inactivos (poblaciones que deberían ser excluyentes); si
          encuentra cruces, detiene el proceso (`AliviosCruzadosError`).

    Parameters
    ----------
    outputs : dict[str, pd.DataFrame]
        Diccionario con la oferta final de cada proceso, indexado por
        nombre ('Moras', 'Inactivos', 'Creditos') — resultado de unir
        los diccionarios que retornan `run_moras`, `run_inactivos` y
        `run_creditos`.
    cols : dict[str, list]
        Diccionario con las columnas requeridas de cada proceso,
        mismas claves que `outputs`.

    Returns
    -------
    pd.DataFrame
        Base consolidada con una fila por ASO_IDENTIFICACION: columnas
        ASO_IDENTIFICACION, NOMBRE_ASOCIADO,
        PORCENTAJE_CONDONACION_MORAS, PORCENTAJE_CONDONACION_INACTIVOS,
        PAGARE y PORCENTAJE_CONDONACION_CREDITOS.

    Raises
    ------
    ColNecesariasError
        Si algún DataFrame de `outputs` no tiene las columnas
        requeridas en `cols` para esa clave.
    AliviosCruzadosError
        Si algún ASO_IDENTIFICACION tiene oferta simultánea de Moras e
        Inactivos.
    """

    # --- Validacion Columnas --- #
    ## --- Hacemos un ciclo de validacion --- ##
    
    for k,v in outputs.items():
        # --- Se extraen las columnas --- #
        COL_NECESARIAS = cols[k]
        
        COL_FALTANTES = [
            c for c in COL_NECESARIAS
            if c not in v.columns
        ]

        if COL_FALTANTES:
            raise ColNecesariasError(f'Error procesando oferta: "{k}'
                                     f'\n Columnas Faltantes: {COL_FALTANTES}')
        else:
            print(f'Oferta {k} - Correctamente Entregada✅')
            outputs[k] = outputs[k][COL_NECESARIAS]
        
    # --- Se realiza la consolidacion -- Outer Join --- #
    ## --- Se aseguran nombres --- ##
    
    Moras = (
        outputs['Moras']
        .rename(
            columns={
                'PORCENTAJE_CONDONACION':'PORCENTAJE_CONDONACION_MORAS'
            }
        )
        .assign(
            MAX_APLICABLE_MORAS = 750_000, 
        )
    )
    
    Inactivos = (
        outputs['Inactivos']
        .rename(
            columns={
                'CEDULA':'ASO_IDENTIFICACION', 
                'PORCENTAJE_CONDONACION':'PORCENTAJE_CONDONACION_INACTIVOS', 
            }
        )
        .assign(
            MAX_APLICABLE_INACTIVOS = 700_000, 
        )
    )
    
    Creditos = (
        outputs['Creditos']
        .rename(
            columns={
                'ASO_NOMBRE_COMPLETO':'NOMBRE_ASOCIADO', 
                'PORCENTAJE_CONDONACION': 'PORCENTAJE_CONDONACION_CREDITOS',
                'LLAVE':'PAGARE', 
            }
        )
        .assign(
            MAX_APLICABLE_CREDITOS = 2_000_000, 
        )
    )
    
    ## --- Se realiza la combinacion de DataFrames --- #
    
    consolidado = (
        Moras
        .merge(Inactivos, on='ASO_IDENTIFICACION', how='outer')
        .merge(Creditos, on='ASO_IDENTIFICACION', how='outer')
    )
    
    ## --- Se rellena la columna nombre --- ##

    consolidado = (
        consolidado
        .assign(
            NOMBRE_ASOCIADO = lambda df:
                df['NOMBRE_ASOCIADO_x']
                .combine_first(df['NOMBRE_ASOCIADO_y'])
                .combine_first(df['NOMBRE_ASOCIADO'])
        )
        .drop(columns=['NOMBRE_ASOCIADO_x', 'NOMBRE_ASOCIADO_y'])
    )
    
    # --- Asegurar tipo INT dentro de las columnas numericas --- #
    
    col_numericas = [
        'ASO_IDENTIFICACION', 
        'PAGARE', 
        'MAX_APLICABLE_MORAS', 
        'MAX_APLICABLE_INACTIVOS', 
        'MAX_APLICABLE_CREDITOS', 
    ]
    
    for col in col_numericas:
        consolidado[col] = pd.to_numeric(
            consolidado[col], 
            errors='coerce', 
        ).astype('Int64')
    
    # --- Se debe validar que las CC de Inactivos no coincidan con las de Moras --- #
    
    validacion = (
        consolidado
        .loc[
            ((~consolidado['PORCENTAJE_CONDONACION_MORAS'].isnull()) & 
             (~consolidado['PORCENTAJE_CONDONACION_INACTIVOS'].isnull())),
            ['ASO_IDENTIFICACION']
        ]
    )
    
    if not validacion.empty:
        raise AliviosCruzadosError('Error: Se han cruzado alivio Inactivos y Moras'
                                   f'\nCantidad ids cruzados: {len(validacion)}')
    print(f'Consolidado Ofertas creado: {len(consolidado)} filas...')
    
    return consolidado

# ==================================
# GENERACION/ PERSISTENCIA: PAYLOAD
# ==================================

def build_payload(
    consolidado:pd.DataFrame, 
    payload_config:PayloadConfig, 
) -> list[dict]:
    
    """
    Arma el payload final a partir de la base consolidada y lo persiste
    como JSON en la capa Output del proyecto.

    Pasos aplicados:
        - Calcula las banderas booleanas APLICA_MORAS/APLICA_INACTIVOS/
          APLICA_CREDITOS según si cada PORCENTAJE_CONDONACION_* está
          poblado.
        - Aplica las reglas de prioridad cuando un asociado cruza en más
          de un proceso: Inactivos gana sobre Creditos, Creditos gana
          sobre Moras — en ambos casos apaga la bandera Y anula (NaN) el
          porcentaje del proceso que pierde, para que no se filtre en
          el payload. El cruce Moras/Inactivos ya está descartado desde
          `consolidar_ofertas` (no puede pasar).
        - Arma una estructura base por registro (`TOTAL_CAMPOS` en
          blanco + `CAMPOS_FIJOS` constantes) y la completa por fila
          según `MAPEO_CAMPOS`, convirtiendo nulos a `""` en vez del
          string literal `"nan"`.
        - Persiste el payload completo en
          data/output/YYYYMM/Consolidado/payload.json.

    Parameters
    ----------
    consolidado : pd.DataFrame
        Resultado de `consolidar_ofertas`.
    payload_config : PayloadConfig
        Configuración del payload: 'TOTAL_CAMPOS' (lista de todos los
        campos), 'CAMPOS_FIJOS' (valores constantes) y 'MAPEO_CAMPOS'
        (campo del payload -> columna de `consolidado`).

    Returns
    -------
    list[dict]
        Un diccionario por asociado, listo para enviar en el body del
        POST.

    Raises
    ------
    ErrorExportando
        Si falla la creación del directorio o la escritura del JSON.
    """
    # --- Columnas APLICA_ALIVIO --- #
    ## --- Indicador Booleano --- ##
    consolidado = (
        consolidado
        .assign(
            APLICA_MORAS = np.where(
                consolidado['PORCENTAJE_CONDONACION_MORAS'].isnull(),
                0, 
                1
            ), 
            APLICA_INACTIVOS = np.where(
                consolidado['PORCENTAJE_CONDONACION_INACTIVOS'].isnull(), 
                0,
                1
            ), 
            APLICA_CREDITOS = np.where(
                consolidado['PORCENTAJE_CONDONACION_CREDITOS'].isnull(), 
                0, 
                1
            )
        )
    )
    
    ## --- Reglas de negocio: Prioridad Alivio --- ##
    ### --- Cuando se cruce Inactivos y Creditos --- ###
    consolidado.loc[
        ((consolidado['APLICA_INACTIVOS'] == 1) &
        (consolidado['APLICA_CREDITOS'] == 1)),
        ['APLICA_INACTIVOS', 'APLICA_CREDITOS', 'PORCENTAJE_CONDONACION_CREDITOS']
    ] = [1, 0, np.nan]
    
    ### --- Cuando se cruce Moras y Creditos --- ###
    consolidado.loc[
        ((consolidado['APLICA_MORAS'] == 1) &
        (consolidado['APLICA_CREDITOS'] == 1)),
        ['APLICA_MORAS', 'APLICA_CREDITOS', 'PORCENTAJE_CONDONACION_MORAS']
    ] = [0, 1, np.nan]
    
    # --- GENERAMOS PAYLOAD --- #
    ## --- Estructura base --- ##
    estructura_base = {campo: "" for campo in payload_config['TOTAL_CAMPOS']}
    estructura_base.update(payload_config['CAMPOS_FIJOS'])
    
    ## --- Se persiste el mes en opt11 --- ##
    MONTH = datetime.date.today().strftime('%Y%m')
    estructura_base['opt11'] = MONTH    
    
    ## --- Se itera para los campos que se actualizan desde el df --- ## 
    
    payload = []
    for _,row in consolidado.iterrows():
        registro = estructura_base.copy()
        for k,v in payload_config['MAPEO_CAMPOS'].items():
            registro[k] = "" if pd.isna(row[v]) else str(row[v])
        payload.append(registro)
        
    # --- Persiste el payload en Output (Gold) --- #

    BASE_PATH = Path(__file__).parents[2].resolve()
    OUTPUT_PATH = BASE_PATH / 'data' / 'output' / MONTH / 'Consolidado'

    if not OUTPUT_PATH.exists():
        print(f"El directorio: {OUTPUT_PATH} no existe")
        print(f"Creando directorio: {OUTPUT_PATH}...")
        OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    try:
        with open(OUTPUT_PATH / 'payload.json', 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f'Payload Consolidado (output) - {MONTH} exportado✅')
    except Exception as e:
        raise ErrorExportando(f'Error exportando payload Consolidado: {e}') from e

    return payload