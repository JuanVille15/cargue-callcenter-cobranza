import sys
import logging
import psutil

from dotenv import load_dotenv

from src.utils.helpers import print_step, load_config
from src.extraccion.commons import extract_common_blob
from src.pipelines import Moras
from src.conexion.blob import guardar_salida, validar_insumos
from src.transformacion.alternativas import tabla_exclusiones, alternativas_vigentes


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("azure").setLevel(logging.WARNING)
    
    fecha, cfg = sys.argv[1], load_config()
    validar_insumos(fecha)
    print_step('[1/3] Extrayendo bases comunes')
    common_files = extract_common_blob(fecha=fecha, cfg=cfg)
    
    print_step('[2/3] Creando base de exclusiones')
    vigentes= alternativas_vigentes(common_files["hist_alternativas"], cfg["params"]["procesos_alternativas"])
    common_files["exclusiones"] = tabla_exclusiones(vigentes=vigentes, perseverados=common_files["perseverados"])
    guardar_salida(common_files["exclusiones"], "silver", "exclusiones", fecha)
    
    print_step('[3/3] Corriendo Pipeline Moras Trempanas')
    oferta = Moras.run_moras(cfg=cfg, common_files=common_files, fecha=fecha)
    print(f"Oferta Moras: {len(oferta['Moras'])} asociados")
    print(f"Pico de memoria: {psutil.Process().memory_info().peak_wset / 1024**2:.0f} MB")