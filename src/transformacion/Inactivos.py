import pandas as pd
from pathlib import Path
import datetime
import janitor
from src.utils import exepciones

def unir_alivios(alivio:pd.DataFrame, alivio_sp:pd.DataFrame) -> pd.Series:

    """
    Consolida las dos bases de alivios ya aplicados en una sola lista de
    cédulas, para excluir esos asociados de la oferta de Inactivos.

    Pasos aplicados:
        - Normaliza nombres de columnas de ambos DataFrames (mayúsculas,
          sin tildes) vía `janitor.clean_names`.
        - Unifica la clave de cédula: `alivio` la trae en
          IDENTIFICACION_ASOCIADO, `alivio_sp` en CEDULA_ASOCIADO — ambas
          se castean a entero y se renombran a CEDULA.
        - Concatena ambas bases por filas (`pd.concat`, axis=0).
        - Elimina nulos y duplicados por CEDULA.

    Parameters
    ----------
    alivio : pd.DataFrame
        DataFrame crudo de alivios aplicados (ej. 'Alivios Aplicados MT'),
        con columna IDENTIFICACION_ASOCIADO.
    alivio_sp : pd.DataFrame
        DataFrame crudo de la segunda base de alivios (ej. 'Alivios Inac'),
        con columna CEDULA_ASOCIADO.

    Returns
    -------
    pd.Series
        Serie de cédulas únicas y no nulas, consolidada de ambas fuentes,
        lista para usarse en el anti-join contra la población filtrada.
    """
    
    alivio = alivio.copy()
    alivio_sp = alivio_sp.copy()
    
    # --- Se normalizan nombres y asegura tipos --- # 
    alivio = (janitor.clean_names(
        df=alivio, 
        case_type='upper', 
        strip_accents=True, 
    )
    .dropna(
        subset= 'IDENTIFICACION_ASOCIADO', 
        ignore_index=True, 
    )
    .assign(
        CEDULA = lambda df: 
            df['IDENTIFICACION_ASOCIADO'].astype(int)
    )
    .drop(
        columns= 'IDENTIFICACION_ASOCIADO'
    )
    )
    
    # --- Se normalizan nombres y asegura tipos --- #
    alivio_sp = (janitor.clean_names(
        df=alivio_sp, 
        case_type='upper', 
        strip_accents=True, 
    )
    .dropna(
        subset= 'FECHA_ENVIO_OPERACIONES', 
        ignore_index=True, 
    )
    .drop_duplicates(
        subset='CEDULA_ASOCIADO', 
        ignore_index=True, 
    )
    .assign(
        CEDULA = lambda df:
            df['CEDULA_ASOCIADO'].astype('Int64')
    )
    .drop(
        columns= 'CEDULA_ASOCIADO'
    )           
    )
    
    # --- Se concatenan los dos DataFrames --- #
    
    Base_alivios = (
        pd.concat(
            [alivio, alivio_sp], 
            axis=0, 
            ignore_index=True,  
        )
        .dropna(
            subset=['CEDULA']
        )
        .drop_duplicates(
            subset = 'CEDULA', 
            ignore_index=True
        )
    )

    return Base_alivios['CEDULA']

