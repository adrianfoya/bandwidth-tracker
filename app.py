from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pandas as pd
import altair as alt
import streamlit as st
from dateutil.tz import tzlocal


CSV_PATH = Path(__file__).with_name("measurements.csv")
SOURCES = ["LibreSpeed", "Fast.com"]
SOURCE_LABELS = {
    "LibreSpeed": "Etecsa (LibreSpeed)",
    "Fast.com": "Fast.com (fastdotcom2)",
}
SOURCE_COLORS = {
    "Etecsa (LibreSpeed)": "#2563EB",
    "Fast.com (fastdotcom2)": "#F28B82",
}
PERIODS = [
    "Últimas 24 horas",
    "Última semana",
    "Último mes",
    "Intervalo personalizado",
]


st.set_page_config(page_title="Monitor de ancho de banda", page_icon="📶", layout="wide")


def load_measurements(csv_path):
    measurements = pd.read_csv(csv_path)
    required_columns = {
        "timestamp_utc",
        "source",
        "download_mbps",
        "upload_mbps",
    }
    missing_columns = required_columns.difference(measurements.columns)
    if missing_columns:
        raise ValueError(f"Faltan columnas requeridas en el CSV: {', '.join(sorted(missing_columns))}")

    measurements["timestamp_utc"] = pd.to_datetime(
        measurements["timestamp_utc"], utc=True, errors="coerce"
    )
    for column in ("download_mbps", "upload_mbps"):
        measurements[column] = pd.to_numeric(measurements[column], errors="coerce")

    return measurements.dropna(subset=["timestamp_utc"])


def selected_interval(period):
    now = datetime.now(timezone.utc)
    if period == "Últimas 24 horas":
        return now - timedelta(hours=24), now
    if period == "Última semana":
        return now - timedelta(days=7), now
    if period == "Último mes":
        month_start = pd.Timestamp(now) - pd.DateOffset(months=1)
        return month_start.to_pydatetime(), now

    local_now = datetime.now().astimezone()
    default_start = local_now - timedelta(days=7)
    start_column, end_column = st.columns(2)
    with start_column:
        start_date = st.date_input("Desde", value=default_start.date())
        start_time = st.time_input("Hora de inicio", value=default_start.time().replace(tzinfo=None))
    with end_column:
        end_date = st.date_input("Hasta", value=local_now.date())
        end_time = st.time_input("Hora de fin", value=local_now.time().replace(tzinfo=None))

    start = datetime.combine(start_date, start_time).astimezone(timezone.utc)
    end = datetime.combine(end_date, end_time).astimezone(timezone.utc)
    return start, end


st.title("Monitor de ancho de banda")
st.caption("Comparación histórica de LibreSpeed (Etecsa) y Fast.com. Velocidades en Mbps.")

period = st.radio("Período", PERIODS, horizontal=True, index=2)


@st.fragment(run_every="10s")
def render_dashboard(selected_period):
    start, end = selected_interval(selected_period)

    if start > end:
        st.error("El inicio del intervalo debe ser anterior al final.")
        return

    try:
        data = load_measurements(CSV_PATH)
    except FileNotFoundError:
        st.error(f"No se encontró el archivo de datos: {CSV_PATH.name}")
        return
    except (pd.errors.ParserError, ValueError) as error:
        st.error(f"No se pudo leer el CSV: {error}")
        return

    data = data[
        data["source"].isin(SOURCES)
        & data["timestamp_utc"].between(
            pd.Timestamp(start), pd.Timestamp(end), inclusive="both"
        )
    ].copy()

    st.caption(
        f"Intervalo: {start.astimezone().strftime('%Y-%m-%d %H:%M')} – "
        f"{end.astimezone().strftime('%Y-%m-%d %H:%M')} (hora local)"
    )

    def show_speed_chart(title, column):
        chart_data = data.dropna(subset=[column]).sort_values("timestamp_utc").copy()
        if end - start > timedelta(hours=24):
            chart_data["day"] = chart_data["timestamp_utc"].dt.tz_convert(tzlocal()).dt.date
            chart_data = chart_data.groupby(["source", "day"], as_index=False)[column].mean()
            chart_data["timestamp_utc"] = chart_data["day"].map(
                lambda day: datetime.combine(day, time.min).astimezone(timezone.utc)
            )

        chart_data["source_label"] = chart_data["source"].map(SOURCE_LABELS)
        chart_data["source_label"] = pd.Categorical(
            chart_data["source_label"],
            categories=[SOURCE_LABELS[source] for source in SOURCES],
            ordered=True,
        )

        st.subheader(title)
        if chart_data.empty:
            st.info("No hay mediciones disponibles para este intervalo.")
            return

        chart = (
            alt.Chart(chart_data)
            .mark_line(point=True)
            .encode(
                x=alt.X("timestamp_utc:T", title="Tiempo"),
                y=alt.Y(f"{column}:Q", title="Velocidad (Mbps)"),
                color=alt.Color(
                    "source_label:N",
                    title="Fuente",
                    scale=alt.Scale(
                        domain=list(SOURCE_COLORS),
                        range=list(SOURCE_COLORS.values()),
                    ),
                ),
                tooltip=[
                    alt.Tooltip("timestamp_utc:T", title="Tiempo", format="%Y-%m-%d %H:%M"),
                    alt.Tooltip("source_label:N", title="Fuente"),
                    alt.Tooltip(f"{column}:Q", title=title),
                ],
            )
            .properties(height=340)
        )
        st.altair_chart(chart, width="stretch")

    show_speed_chart("Descarga", "download_mbps")
    show_speed_chart("Subida", "upload_mbps")


render_dashboard(period)