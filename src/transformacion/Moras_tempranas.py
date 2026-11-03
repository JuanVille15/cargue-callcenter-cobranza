import pandas as pd
import numpy as np
import datetime
from pathlib import Path
from src.utils import exepciones

def filtrar_r10(r10:pd.DataFrame) -> pd.DataFrame:
    
    """
    Normaliza los nombres de columnas del R10 y aplica los filtros de elegibilidad
    para el proceso de Moras Tempranas.

    Los criterios de elegibilidad son:
        - Edad de cartera hoy: 3 o 4 meses.
        - Antigüedad en Coomeva: mayor a 2 años.
        - Cuotas canceladas: 24 o más.
        - Estado Multiactiva: 'Activo Cobranza Interna'.
        - Tipo de cliente: 'Mixto (Asociado/Cliente)' o 'Solo Asociado'.

    Retorna únicamente las columnas necesarias para las etapas siguientes:
    CEDULA_ASOCIADO, NOMBRE_ASOCIADO, EDAD_CARTERA_INICIAL y SUBCAMPANA.

    Parameters
    ----------
    r10 : pd.DataFrame
        DataFrame crudo extraído desde el DWH con la población R10.
        Es un insumo compartido con otros pipelines (vía `common_files`),
        por lo que acá se trabaja sobre una copia y no se lo muta en sitio.

    Returns
    -------
    pd.DataFrame
        DataFrame filtrado y reducido a las columnas necesarias.
        CEDULA_ASOCIADO es convertida a entero.
    """
    #---Se normaliza los nombres del r10 (sobre copia, r10 es compartido) ---#

    r10 = r10.copy()
    r10.columns = (r10.columns
                   .str.replace(' ','_')
                   .str.strip()
                   .str.upper()
                   .str.replace('Ñ','N'))

    # --- Se generan filtros dentro del r10 original --- #
    ## --- Lista de columnas finales --- ##
    columnas_necesarias = ['CEDULA_ASOCIADO', 
                           'NOMBRE_ASOCIADO', 
                           'EDAD_CARTERA_INICIAL', 
                           'SUBCAMPANA']
    
    r10 = (r10
           .loc[(r10['EDAD_CARTERA_HOY']
                 .astype(int)
                 .isin([3,4])
                 ) &
                (r10['ANTIGUEDAD_DEL_ASOCIADO_EN_COOMEVA'] > 2
                 ) &
                (
                    r10['NO_CUOTAS_CANCELADAS'] >= 24
                ) &
                (
                    r10['ESTADO_COOMEVA_HOY'] == 'Activo Cobranza Interna'
                ) &
                (
                  r10['TIPO_CLIENTE']
                  .isin(['Mixto (Asociado/Cliente)','Solo Asociado'])  
                )
                ,columnas_necesarias]
           .assign(
               CEDULA_ASOCIADO = lambda df: df['CEDULA_ASOCIADO'].astype(int)
           )
           )

    return r10

def filtrar_aliviosp(alivio_sp:pd.DataFrame) -> pd.DataFrame:
    
    """
    Normaliza los nombres de columnas del archivo Alivio SP y lo prepara
    como base de cruce contra la población R10.

    Pasos aplicados:
        - Elimina registros sin fecha de envío a operaciones.
        - Elimina duplicados por cédula, conservando el primero.
        - Agrega la columna indicadora APLICA_SP = 'SI'.

    Parameters
    ----------
    alivio_sp : pd.DataFrame
        DataFrame crudo leído desde el archivo Excel de Alivio SP,
        hoja 'CONSOLIDADO APLICACIONES'. Es un insumo compartido con
        Inactivos (vía `common_files`), por lo que acá se trabaja sobre
        una copia y no se lo muta en sitio.

    Returns
    -------
    pd.DataFrame
        DataFrame limpio con los asociados que ya tienen SP aplicado.
    """
    # --- Normalizar el nombre de las columnas (sobre copia, alivio_sp es compartido) --- #

    alivio_sp = alivio_sp.copy()
    alivio_sp.columns = (alivio_sp.columns
                         .str.replace(' ','_')
                         .str.strip()
                         .str.upper()
                         )
    
    # --- Eliminar vacios // Duplicados por cedula // aplica_sp --- #
    
    alivio_sp = (alivio_sp
                 .dropna(subset='FECHA_ENVIO_OPERACIONES', 
                         ignore_index=True)
                 .drop_duplicates(subset='CEDULA_ASOCIADO', 
                                  ignore_index=True)
                 .assign(APLICA_SP = 'SI')
                 )

    return alivio_sp