def agr_cuotas_pagadas(r10:pd.DataFrame) -> pd.DataFrame:
    
    """
    Deriva el total de cuotas pagadas por asociado a partir del R10 crudo,
    para usarlo como filtro de elegibilidad en Inactivos.

    R10 es un insumo compartido con MT (vía `common_files`), por lo que acá
    se trabaja sobre una copia y no se lo muta en sitio.

    Pasos aplicados:
        - Normaliza nombres de columnas vía `janitor.clean_names`.
        - Castea CEDULA_ASOCIADO a entero y unifica la clave a CEDULA
          (convención usada en el resto de Inactivos), renombrando también
          NO_CUOTAS_CANCELADAS a CUOTAS_PAGADAS.
        - Agrupa por CEDULA y suma CUOTAS_PAGADAS, quedando una fila
          por asociado.

    Parameters
    ----------
    r10 : pd.DataFrame
        DataFrame crudo con la población R10 extraída desde GCC
        (ver `extract_r10` en `extraccion/commons.py`).

    Returns
    -------
    pd.DataFrame
        DataFrame con columnas CEDULA y CUOTAS_CANCELADAS (suma de cuotas
        pagadas), una fila por asociado, lista para cruzar con la
        población de Inactivos.
    """
    # --- Se normalizar y se aseguran tipos en r10 --- #
    
    r10 = (
        janitor.clean_names(
            df = r10.copy(), 
            case_type='upper', 
            strip_accents=True, 
        )
        .assign(
            CEDULA_ASOCIADO = lambda df: 
                df['CEDULA_ASOCIADO'].astype(int), 
        )
        .rename(
            columns = {
                'CEDULA_ASOCIADO': 'CEDULA', 
                'NO_CUOTAS_CANCELADAS': 'CUOTAS_PAGADAS', 
            }
        )
    )
    
    # --- Se agrupa por cedula el numero de cuotas pagadas --- #
    tbl_cuotas_pagadas = (
        r10.groupby(
            by=['CEDULA','NOMBRE_ASOCIADO'],
        )
        .agg(
            CUOTAS_CANCELADAS = ('CUOTAS_PAGADAS', 'sum'), 
        )
        .reset_index(
            drop=False, 
        )
    )
    
    # --- Se trae el estado_hoy: Filtro Posterior--- #
    
    tbl_cuotas_pagadas = (
        tbl_cuotas_pagadas
        .merge(
            r10[['CEDULA','ESTADO_COOMEVA_HOY']], 
            how='left', 
            on='CEDULA', 
        )
        .drop_duplicates(
            subset='CEDULA', 
            keep='first', 
            ignore_index=True, 
        )
    )

    return tbl_cuotas_pagadas

def cruce_general(Base_alivios: pd.Series, 
                  tbl_cuotas_pagadas: pd.DataFrame, 
                  inactivos_files: dict[str, pd.DataFrame]
                  ) -> pd.DataFrame:
    """
    Cruza la población de Inactivos con scoring, homologación y cuotas
    pagadas, y excluye a los asociados que ya tienen un alivio aplicado.

    Pasos aplicados:
        - Normaliza población y scoring (`janitor.clean_names`, cédula
          casteada a entero).
        - De scoring conserva solo CEDULA, SCORING y GRUPOS.
        - left_join en cadena: población + scoring (por CEDULA) +
          homologación (GRUPOS = GRUPO_SCORING) + tbl_cuotas_pagadas
          (por CEDULA).
        - Descarta la columna auxiliar GRUPO_SCORING tras el cruce con
          homologación.
        - Excluye (anti-join) los asociados presentes en `Base_alivios`.

    Los nulos que puedan quedar tras el left_join con homologación
    (asociados sin match de scoring) no se resuelven acá — se completan
    en `build_final_base`, antes de aplicar los filtros de elegibilidad.

    Parameters
    ----------
    Base_alivios : pd.Series
        Serie de cédulas con alivio ya aplicado (output de `unir_alivios`),
        usada para excluir asociados de la oferta.
    tbl_cuotas_pagadas : pd.DataFrame
        DataFrame con columnas CEDULA y CUOTAS_CANCELADAS (output de
        `agr_cuotas_pagadas`).
    inactivos_files : dict[str, pd.DataFrame]
        Diccionario con las claves 'poblacion_inactivos' y 'scoring',
        crudos desde extracción.

    Returns
    -------
    pd.DataFrame
        Población cruzada con scoring, homologación y cuotas pagadas,
        excluyendo a quienes ya tienen alivio aplicado.
    """
    # --- Asegurar tipos de datos y filtros --- #
    
    ## --- Base de poblacion --- #
    
    poblacion = (
        janitor.clean_names(
            df=inactivos_files['poblacion_inactivos'].copy(), 
            case_type='upper', 
            strip_accents=True, 
        )
        .assign(
            CEDULA = lambda df:
                df['CEDULA'].astype(int)
        )
    )
    
    ## --- Base de scoring --- #
    
    scoring = (
        janitor.clean_names(
            inactivos_files['scoring'].copy(), 
            case_type='upper', 
            strip_accents=True, 
        )
        .assign(
            CEDULA = lambda df:
                df['ID'].astype(int)
        )
        .drop(
            columns = 'ID'
        )
        .loc[:, 
             ['CEDULA', 'CATEGORIA_SCORE']]
    )
    
    # --- Se cruzan las bases --- #
    
    ## --- Se crea la tabla homologacion --- #
    base_final = (
        pd.merge(
            left=poblacion, 
            right=scoring,
            how='left',
            on='CEDULA', 
        )
        .merge(
            right=tbl_cuotas_pagadas, 
            how='left', 
            on='CEDULA', 
        )
        .rename(
            columns={'CATEGORIA_SCORE': 'GRUPO_SCORING'}
        )
        .loc[lambda df: 
            ~df['CEDULA'].isin(Base_alivios), 
            :]
    )

    return base_final

