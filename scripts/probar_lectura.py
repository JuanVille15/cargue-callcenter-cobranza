import logging
import psutil

from datetime import date
from dotenv import load_dotenv
from src.conexion.blob import catalogo, leer_fuente, validar_insumos

if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("azure").setLevel(logging.WARNING)
    fecha = date.today().strftime("%Y-%m-%d")
    
    validar_insumos(fecha)
    for fuente, spec in catalogo()["fuentes"].items():
        if spec.get("requerido", True):
            leer_fuente(fuente, fecha)
    print(f"Pico de memoria: {psutil.Process().memory_info().peak_wset / 1024**2:.0f} MB")