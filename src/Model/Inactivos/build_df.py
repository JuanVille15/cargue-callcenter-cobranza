
import pandas as pd
import numpy as np
import janitor
from src.utils.exepciones import EmptyDataFrameError
from src.utils.helpers import winsorizar

# =====================
# ALISTAR EL DF INICIAL
# =====================

def serie_oferta_inicial(oferta_inactivos:pd.DataFrame, 
) -> pd.DataFrame:
    
    """
    Reduce la oferta inicial de Inactivos a la lista de cédulas únicas
    que van a alimentar el resto del feature engineering.

    Elimina duplicados por CEDULA, conserva solo esa columna y la castea
    a entero. Trabaja sobre una copia, sin mutar `oferta_inactivos`.

    Parameters
    ----------
    oferta_inactivos : pd.DataFrame
        Base final de `build_final_base` (transformacion/Inactivos.py),
        con al menos la columna CEDULA.

    Returns
    -------
    pd.DataFrame
        DataFrame de una sola columna (CEDULA), sin duplicados.

    Raises
    ------
    EmptyDataFrameError
        Si no queda ningún registro tras eliminar duplicados.
    """
    oferta_inactivos = (
        oferta_inactivos.copy()
        .drop_duplicates(
            subset='CEDULA', 
            ignore_index=True, 
        )
        .loc[
            :, 
            ['CEDULA']
        ]
        .astype(int)
    )
    
    print(f'Registros Iniciales Alivio Inactivos: {int(oferta_inactivos.shape[0])}')
    if oferta_inactivos.empty:
        raise EmptyDataFrameError('No hay registros que cumplan condiciones iniciales')

    return oferta_inactivos


# ==========================
# TRANSFORMAR BASES FEATURES
# ===========================

def perfil_vinculacion(perfil:pd.DataFrame, 
) -> pd.DataFrame:
    
    """
    Prepara el perfil de vinculación (vista Bodega BI) como insumo de
    features para el modelo de Inactivos.

    Conserva fecha de inserción, identificación y agrupación de perfil,
    renombra columnas a la convención del proyecto (CEDULA, PERFIL,
    FECHA) y castea tipos (FECHA a datetime, CEDULA a entero). Trabaja
    sobre una copia, sin mutar `perfil`.

    Parameters
    ----------
    perfil : pd.DataFrame
        DataFrame crudo de la vista de perfil de vinculación
        (`common_files['Perfil']`).

    Returns
    -------
    pd.DataFrame
        DataFrame con columnas CEDULA y PERFIL, listo para cruzar contra
        la oferta de Inactivos.
    """    
    perfil = (
        perfil.copy()
        .loc[
            :, 
            ['dtmFechaInsercion', 
             'strIdentificacion', 
             'strAgrupacionPerfil']
        ]
        .rename(
            columns={
                'strIdentificacion': 'CEDULA', 
                'strAgrupacionPerfil': 'PERFIL', 
                'dtmFechaInsercion': 'FECHA', 
            }
        )
        .assign(
            FECHA = lambda df:
                pd.to_datetime(df['FECHA'], 
                               errors='coerce'),
            CEDULA = lambda df:
                df['CEDULA'].astype(int)
        )
    )

    return perfil[['CEDULA', 'PERFIL']]

def vista_360(
    vista360:pd.DataFrame, 
    ini_cols:list[str], 
    rename_map: dict[str,str], 
    output_cols:list[str], 
) -> pd.DataFrame:

    """
    Prepara la Vista 360 como insumo de features, derivando período y
    llave de cosecha por asociado.

    Pasos aplicados:
        - Filtra a `ini_cols` y renombra columnas según `rename_map`.
        - Castea FECHA a datetime y deriva ANO, MES (con cero a la
          izquierda) y PERIODO (ANO + MES concatenados).
        - Deriva LLAVE_COSECHA como CEDULA + '_' + PERIODO.
        - Castea CEDULA a entero.
        - Recorta el resultado a `output_cols`.

    Trabaja sobre una copia, sin mutar `vista360`.

    Parameters
    ----------
    vista360 : pd.DataFrame
        DataFrame crudo de la Vista 360 (`common_files['vista_360']`).
    ini_cols : list[str]
        Columnas a conservar de `vista360` antes de transformar.
    rename_map : dict[str, str]
        Mapeo de nombres originales a los nombres usados en el proyecto
        (debe incluir la columna de fecha renombrada a 'FECHA' y la de
        identificación a 'CEDULA').
    output_cols : list[str]
        Columnas finales a retornar, una vez calculadas ANO, MES,
        PERIODO y LLAVE_COSECHA.

    Returns
    -------
    pd.DataFrame
        Vista 360 transformada, recortada a `output_cols`.
    """
    # --- Filtramos las columnas necesarias y renombramos --- #
    
    vista360 = (
        vista360.copy()
        .loc[
            :,
            ini_cols, 
        ]
        .rename(
            columns=rename_map,
        )
    )
    
    # --- Nuevas columnas y asegurar tipos de datos --- #
    
    vista360 = (
        vista360
        .assign(
            FECHA = pd.to_datetime(
                vista360['FECHA'], 
                errors='coerce',
            ), 
            ANO = lambda df:
                df['FECHA']
                .dt.year.astype(str), 
            MES = lambda df:
                df['FECHA']
                .dt.month.astype(str).str.zfill(2), 
            PERIODO = lambda df:
                (
                    df['ANO'] + df['MES']
                ), 
            LLAVE_COSECHA = lambda df:
                (
                    df['CEDULA'].astype(str) + '_' + df['PERIODO']
                ), 
            CEDULA = lambda df:
                df['CEDULA'].astype(int)
        )
    )

    return vista360[output_cols]