def filter_aliviofinanciero(alivio_financiero:pd.DataFrame) -> pd.DataFrame:
    
    """
    Normaliza los nombres de columnas del archivo Alivio Financiero y lo prepara
    como base de cruce contra la población R10.

    Pasos aplicados:
        - Filtra registros con estado 'APLICADO' o 'EN PROCESO'.
        - Elimina duplicados por identificación, conservando el primero.
        - Agrega la columna indicadora APLICA_FINAN = 'SI'.
        - Renombra IDENTIFICACION_ASOCIADO → CEDULA_ASOCIADO para unificar clave.

    Parameters
    ----------
    alivio_financiero : pd.DataFrame
        DataFrame crudo leído desde el archivo Excel de Alivio Financiero.
        Es un insumo compartido con Inactivos (vía `common_files`), por lo
        que acá se trabaja sobre una copia y no se lo muta en sitio.

    Returns
    -------
    pd.DataFrame
        DataFrame limpio con los asociados que tienen alivio financiero vigente.
    """
    # --- Normalizar el nombre de las columnas (sobre copia, alivio_financiero es compartido) --- #

    alivio_financiero = alivio_financiero.copy()
    alivio_financiero.columns = (
        alivio_financiero.columns
        .str.replace(' ','_')
        .str.replace('ó','o')
        .str.strip()
        .str.upper()
    )
    
    # --- Estado: APLICADO O EN PROCESO // Duplicados por cedula // APLICA_FINAN --- #
    
    alivio_financiero = (
        alivio_financiero
        .loc[(
            alivio_financiero['ESTADO'] == 'APLICADO'
            ) | 
             (
            alivio_financiero['ESTADO'] == 'EN PROCESO'
        ), 
            :]
        .drop_duplicates(
            subset='IDENTIFICACION_ASOCIADO', 
            ignore_index=True
        )
        .assign(
            APLICA_FINAN = 'SI'
        )
        .rename(columns={
            'IDENTIFICACION_ASOCIADO':'CEDULA_ASOCIADO'
        }
        
        )
    )

    return alivio_financiero