def build_final_base(base_final:pd.DataFrame) -> pd.DataFrame:
    
    """
    Completa valores nulos de segmentación, aplica los filtros de
    elegibilidad de Inactivos y persiste el resultado en la capa processed.

    Pasos aplicados:
        - Rellena SEGMENTO_ORIGINAL, PRIORIDAD_AJUSTADA y PRIORIDAD para
          los asociados sin match en la tabla de homologación, con el
          mismo criterio que usa GRUPO_SCORING == 0 ('Verde_Perfil_Bueno_2',
          prioridad ajustada 2, 'ALTA PRIORIDAD').
        - Filtra a los asociados elegibles: PRIORIDAD == 'ALTA PRIORIDAD',
          ANTIGUEDAD > 5, CUOTAS_CANCELADAS > 12 y TIPO_PERSONA persona
          natural.
        - Exporta el resultado a data/processed/YYYYMM/AlivioInactivos/.

    Parameters
    ----------
    base_final : pd.DataFrame
        DataFrame resultado de `cruce_general`, con población, scoring,
        homologación y cuotas pagadas ya cruzados.

    Returns
    -------
    pd.DataFrame
        Base final de asociados elegibles para la oferta de Inactivos.

    Raises
    ------
    ExportacionAlivioInacError
        Si falla la escritura del archivo Excel en disco.
    """
    # --- fillear nulos antes de filtros --- #
    
    base_final = (
        base_final
        .fillna(
            {
                'GRUPO_SCORING':'Medio', 
            }
        )
    )
    
    # --- Se filtran los asociados elegibles --- #
    
    base_final = (
        base_final.loc[
            (base_final['GRUPO_SCORING'] == 'Alto') &
            (base_final['ANTIGUEDAD'] > 5) &
            (base_final['CUOTAS_CANCELADAS'] > 12) &
            (base_final['TIPO_PERSONA'].isin(['NATURAL', 
                                              'Persona Natural'])) 
        ]
    )
    
    # --- Orden de salida de las columnas --- #
    
    col = base_final.pop('NOMBRE_ASOCIADO')
    base_final.insert(
        loc=int(base_final.columns.to_list().index('CEDULA') + 1), 
        column='NOMBRE_ASOCIADO', 
        value=col
    )
    
    # --- Se eliminan asociados que no esten en estado Inactivo --- #
    ## --- Alerta de asociados no Inactivos --- ##
    NO_INACTIVOS = (base_final['ESTADO_COOMEVA_HOY'] != 'Inactivo').sum()

    if NO_INACTIVOS > 0:
        print(f'Hay {NO_INACTIVOS} asociados no Inactivos'
            '\nEliminando de la oferta inicial...')

    base_final = (
        base_final[
            base_final['ESTADO_COOMEVA_HOY'] == 'Inactivo'
        ]
        .drop(
            columns='ESTADO_COOMEVA_HOY'
        )
    )
    
    print(f'Oferta Inicial Inactivos Creada: {len(base_final)} filas...')
    
    # --- Se persiste en processed --- #
    
    BASE_PATH = Path(__file__).parents[2].resolve()
    MONTH = datetime.date.today().strftime(format='%Y%m')
    OUTP_PATH = BASE_PATH / 'data' / 'processed' / MONTH / 'AlivioInactivos'
    
    if not OUTP_PATH.exists():
        print(f"El directorio: {OUTP_PATH} no existe")
        print(f"Creando directorio:{OUTP_PATH}...")
        OUTP_PATH.mkdir(parents=True, 
                        exist_ok=True)
    
    try:
        with pd.ExcelWriter(f'{OUTP_PATH}/{MONTH}.xlsx', 
                            engine='openpyxl', 
                            ) as file:
            base_final.to_excel(
                file, 
                index=False, 
            )
            print(f'Archivo Oferta Inicial -{MONTH}.xlsx creado...')
    except Exception as e:
        raise exepciones.ExportacionAlivioInacError(f'Error exportando: {OUTP_PATH.name} - {e}') from e
    
    return base_final