def reactivaciones_previas(
    consol_inactivos:pd.DataFrame, 
) -> pd.DataFrame:

    """
    Cuenta cuántas reactivaciones previas tiene cada asociado, a partir
    del consolidado histórico de reactivados.

    Normaliza nombres de columnas (`janitor.clean_names`), castea CEDULA
    a entero (valores no numéricos se imputan a 0) y MES_REACTIVACION a
    fecha (formato dd/mm/YYYY). Descarta registros sin fecha válida y
    agrupa por CEDULA, contando el número de reactivaciones.

    Parameters
    ----------
    consol_inactivos : pd.DataFrame
        DataFrame crudo del consolidado de reactivados
        (`common_files['consol_inactivos']`).

    Returns
    -------
    pd.DataFrame
        DataFrame con columnas CEDULA y REACTIVACIONES_ANTERIORES, una
        fila por asociado con al menos una reactivación con fecha válida.
    """
    # --- Se Normalizan los nombres --- #
    
    reactivaciones = (
        janitor.clean_names(
            df = consol_inactivos.copy(), 
            case_type='upper', 
            strip_accents=True, 
        )
    )
    
    # --- Se aseguran tipos y se cuentan las reactivaciones --- #
    
    reactivaciones = (
        reactivaciones
        .assign(
            CEDULA = lambda df:
                pd.to_numeric(
                    df['CEDULA'], 
                    errors='coerce', 
                )
                .fillna(0)
                .astype(int), 
            MES_REACTIVACION = lambda df:
                pd.to_datetime(
                    df['MES_REACTIVACION'], 
                    format='%d/%m/%Y', 
                    errors='coerce', 
                )
        )
        .dropna(
            subset='MES_REACTIVACION', 
            ignore_index=True, 
        )
        .groupby(
            by='CEDULA', 
        )
        .size()
        .reset_index(
            name='REACTIVACIONES_ANTERIORES',  
        )
    )

    return reactivaciones

# ================================
# CREACION BASE FINAL - INFERENCIA
# ================================

def cruce_bases(
    oferta_inactivos:pd.DataFrame, 
    perfil:pd.DataFrame, 
    vista360:pd.DataFrame, 
    reactivaciones:pd.DataFrame, 
) -> pd.DataFrame:

    """
    Cruza la oferta inicial de Inactivos con las bases de features
    (perfil de vinculación, Vista 360 y reactivaciones previas).

    Encadena tres left_join por CEDULA, partiendo de `oferta_inactivos`,
    y elimina duplicados remanentes por CEDULA (conservando el primero).

    Parameters
    ----------
    oferta_inactivos : pd.DataFrame
        Cédulas de la oferta inicial (output de `serie_oferta_inicial`).
    perfil : pd.DataFrame
        Perfil de vinculación ya transformado (output de la función
        `perfil_vinculacion`).
    vista360 : pd.DataFrame
        Vista 360 ya transformada (output de la función `vista_360`).
    reactivaciones : pd.DataFrame
        Conteo de reactivaciones previas (output de
        `reactivaciones_previas`).

    Returns
    -------
    pd.DataFrame
        Base cruzada con una fila por CEDULA, enriquecida con perfil,
        Vista 360 y reactivaciones previas.
    """
    # --- Se cruzan todas las bases y se eliminan duplicados --- #
    
    base_final = (
        pd.merge(
            left=oferta_inactivos, 
            right=perfil, 
            how='left', 
            on='CEDULA', 
        )
        .merge(
            right=vista360, 
            how='left', 
            on='CEDULA', 
        )
        .merge(
            right=reactivaciones, 
            how='left', 
            on='CEDULA', 
        )
        .drop_duplicates(
            subset='CEDULA', 
            ignore_index=True, 
            keep='first', 
        )
    )

    return base_final

