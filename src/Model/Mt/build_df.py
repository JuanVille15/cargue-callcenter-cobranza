import pandas as pd

from src.utils.exepciones import EmptyDataFrameError

# ====================
# CREACION DF INICIAL
# ====================

def build_ini_base(tbl_factura:pd.DataFrame) -> pd.DataFrame:
    
    """
    Extrae las cédulas únicas del proceso de Moras Tempranas como punto de
    partida para el armado de la matriz del modelo.

    Toma la columna ASO_IDENTIFICACION de la tabla de facturación, elimina
    duplicados y convierte el resultado en un DataFrame de una sola columna.
    Si no hay registros, detiene el proceso con una excepción explícita.

    Parameters
    ----------
    tbl_factura : pd.DataFrame
        Tabla de facturación enriquecida, resultado de create_fac_base.
        Debe contener la columna ASO_IDENTIFICACION.

    Returns
    -------
    pd.DataFrame
        DataFrame de una sola columna (ASO_IDENTIFICACION) con las cédulas
        únicas que conforman la población inicial del modelo.

    Raises
    ------
    EmptyDataFrameError
        Si tras la deduplicación no queda ningún registro.
    """
    # --- Se crea la instancia de cedulas iniciales --- #
    alivio = (
        tbl_factura['ASO_IDENTIFICACION']
        .drop_duplicates(
            keep='first', 
            ignore_index=True, 
        )
        .to_frame(
            name='ASO_IDENTIFICACION'
        )
    )
    
    print(f'Registros iniciales Alivio MT: {int(alivio.shape[0])}')
    
    if alivio.empty:
        raise EmptyDataFrameError('No hay registros que cumplan condiciones iniciales.')

    return alivio

def demo_columns(alivio:pd.DataFrame, 
                 demografica:pd.DataFrame, 
                 cols_demografica:list) -> pd.DataFrame:
    """
    Incorpora las columnas demográficas requeridas por el modelo a la base
    de cédulas iniciales mediante un left merge.

    Antes del merge valida que todas las columnas en `cols_demografica` existan
    en el DataFrame demográfico. Las columnas de `demografica` que no sean
    necesarias para el modelo ni la clave de join son eliminadas para no
    contaminar la matriz de features.

    Parameters
    ----------
    alivio : pd.DataFrame
        Base de cédulas iniciales con columna ASO_IDENTIFICACION.
    demografica : pd.DataFrame
        Vista demográfica extraída desde el DWH Bodega BI. Debe contener
        la columna 'Identificacion' como clave de join.
    cols_demografica : list
        Lista de columnas demográficas que el modelo requiere. Toda columna
        en `demografica` que no esté en esta lista (excepto 'Identificacion')
        es eliminada antes del merge.

    Returns
    -------
    pd.DataFrame
        Base `alivio` enriquecida con las columnas demográficas del modelo.

    Raises
    ------
    KeyError
        Si alguna columna de `cols_demografica` no existe en `demografica`.
    """
    
    # --- Preparacion antes de merge --- #
    alivio = alivio.astype(int)
   
    ## --- Columnas necesarias de demografica --- #
    columnas_faltantes = [c for c in cols_demografica if c not in demografica.columns]
   
    columnas_adicionales = [c for c in demografica.columns 
                        if c not in cols_demografica and c != 'Identificacion']
    
    if columnas_faltantes:
       raise KeyError(
    f'Hay columnas faltantes en base Demografica\n'
    f'Faltantes: {columnas_faltantes}'
    )
       
    ## --- Se elimina las columnas adicionales // Se asigna type--- ##
   
    demografica = (
       demografica
       .drop_duplicates(
           subset='Identificacion',
           ignore_index=True, 
       )
       .drop(
           columns=columnas_adicionales
       )
       .assign(
           Identificacion = lambda df: df['Identificacion'].astype(int)
       )
   )
   
   # --- Merge into alivio base --- #
   
    alivio = (
       pd.merge(
           left=alivio, 
           right=demografica, 
           how='left', 
           left_on='ASO_IDENTIFICACION',  
           right_on= 'Identificacion', 
           )
       .drop(
           columns='Identificacion'
       )
   )
   
    return alivio

def cantidad_reactivaciones(consol_inactivos:pd.DataFrame, 
                            alivio:pd.DataFrame) -> pd.DataFrame:
    
    """
    Calcula la cantidad histórica de reactivaciones de cada asociado y la
    incorpora como feature a la base del modelo.

    Agrupa el consolidado de inactivos por cédula, cuenta las apariciones
    (cada fila representa una reactivación) y cruza el conteo con la base
    inicial mediante un left merge. Los asociados sin historial de
    reactivaciones quedan con valor 0.

    Parameters
    ----------
    consol_inactivos : pd.DataFrame
        Base consolidada de inactivos/reactivados. Debe contener la columna
        'Cedula'.
    alivio : pd.DataFrame
        Base de cédulas iniciales con columna ASO_IDENTIFICACION.

    Returns
    -------
    pd.DataFrame
        Base `alivio` con la columna adicional 'Cantidad_Reactivaciones'.
    """
    # --- Se toma la base de reactivados y se hace conteo --- #
    
    agr_reactivaciones = (
        consol_inactivos
        .groupby(
            by='Cedula'
        )
        .agg(
            Cantidad_Reactivaciones = ('Cedula','count')
        )
        .reset_index()
    )
    
    # --- Cruzamos con la base que pasó las condiciones iniciales --- #
    
    alivio = (
        alivio
        .merge(
            agr_reactivaciones
            .assign(Cedula = lambda df: df['Cedula'].astype('int64')), 
            how='left', 
            left_on='ASO_IDENTIFICACION', 
            right_on='Cedula'
        )
        .drop(
            columns='Cedula',
        )
        .assign(
            Cantidad_Reactivaciones = lambda df: df['Cantidad_Reactivaciones'].fillna(0)
        )
    )
    return alivio

