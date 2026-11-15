"""Lectura de respuestas y conversión a las 10 variables del sistema difuso.

Fuentes, en este orden de prioridad (se configuran en .streamlit/secrets.toml):
  1. Google Sheets privado con cuenta de servicio:  SHEET_ID + [gcp_service_account]
  2. Google Sheets publicado como CSV:               FORM_CSV_URL (y opcional STREAMLIT_CSV_URL)
  3. Un Excel local o subido desde la barra lateral (respaldo para pruebas)

Hoja 1 = respuestas del Google Form (encabezados tal como los crea Forms).
Hoja "respuestas_streamlit" (opcional) = respuestas de la app de Streamlit, ya en las
10 variables (ver guardar_respuesta.py).
"""
import math
import re
import unicodedata

import numpy as np
import pandas as pd

VARS = ["notas", "asistencia", "horas", "entendimiento", "interes", "metodo",
        "participacion", "amonestaciones", "sueno", "emocion"]
HOJA_STREAMLIT = "respuestas_streamlit"


# ---------- conversión de una celda a número ----------
def num(v):
    """Número, '14.5', '14,5', '4 o menos' → 4, '5 o más' → 5, 'Ninguno' → 0; vacío → NaN."""
    if v is None:
        return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    t = str(v).strip().lower()
    if t == "" or t == "nan":
        return np.nan
    if t.startswith("ninguno"):
        return 0.0
    m = re.search(r"\d+([.,]\d+)?", t)
    return float(m.group().replace(",", ".")) if m else np.nan


def es_si(v):
    return isinstance(v, str) and v.strip().upper().startswith("S")


def _sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").lower()


def normalizar_carrera(v):
    if not isinstance(v, str) or not v.strip():
        return "Sin dato"
    t = " ".join(v.split())
    n = _sin_tildes(t)
    if "empresarial" in n:
        return "Ingeniería Empresarial"
    if "informacion" in n or "ing info" in n:
        return "Ingeniería de la Información"
    return t[:1].upper() + t[1:].lower()


# ---------- formulario de Google ----------
def procesar_formulario(df):
    """df: hoja de respuestas del Google Form. Devuelve una lista de personas."""
    H = [str(h) for h in df.columns]
    Hn = [_sin_tildes(h) for h in H]

    def col(*partes):
        partes = [_sin_tildes(p) for p in partes]
        for i, h in enumerate(Hn):
            if all(p in h for p in partes):
                return H[i]
        return None

    cursos = []
    for h in H:
        m = re.match(r"^¿Llevas o llevaste (.+)\?$", h.strip())
        if m:
            cursos.append(m.group(1))

    c = {k: col(*p) for k, p in {
        "marca": ("marca temporal",), "acepta": ("aceptas",), "matric": ("matriculado",),
        "atencion": ("marca la opcion 4",), "metodo": ("metodo o plan",), "amon": ("amonestaciones",),
        "sueno": ("horas duermes",), "E1": ("agobiado",), "E2": ("tranquilo",), "E3": ("con energia",),
        "R1": ("desaprobaste",), "R2a": ("dejar la universidad",), "R2b": ("cambiarme de carrera",),
        "R2c": ("pueda terminar",), "apoyo": ("tipo de apoyo",), "ciclo": ("ciclo de tu carrera",),
        "carrera": ("carrera",)}.items()}
    # "carrera" también aparece en otras preguntas: tomar la columna cuyo encabezado es exactamente "Carrera"
    c["carrera"] = next((h for h in H if h.strip().lower() == "carrera"), None)

    personas = []
    for fila, (_, r) in enumerate(df.iterrows(), start=1):
        g = lambda k: r[c[k]] if c.get(k) else None
        p = {"id": f"P{fila}", "fila": fila, "origen": "Formulario", "marca": g("marca"),
             "carrera": normalizar_carrera(g("carrera")), "ciclo": g("ciclo") if isinstance(g("ciclo"), str) else "Sin dato",
             "apoyo": [a.strip() for a in str(g("apoyo")).split(",")] if isinstance(g("apoyo"), str) else [],
             "valida": True, "motivo": "", "cursos": []}
        if not es_si(g("acepta")):
            p.update(valida=False, motivo="No aceptó participar")
        elif not es_si(g("matric")):
            p.update(valida=False, motivo="No está matriculado/a")
        elif num(g("atencion")) != 4:
            p.update(valida=False, motivo="Falló la pregunta de atención")

        crudo = {"Método (Sí/No)": g("metodo"), "Amonestaciones": g("amon"), "Sueño (h)": g("sueno"),
                 "E1 agobiado": g("E1"), "E2 tranquilo": g("E2"), "E3 con energía": g("E3")}
        E1, E2, E3 = num(g("E1")), num(g("E2")), num(g("E3"))
        x = {"metodo": 1.0 if es_si(g("metodo")) else 0.0,
             "amonestaciones": min(num(g("amon")), 5),
             "sueno": min(num(g("sueno")), 13),
             "emocion": float(np.mean([6 - E1, E2, E3]))}

        por_curso = []
        for cu in cursos:
            if not es_si(r[col("llevas o llevaste " + cu)]):
                continue
            q = lambda t: num(r[col("[" + cu + "]", t)]) if col("[" + cu + "]", t) else np.nan
            rec = {"notas": q("nota"), "asistencia": q("porcentaje"), "horas": q("horas dedicas"),
                   "C1": q("entiendo (o entendia) los contenidos"), "C2": q("no entiendo"),
                   "C3": q("interesantes"), "C4": q("solo por cumplir"),
                   "participacion": q("participas"), "R3": q("en riesgo")}
            rec["entendimiento"] = np.mean([rec["C1"], 6 - rec["C2"]])
            rec["interes"] = np.mean([rec["C3"], 6 - rec["C4"]])
            por_curso.append((cu, rec))
            for k, v in rec.items():
                crudo[f"[{cu}] {k}"] = v
        p["cursos"] = [cu for cu, _ in por_curso]
        if not por_curso and p["valida"]:
            p.update(valida=False, motivo="No marcó ningún curso")
        for k in ("notas", "asistencia", "horas", "entendimiento", "interes", "participacion"):
            x[k] = float(np.mean([rec[k] for _, rec in por_curso])) if por_curso else np.nan
        x["notas"] = min(max(x["notas"], 0), 20) if not math.isnan(x["notas"]) else np.nan
        x["asistencia"] = min(max(x["asistencia"], 0), 100) if not math.isnan(x["asistencia"]) else np.nan
        x["horas"] = min(x["horas"], 10) if not math.isnan(x["horas"]) else np.nan

        p["x"], p["crudo"] = x, crudo
        p["R1"] = num(g("R1"))
        r2 = [v for v in (num(g("R2a")), num(g("R2b")), num(g("R2c"))) if not math.isnan(v)]
        p["R2"] = float(np.mean(r2)) if r2 else np.nan
        p["R3"] = float(np.mean([rec["R3"] for _, rec in por_curso])) if por_curso else np.nan
        if p["valida"] and any(math.isnan(x[v]) for v in VARS):
            p.update(valida=False, motivo="Respuestas incompletas")
        personas.append(p)
    return personas


