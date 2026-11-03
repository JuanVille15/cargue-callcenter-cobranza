import datetime
from src.conexion.gcc import execute_query
from src.utils.exepciones import GCCdesactualizadoError

def val_gcc_actualizado(query_val_gcc:str):
    
    ultima_actualizacion = execute_query(query_val_gcc).iloc[0,0]
    
    if datetime.datetime.strptime(str(ultima_actualizacion), "%Y-%m-%d").date() == datetime.date.today():
        print("El DW GCC está actualizado al día de hoy")
        print("Se da inicio al proceso")
    else:
        print(f"Fecha última actializacion GCC: {ultima_actualizacion}")
        raise GCCdesactualizadoError("El DW GCC no está actualizado al dia de hoy.")