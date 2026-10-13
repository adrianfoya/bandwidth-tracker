import argparse
import csv
import logging
import math
from datetime import datetime, timezone
from pathlib import Path


CSV_COLUMNS = (
    "timestamp_utc",
    "source",
    "download_mbps",
    "upload_mbps",
    "status",
    "error",
)


def append_result(csv_path, row):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with csv_path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description="Mide descarga y subida con fastdotcom2 y agrega el resultado a un CSV."
    )
    parser.add_argument("--csv", type=Path, default=Path("measurements.csv"))
    parser.add_argument(
        "--max-time",
        type=int,
        default=10,
        help="Tiempo máximo de medición pasado a fastdotcom2, en segundos",
    )
    args = parser.parse_args()

    if args.max_time <= 0:
        parser.error("max-time debe ser mayor que cero")

    download_mbps = ""
    upload_mbps = ""
    error_message = ""

    try:
        import fastdotcom2

        result = fastdotcom2.fast_com2(verbose=False, max_time=args.max_time)
        download = float(result["download_speed"])
        upload = float(result["upload_speed"])
        if not math.isfinite(download) or not math.isfinite(upload):
            raise ValueError("fastdotcom2 devolvió velocidades no válidas")
        download_mbps = f"{download:.2f}"
        upload_mbps = f"{upload:.2f}"
        logging.info("Descarga: %s Mbps", download_mbps)
        logging.info("Subida: %s Mbps", upload_mbps)
    except ImportError as error:
        error_message = (
            "No se encontró fastdotcom2. Instálalo con: "
            "python3 -m pip install fastdotcom2"
        )
        logging.error("%s (%s)", error_message, error)
    except Exception as error:
        error_message = f"{type(error).__name__}: {error}"
        logging.exception("Falló la medición con fastdotcom2")

    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Fast.com",
        "download_mbps": download_mbps,
        "upload_mbps": upload_mbps,
        "status": "error" if error_message else "success",
        "error": error_message,
    }

    try:
        append_result(args.csv, row)
    except OSError as error:
        logging.error("No se pudo guardar el CSV %s: %s", args.csv, error)
        return 1

    print(f"Descarga: {download_mbps or 'fallida'} Mbps")
    print(f"Subida: {upload_mbps or 'fallida'} Mbps")
    print(f"CSV: {args.csv}")
    return 1 if error_message else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