def perfil_asociado(perfil:pd.DataFrame, 
                    alivio: pd.DataFrame) -> pd.DataFrame:

    """
    Incorpora el perfil de vinculación del asociado como feature categórica
    a la base del modelo.

    Deduplica el perfil por identificación, conserva únicamente las columnas
    necesarias y cruza con la base inicial mediante un left merge. Los
    asociados sin perfil registrado son imputados con la categoría 'Operativo',
    que corresponde al perfil más frecuente en la población.

    Parameters
    ----------
    perfil : pd.DataFrame
        Vista de perfil de vinculación extraída desde el DWH Bodega BI.
        Debe contener las columnas 'strIdentificacion' y 'strAgrupacionPerfil'.
    alivio : pd.DataFrame
        Base de cédulas enriquecida con columna ASO_IDENTIFICACION.

    Returns
    -------
    pd.DataFrame
        Base `alivio` con la columna adicional 'strAgrupacionPerfil'.
    """
    # --- Se alista la base de perfil --- #
    
    perfil = (
        perfil
        .drop_duplicates(
            subset='strIdentificacion'
        )
        .assign(strIdentificacion = lambda df: df['strIdentificacion'].astype(int))
        .loc[
            :,
            ['strIdentificacion', 
             'strAgrupacionPerfil']
        ]
    )
    
    # --- Cruzar con la base original de alivio --- #
    
    alivio = (
        alivio
        .merge(
            right= perfil, 
            how='left', 
            left_on= 'ASO_IDENTIFICACION', 
            right_on= 'strIdentificacion'
        )
        .drop(
            columns='strIdentificacion'
        )
        .assign(
            strAgrupacionPerfil = lambda df: df['strAgrupacionPerfil'].fillna(
                'Operativo' ## -- Imputa con Operativo
            )
        )
    )

    return alivio

def final_matrix(alivio:pd.DataFrame, 
                 col_order:list) -> tuple:
    
    """
    Aplica el preprocesamiento final y construye la matriz de features lista
    para ser escalada y pasada al modelo.

    Pasos aplicados en orden:
        1. Convierte 'saldo_aportes' de string con coma decimal a entero.
        2. Elimina registros con cualquier valor nulo.
        3. Aplica One-Hot Encoding a 'strAgrupacionPerfil' sobre una copia
        sin ASO_IDENTIFICACION (sin drop_first, dtype int).
        4. Valida que todas las columnas de `col_order` estén presentes
        en la matriz resultante (garantía de compatibilidad con el escalador).
        5. Retorna la matriz X y la base con identificadores para poder
        asociar las predicciones del modelo a la población original.

    Parameters
    ----------
    alivio : pd.DataFrame
        Base enriquecida con columnas demográficas, reactivaciones y perfil.
    col_order : list
        Orden de columnas que espera el escalador (StandardScaler o similar).
        Debe coincidir exactamente con el orden usado en el entrenamiento.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        - x_feature : Matriz X lista para escalar, con columnas en el orden
                    de `col_order`. No contiene ASO_IDENTIFICACION.
        - alivio    : Base original con ASO_IDENTIFICACION intacto, para
                    unir las etiquetas predichas a la población.

    Raises
    ------
    KeyError
        Si alguna columna de `col_order` no está presente en la matriz tras
        el One-Hot Encoding. Indica incompatibilidad con el artefacto escalador.
    """
# --- Se cambia el tipo de dato de aportes --- #
    
    alivio['saldo_aportes'] = (
        alivio['saldo_aportes']
        .round(0)
        .astype('Int64')
    )
    
    # --- Si una columna tiene nulos, eliminar el registro del df --- #
    
    alivio.dropna(
        axis= 0, 
        ignore_index=True, 
        inplace=True
    )
    
    # --- One Hot Variable Perfil Vinculación --- #
    
    x_feature = (
    pd.get_dummies(
        alivio.drop(columns='ASO_IDENTIFICACION'),
        columns=['strAgrupacionPerfil'], 
        drop_first=False,
        dtype=int
    )
    )

    # --- Orden final a las columnas resultantes --- #
    
    ## --- Validar si hay columnas faltantes --- ##
    
    col_faltantes = [c for c in col_order if c not in x_feature.columns]
    
    if col_faltantes:
        raise KeyError(
            f'Faltan columnas requeridas por el escalador'
            f'\nFaltantes: {col_faltantes}'
        )
    
    return x_feature[col_order], alivio