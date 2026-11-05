import logging
import azure.functions as func
from main import main as run_pipeline

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