def final_matrix(
    base_final:pd.DataFrame, 
    col_order: list[str], 
) -> tuple[pd.DataFrame, pd.DataFrame]:

    """
    Construye la matriz de features final para el modelo de Inactivos:
    ordena columnas, imputa nulos, winsoriza numéricas, normaliza
    categóricas y aplica one-hot encoding.

    Pasos aplicados:
        - Valida que `base_final` tenga todas las columnas de `col_order`
          (levanta KeyError si falta alguna) y reordena según esa lista.
        - Imputa nulos de PERFIL con 'Operativo'.
        - Imputa con 0 los nulos de las columnas numéricas (excluyendo
          CEDULA de esa lista).
        - Winsoriza cada columna numérica (ver `winsorizar` en
          `utils/helpers.py`), acotando outliers por IQR.
        - Reemplaza 'NC' por 'Operativo' en PERFIL.
        - Agrupa TIPO_VINCULACION en las categorías conocidas
          ('Profesional', 'Mayor 60', 'Técnicos y Tecnólogos') y el resto
          como 'Otros'.
        - Aplica one-hot encoding sobre PERFIL y TIPO_VINCULACION.

    Parameters
    ----------
    base_final : pd.DataFrame
        Base cruzada (output de `cruce_bases`), con todas las columnas
        de negocio y de features sin procesar.
    col_order : list[str]
        Orden y subconjunto de columnas requerido por el modelo.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        - x_features : matriz de features one-hot, sin la columna CEDULA,
          lista para el modelo.
        - base_final : base intermedia (post-imputación, winsorización y
          normalización de categóricas, sin one-hot), con CEDULA intacta
          para el join posterior con las predicciones.

    Raises
    ------
    KeyError
        Si `col_order` incluye alguna columna que no existe en
        `base_final`.
    """
    # --- Se le da orden a las columnas --- #
    ## --- Se valida si estan todas las columnas --- ##
    
    col_faltantes = [
        c for c in col_order
        if c not in base_final.columns
    ]
    
    if col_faltantes:
        raise KeyError(
            f'Faltan columnas requeridas en base final'
            f'\nFaltantes: {col_faltantes}'
        )
    else:
        base_final = base_final[col_order]
        
    # --- Se imputan los nulos de la columna perfil --- #
    
    base_final['PERFIL'] = (
        base_final['PERFIL']
        .fillna('Operativo')
    )
    
    # --- En columnas numericas: Imputar con 0 --- #
    
    col_numericas = base_final.select_dtypes(
        include='number', 
    ).columns.to_list()
    
    base_final[col_numericas] = (
        base_final[col_numericas]
        .fillna(0)
    )
    
    # --- Se winsorizan las columnas numericas --- #
    ## --- Eliminar CEDULA de las columnas numericas --- ##
    
    if 'CEDULA' in col_numericas:
        col_numericas.remove('CEDULA')
    
    for col in col_numericas:
        base_final = winsorizar(
            df=base_final, 
            columna=col, 
        )
    
    # --- Reemplazos columna categoricas --- #
    
    ## --- Se reemplaza 'NC' con Operativo en Perfil --- ##
    
    base_final['PERFIL'] = (
        base_final['PERFIL']
        .replace(
            'NC', 
            'Operativo'
        )
    )
    
    ## --- Reemplazos TIPO_VINCULACION --- ##
    
    base_final['TIPO_VINCULACION'] = (
        np.where(
            base_final['TIPO_VINCULACION'].isin(
                [
                    'Profesional', 'Mayor 60', 
                    'Técnicos y Tecnólogos', 
                ]
            ), 
            base_final['TIPO_VINCULACION'], 
            'Otros'
        )
    )
    
    # --- One-Hot: Columna Categoricas --- #
    
    x_features = (
        pd.get_dummies(
            data=base_final, 
            columns=[
                'PERFIL', 'TIPO_VINCULACION', 
            ], 
            drop_first=False, 
            dtype=int, 
        )
    )

    col_finales = [
        col for col in x_features.columns
        if col != 'CEDULA'
    ]
    
    return x_features[col_finales], base_final