def filter_perseverados(perseverados:pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza los nombres de columnas del archivo de perseverados y lo prepara
    como base de cruce contra la población R10.

    Pasos aplicados:
        - Elimina duplicados por identificación, conservando el primero.
        - Agrega la columna indicadora APLICA_PER = 'SI'.
        - Renombra IDENTIFICACION → CEDULA_ASOCIADO para unificar clave.

    Parameters
    ----------
    perseverados : pd.DataFrame
        DataFrame crudo leído desde el archivo Excel de perseverados.

    Returns
    -------
    pd.DataFrame
        DataFrame limpio con los asociados identificados como perseverados.
    """
    # --- Normalizar el nombre de las columnas --- #
    
    perseverados.columns = (
        perseverados.columns
        .str.replace(' ','_')
        .str.strip()
        .str.upper()
    )
    
    # --- Duplicados por Identificacion // APLICA_PER --- #
    
    perseverados = (
        perseverados.drop_duplicates(
            subset='IDENTIFICACION', 
            ignore_index=True
        )
        .assign(
            APLICA_PER = 'SI'
        )
        .rename(
            columns={
                'IDENTIFICACION':'CEDULA_ASOCIADO'
            }
        )
    )

    return perseverados

def filter_acr(acr:pd.DataFrame) -> pd.DataFrame:
    
    """
    Normaliza los nombres de columnas del archivo ACR y lo prepara
    como base de cruce contra la población R10.

    Pasos aplicados:
        - Elimina duplicados por cédula, conservando el primero.
        - Agrega la columna indicadora APLICA_ACR = 'SI'.
        - Renombra CEDULA → CEDULA_ASOCIADO para unificar clave de join.

    Parameters
    ----------
    acr : pd.DataFrame
        DataFrame crudo leído desde el archivo Excel ACR, hoja 'Consolidado'.
        Debe contener la columna 'CEDULA'.

    Returns
    -------
    pd.DataFrame
        DataFrame limpio con los asociados con ACR activo,
        listo para cruzar con R10 vía cruzar_poblacion.
    """
     
    # --- Normalizar el nombre de las columnas --- #
    
    acr.columns = (
        acr.columns
        .str.replace(' ','_')
        .str.strip()
        .str.upper()
    )
    
    # --- Se eliminan los duplicados / Se crea columna APLICA_ACR --- #
    
    acr = (
        acr
        .drop_duplicates(
            subset='CEDULA', 
            ignore_index=True, 
            keep='first', 
        )
        .assign(
            APLICA_ACR = 'SI', 
            CEDULA = lambda df: pd.to_numeric(
                df['CEDULA'], 
                errors='coerce', 
            )
        )
        .rename(
            columns={
                'CEDULA':'CEDULA_ASOCIADO'
            }
        )
    )
    
    return acr
    

def cruzar_poblacion(r10:pd.DataFrame, 
                     base_cruce:pd.DataFrame) -> pd.DataFrame:
    """
    Cruza la población R10 contra una base de filtro mediante un left merge,
    e indica con 'SI'/'NO' si cada asociado aplica a esa base.

    La columna indicadora se detecta automáticamente buscando cualquier columna
    cuyo nombre contenga el prefijo 'APLICA_'. Los registros sin match quedan
    marcados como 'NO'.

    Esta función es genérica y se llama una vez por cada base de cruce
    (alivio_sp, alivio_financiero, perseverados).

    Parameters
    ----------
    r10 : pd.DataFrame
        DataFrame con la población R10 filtrada, indexada por CEDULA_ASOCIADO.
    base_cruce : pd.DataFrame
        DataFrame preparado por alguna de las funciones filtrar_* / filter_*,
        que contiene CEDULA_ASOCIADO y una columna con prefijo 'APLICA_'.

    Returns
    -------
    pd.DataFrame
        R10 enriquecido con la columna indicadora de la base de cruce.
    """
    
    # --- Se extrae el nombre de la columna a fillear --- #
    
    columna = str([c for c in base_cruce.columns if 'APLICA_' in c][0])
    
    # --- Se genera el merge población vs bases filtro --- #
    
    r10 = (
        r10.merge(
            right=base_cruce[['CEDULA_ASOCIADO',columna]]
            .assign(
                CEDULA_ASOCIADO = lambda df: df['CEDULA_ASOCIADO'].astype('Int64')
            ), 
            how= 'left', 
            on='CEDULA_ASOCIADO', 
        )
    )
    
    # --- Se rellena la columna con 'NO' --- #
    
    r10[columna] = r10[columna].fillna('NO')
    
    # --- Se filtran solo donde aparece 'NO' --- #
    
    r10 =(
        r10[r10[columna] == 'NO']
    )
    
    return r10

def create_fac_base(r10:pd.DataFrame, 
                    fac:pd.DataFrame) -> pd.DataFrame:
    """
    Filtra la facturación a los asociados presentes en R10, la pivotea por
    código de contrato y la une con R10 para enriquecer con datos de cartera.

    Pasos aplicados:
        - Filtra fac conservando solo los ASO_IDENTIFICACION presentes en R10.
        - Pivotea FACT_VALOR_VENCIDO por CON_CODIGO (suma), usando
          ASO_IDENTIFICACION como índice. Valores sin dato quedan en 0.
        - Merge left de la tabla pivoteada con R10, uniendo
          ASO_IDENTIFICACION (fac) con CEDULA_ASOCIADO (r10).
        - Elimina la columna CEDULA_ASOCIADO redundante tras el merge.

    Parameters
    ----------
    r10 : pd.DataFrame
        DataFrame con la población R10 filtrada.

    Returns
    -------
    pd.DataFrame
        Tabla pivoteada por tipo de contrato, enriquecida con los campos
        de cartera provenientes de R10.
    """
    # --- Se filtra la base de facturación --- #
    
    fac = (
        fac[(
            fac['ASO_IDENTIFICACION'].astype(int).isin(
                r10['CEDULA_ASOCIADO']
            )
        )
            ][['ASO_IDENTIFICACION', 
               'CON_CODIGO', 
               'FACT_VALOR_VENCIDO']
              ]
    )
    
    # --- Se pivotea la factura --- #
    tbl_factura = (pd.pivot_table(
        data=fac, 
        values='FACT_VALOR_VENCIDO', 
        columns='CON_CODIGO', 
        aggfunc='sum', 
        index=['ASO_IDENTIFICACION'],
        fill_value=0
    )
                   .reset_index(
                       drop=False,
                   )
    )
    
    tbl_factura.columns.name = None
    
    # --- se genera el merge entre fac y r10 --- #
    
    tbl_factura = (
        tbl_factura
        .merge(
            right=r10, 
            how='left', 
            left_on='ASO_IDENTIFICACION', 
            right_on='CEDULA_ASOCIADO'
        )
        .drop(
            columns='CEDULA_ASOCIADO'
        )
    )

    return tbl_factura

def create_final_base(tbl_factura:pd.DataFrame, 
                      columnas:list) ->pd.DataFrame:
    
    """
    Calcula las columnas del modelo de condonación sobre la tabla de facturación
    enriquecida, aplica el filtro de elegibilidad final y persiste el resultado
    en la capa processed.

    Columnas calculadas:
        - PORCENTAJE_CONDONACION : 50% si edad de cartera inicial es 3, 40% si es 4.
        - TOTAL_ADEUDADO          : suma de AUX.FUN. + SOLIDAR. + SOLIDARE.
        - TOTAL_A_PAGAR_POR_COOMEVA : porcentaje del total adeudado, con tope de $750.000.
        - TOTAL_A_PAGAR_POR_ASOCIADO: total adeudado menos lo que asume Coomeva.
        - TOTAL_A_CONDONAR        : suma de APORTES + CALAMID + RECREA.

    Solo se conservan los registros donde TOTAL_A_PAGAR_POR_ASOCIADO > 0.
    El resultado se exporta como Excel en data/processed/YYYYMM/AlivioMT/YYYYMM.xlsx.

    Parameters
    ----------
    tbl_factura : pd.DataFrame
        DataFrame resultado de create_fac_base, con columnas de facturación
        y cartera unificadas.
    columnas : list
        Lista de columnas a conservar en el resultado final.

    Returns
    -------
    pd.DataFrame
        Base de asociados iniciales elegibles con todas las columnas
        del modelo de condonación calculadas.

    Raises
    ------
    ExportacionAlivioMTError
        Si ocurre un error al escribir el archivo Excel en disco.
    """
    # --- Crear columna Porcentaje Condonacion --- #
    
    tbl_factura['PORCENTAJE_CONDONACION'] = (
        np.where(
            tbl_factura['EDAD_CARTERA_INICIAL'] == 3, 
            0.5, 
            0.4
        )
    )
    
    # --- Columna Total Adeudado --- #
    
    tbl_factura['TOTAL_ADEUDADO'] = (
        (
        tbl_factura['AUX.FUN.'] + 
        tbl_factura['SOLIDAR.'] +
        tbl_factura['SOLIDARE']
        )
        .astype('int64')
    )
    
    # --- Columna Total a pagar Coomeva --- #
    
    tbl_factura['TOTAL_A_PAGAR_POR_COOMEVA'] = (
        np.where(
            (
                (tbl_factura['TOTAL_ADEUDADO']*tbl_factura['PORCENTAJE_CONDONACION']).astype(int) > 750_000
            ), 
            750_000, 
            (tbl_factura['TOTAL_ADEUDADO']*tbl_factura['PORCENTAJE_CONDONACION']).astype(int)
        )
    )
    
    # --- Columna: Total a pagar Asociado --- #
    
    tbl_factura['TOTAL_A_PAGAR_POR_ASOCIADO'] = (
        (tbl_factura['TOTAL_ADEUDADO'] - 
         tbl_factura['TOTAL_A_PAGAR_POR_COOMEVA'])
        .astype(int)
    )
    
    # --- Columna Total a condonar --- #
    
    tbl_factura['TOTAL_A_CONDONAR'] = (
        (
            tbl_factura['APORTES'] + 
            tbl_factura['CALAMID'] +
            tbl_factura['RECREA'] 
        ).astype(int)
    )

    # --- Persiste tbl_factura into proccesed --- #
    
    tbl_factura = tbl_factura.loc[
        tbl_factura['TOTAL_A_PAGAR_POR_ASOCIADO'] > 0, 
        columnas
    ]
    
    BASE_PATH = Path(__file__).parents[2].resolve()
    MONTH = datetime.date.today().strftime(format='%Y%m')
    OUTP_PATH = BASE_PATH / 'data' / 'processed' / MONTH / 'AlivioMT'
    
    if not OUTP_PATH.exists():
        print(f"El directorio: {OUTP_PATH} no existe")
        print(f"Creando directorio:{OUTP_PATH}...")
        OUTP_PATH.mkdir(parents=True, 
                        exist_ok=True)
        
    try:
        with pd.ExcelWriter(f'{OUTP_PATH}/{MONTH}.xlsx', 
                        engine='openpyxl', 
                        ) as file:
            tbl_factura.to_excel(file, 
                             index=False)
        print(f'Archivo Inicial - {MONTH}.xlsx creado...')
    except Exception as e:
        raise exepciones.ExportacionAlivioMTError(f'Error Exportando: {OUTP_PATH.name} - {e}')
    
    return tbl_factura