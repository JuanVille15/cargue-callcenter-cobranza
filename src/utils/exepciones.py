class GCCconexionError(Exception):
    "No se pudo establecer conexión con GCC"
    pass

class GCCdesactualizadoError(Exception):
    "GCC no esta actualizado"
    pass

class ExportacionAlivioMTError(Exception):
    "Error a la hora de exportar Alivio MT"
    pass

class ExportacionAlivioInacError(Exception):
    "Error a la hora de exportar Alivio Inactivos"
    pass

class BodegaBiconexionError(Exception):
    "No se pudo establecer conexión con Bodega"
    pass

class ErrorConsultadoDemografica(Exception):
    "Ocurrió un error consultado vista demografica"
    pass

class ErrorConsultadoPerfil(Exception):
    "Ocurrio un error extrayendo perfil de vinculación"
    pass

class ErrorConsultadoVista360(Exception):
    "Ocurrio un error extrayendo la vista 360"
    pass

class EmptyDataFrameError(Exception):
    "El DataFrame no tiene registros"
    pass

class ErrorCargandoArterfacto(Exception):
    "Ocurrio un error cargando los .pkl"
    pass

class ErrorExportando(Exception):
    "Ocurrio un error intentando exportar un archivo"
    pass

class ColNecesariasError(Exception):
    "Faltan columnas necesarias en el DataFrame"
    pass

class AliviosCruzadosError(Exception):
    "Se han cruzado alivio Inactivos y Moras"
    pass

class ErrorEnvioOferta(Exception):
    "Ocurrio un error enviando la oferta a Wolkvox"
    pass

class ErrorNotificacion(Exception):
    "Ocurrio un error enviando la notificacion por correo"
    pass

class CatalogoInvalidoError(Exception):
    "Ocurrio un error con el catalogo de fuente"
    pass

class InsumoNoEncontradoError(Exception):
    "No se encuentra un insumo solicitado"
    pass

class InsumosIncompletosError(Exception):
    "El insumo no tiene todos los campos"
    pass
