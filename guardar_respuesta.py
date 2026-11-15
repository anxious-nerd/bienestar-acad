"""Guardar en Google Sheets las respuestas que se llenan en la app de Streamlit (la encuesta).

Uso dentro de la encuesta de Streamlit, después de calcular las 10 variables:

    from guardar_respuesta import guardar_respuesta
    guardar_respuesta(x, cursos=["Física"], R1=1, R2=2.3, R3=3, carrera="Ingeniería Empresarial", ciclo="7.º–8.º",
                      apoyo=["Tutoría académica"], atencion=4)

x es un dict con: notas, asistencia, horas, entendimiento, interes, metodo, participacion,
amonestaciones, sueno, emocion (las mismas unidades que usa el sistema difuso).
Las filas se agregan a la pestaña "respuestas_streamlit" del mismo Google Sheet del formulario,
y el dashboard las lee junto con las del Google Form.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
import streamlit as st

from datos import HOJA_STREAMLIT, VARS

COLUMNAS = ["marca_temporal", *VARS, "R1", "R2", "R3", "cursos", "carrera", "ciclo", "apoyo", "atencion"]


@st.cache_resource
def _hoja():
    gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
    sh = gc.open_by_key(st.secrets["SHEET_ID"])
    try:
        ws = sh.worksheet(HOJA_STREAMLIT)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(HOJA_STREAMLIT, rows=1000, cols=len(COLUMNAS))
    if ws.row_values(1) != COLUMNAS:
        ws.update([COLUMNAS], "A1")  # escribe o actualiza los encabezados
    return ws


def guardar_respuesta(x, cursos=(), R1="", R2="", R3="", carrera="", ciclo="", apoyo=(), atencion=4):
    fila = [datetime.now(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M:%S"),
            *[round(float(x[v]), 4) for v in VARS], R1, R2, R3, ", ".join(cursos), carrera, ciclo, ", ".join(apoyo), atencion]
    _hoja().append_row(fila, value_input_option="USER_ENTERED")
