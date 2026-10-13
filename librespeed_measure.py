import argparse
import csv
import logging
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SERVER_URL = "http://speedtest.cd.etecsa.cu/"
CSV_COLUMNS = (
    "timestamp_utc",
    "source",
    "download_mbps",
    "upload_mbps",
    "status",
    "error",
)
def measure_speed(server_url, timeout, browser_path):
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError(
            "No se encontró Playwright. Instálalo con: python -m pip install playwright"
        ) from error

    with sync_playwright() as playwright:
        try:
            launch_options = {"headless": True}
            if browser_path:
                launch_options["executable_path"] = browser_path
            browser = playwright.chromium.launch(**launch_options)
        except Exception as error:
            raise RuntimeError(
                "No se pudo iniciar Chromium. Instálalo con: "
                "python -m playwright install chromium"
            ) from error

        page = browser.new_page()
        page.goto(server_url, wait_until="domcontentloaded", timeout=timeout * 1000)
        start_button = page.locator("#startStopBtn")
        start_button.wait_for(state="visible", timeout=timeout * 1000)
        start_button.click()

        errors = []
        try:
            page.wait_for_function(
                "() => !document.querySelector('#startStopBtn')?.classList.contains('running')",
                timeout=timeout * 1000,
            )
        except PlaywrightTimeoutError:
            errors.append(f"La medición excedió el timeout de {timeout} segundos")

        def read_speed(selector):
            text = page.locator(selector).inner_text(timeout=5000).strip()
            try:
                speed = float(text)
            except ValueError:
                return None
            return speed if math.isfinite(speed) and speed >= 0 else None

        download = read_speed("#dlText")
        upload = read_speed("#ulText")
        if download is None or upload is None:
            errors.append("La página no mostró una velocidad válida de descarga o subida")
        browser.close()
        return download, upload, errors


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
        description="Mide descarga y subida en la página LibreSpeed con Playwright y guarda el resultado en CSV."
    )
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL)
    parser.add_argument("--csv", type=Path, default=Path("measurements.csv"))
    parser.add_argument(
        "--browser",
        default=shutil.which("chromium") or shutil.which("google-chrome"),
        help="Ruta a Chromium o Chrome (se detecta automáticamente si está instalado)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Tiempo máximo, en segundos, para cargar y completar la prueba",
    )
    args = parser.parse_args()

    if args.timeout <= 0:
        parser.error("timeout debe ser mayor que cero")

    results = {"download_mbps": "", "upload_mbps": ""}
    errors = []
    try:
        download, upload, errors = measure_speed(
            args.server_url.rstrip("/") + "/", args.timeout, args.browser
        )
        if download is not None:
            results["download_mbps"] = f"{download:.2f}"
            logging.info("Descarga: %s Mbps", results["download_mbps"])
        if upload is not None:
            results["upload_mbps"] = f"{upload:.2f}"
            logging.info("Subida: %s Mbps", results["upload_mbps"])
    except Exception as error:
        errors.append(str(error))
        logging.exception("Fallo en prueba LibreSpeed")

    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "LibreSpeed",
        **results,
        "status": "partial" if errors and any(results.values()) else "error" if errors else "success",
        "error": " | ".join(errors),
    }
    try:
        append_result(args.csv, row)
    except OSError as error:
        logging.error("No se pudo guardar el CSV %s: %s", args.csv, error)
        return 1

    print(f"Descarga: {row['download_mbps'] or 'fallida'} Mbps")
    print(f"Subida: {row['upload_mbps'] or 'fallida'} Mbps")
    print(f"CSV: {args.csv}")
    return 1 if errors else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())