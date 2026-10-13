import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
MEASUREMENT_SCRIPTS = ("librespeed_measure.py", "fastdotcom2_measure.py")


def run_cycle(csv_path):
    for script_name in MEASUREMENT_SCRIPTS:
        command = [
            sys.executable,
            str(PROJECT_DIR / script_name),
            "--csv",
            str(csv_path),
        ]
        logging.info("Iniciando medición: %s", script_name)
        try:
            result = subprocess.run(command, check=False)
        except OSError:
            logging.exception("No se pudo ejecutar %s", script_name)
            continue

        if result.returncode:
            logging.warning("%s terminó con código %s", script_name, result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="Ejecuta periódicamente las mediciones LibreSpeed y Fast.com."
    )
    parser.add_argument(
        "--interval-minutes",
        type=float,
        default=5,
        help="Intervalo entre inicios de ciclos, en minutos (por defecto: 2)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=PROJECT_DIR / "measurements.csv",
        help="Ruta del CSV de mediciones",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Ejecuta un ciclo y termina",
    )
    args = parser.parse_args()

    if args.interval_minutes <= 0:
        parser.error("interval-minutes debe ser mayor que cero")

    interval_seconds = args.interval_minutes * 60
    logging.info("Intervalo entre ciclos: %s minutos", args.interval_minutes)

    try:
        while True:
            cycle_started = time.monotonic()
            run_cycle(args.csv.resolve())
            if args.once:
                break

            remaining = interval_seconds - (time.monotonic() - cycle_started)
            if remaining > 0:
                time.sleep(remaining)
    except KeyboardInterrupt:
        logging.info("Programador detenido")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()