# ---------- respuestas guardadas por la app de Streamlit ----------
def procesar_streamlit(df):
    personas = []
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        x = {v: num(r.get(v)) for v in VARS}
        p = {"id": f"S{i}", "fila": i, "origen": "Streamlit", "marca": r.get("marca_temporal"),
             "carrera": normalizar_carrera(r.get("carrera")), "ciclo": r.get("ciclo") if isinstance(r.get("ciclo"), str) and r.get("ciclo") else "Sin dato",
             "apoyo": [a.strip() for a in str(r.get("apoyo", "")).split(",") if a.strip() and a.strip() != "nan"],
             "cursos": [s.strip() for s in str(r.get("cursos", "")).split(",") if s.strip() and s.strip() != "nan"],
             "x": x, "crudo": {v: r.get(v) for v in VARS},
             "R1": num(r.get("R1")), "R2": num(r.get("R2")), "R3": num(r.get("R3")),
             "valida": not any(math.isnan(x[v]) for v in VARS), "motivo": ""}
        if not p["valida"]:
            p["motivo"] = "Respuestas incompletas"
        at = num(r.get("atencion"))
        if not math.isnan(at) and at != 4:
            p.update(valida=False, motivo="Falló la pregunta de atención")
        personas.append(p)
    return personas


# ---------- fuentes ----------
def _df_de_valores(valores):
    if not valores:
        return pd.DataFrame()
    return pd.DataFrame(valores[1:], columns=valores[0])


def leer_fuentes(secrets, archivo_subido=None, excel_local=None):
    """Devuelve (df_formulario, df_streamlit, descripción de la fuente)."""
    if "SHEET_ID" in secrets and "gcp_service_account" in secrets:
        import gspread
        gc = gspread.service_account_from_dict(dict(secrets["gcp_service_account"]))
        sh = gc.open_by_key(secrets["SHEET_ID"])
        df_f = _df_de_valores(sh.get_worksheet(0).get_all_values())
        try:
            df_s = _df_de_valores(sh.worksheet(HOJA_STREAMLIT).get_all_values())
        except gspread.WorksheetNotFound:
            df_s = pd.DataFrame()
        return df_f, df_s, "Google Sheets (cuenta de servicio)"
    if "FORM_CSV_URL" in secrets:
        df_f = pd.read_csv(secrets["FORM_CSV_URL"], dtype=str)
        df_s = pd.read_csv(secrets["STREAMLIT_CSV_URL"], dtype=str) if secrets.get("STREAMLIT_CSV_URL") else pd.DataFrame()
        return df_f, df_s, "Google Sheets (CSV publicado)"
    fuente = archivo_subido or excel_local
    if fuente is not None:
        xl = pd.ExcelFile(fuente)
        df_f = xl.parse(xl.sheet_names[0])
        df_s = xl.parse(HOJA_STREAMLIT, dtype=str) if HOJA_STREAMLIT in xl.sheet_names else pd.DataFrame()
        return df_f, df_s, "Archivo Excel"
    return pd.DataFrame(), pd.DataFrame(), "Sin fuente configurada"


def cargar_personas(df_f, df_s):
    personas = procesar_formulario(df_f) if not df_f.empty else []
    if not df_s.empty:
        personas += procesar_streamlit(df_s)
    return personas
