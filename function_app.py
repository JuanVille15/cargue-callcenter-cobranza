import json
import logging
import azure.functions as func
from main import main as run_pipeline
from src.utils.helpers import load_config
from src.pipelines import Comunes, Moras

app = func.FunctionApp()

@app.timer_trigger(schedule="0 0 11 * * *", arg_name="timer", use_monitor=False)
def alivio_diario(timer: func.TimerRequest) -> None:
    logging.info("Inicio pipeline alivio")
    try:
        run_pipeline()
    except SystemExit as e:
        if e.code not in (0, None):
            raise RuntimeError(f"Pipeline termino con codigo {e.code}") from e
    logging.info("Fin pipeline alivio")
    
@app.route(route="probar_moras", auth_level=func.AuthLevel.FUNCTION)
def probar_moras(req: func.HttpRequest) -> func.HttpResponse:
    """Corre comunes + exclusiones + Moras para ?fecha=YYYY-MM-DD. Solo para pruebas."""
    
    fecha = req.params.get("fecha")
    if not fecha:
        return func.HttpResponse("Falta el parámetro ?fecha=YYYY-MM-DD", status_code=400)
    
    cfg = load_config()
    comunes = Comunes.run_comunes(cfg=cfg, fecha=fecha)
    oferta = Moras.run_moras(cfg=cfg, common_files=comunes, fecha=fecha)
    
    return func.HttpResponse(
        json.dumps({"fecha":fecha, "oferta_moras": len(oferta["Moras"])}),
        mimetype="application/json",
        status_code=200
    )    
