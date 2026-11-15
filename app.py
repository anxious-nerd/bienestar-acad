"""Encuesta de bienestar integral para estudiantes.

Las mismas preguntas del Google Form. Al enviar, el estudiante ve su resultado y sus
recomendaciones, y la respuesta se guarda en el Google Sheet que lee el dashboard.
Las transformaciones (ítems invertidos, promedio de cursos, filtros) son las mismas que usa
el dashboard: se hace pasando la respuesta por datos.procesar_formulario.
"""
import math

import pandas as pd
import streamlit as st

import datos
import fuzzy_engine as fe

st.set_page_config(page_title="Encuesta de bienestar integral", page_icon="🌱", layout="centered")

CURSOS = ["Física", "Analítica de la Web", "Estrategia"]
LLEVA = ["No", "Sí, ya lo llevé", "Sí, lo estoy llevando este ciclo"]
LIK = [1, 2, 3, 4, 5]
ACUERDO = "1 = Totalmente en desacuerdo · 5 = Totalmente de acuerdo"
FRECUENCIA = "1 = Nunca · 5 = Siempre"
RIESGO = "1 = Nada en riesgo · 5 = Muy en riesgo"
SUENO = ["4 o menos", "5", "6", "7", "8", "9", "10 o más"]
AMON = ["Ninguno", "1", "2", "3", "4", "5 o más"]
APOYO = ["Tutoría académica", "Técnicas y hábitos de estudio", "Bienestar o apoyo emocional",
         "Apoyo para organizar mi tiempo", "Ninguno por ahora"]
CICLOS = ["1.º–2.º", "3.º–4.º", "5.º–6.º", "7.º–8.º", "9.º o más"]
COL = {"bajo": "#B9382A", "medio": "#B7740F", "alto": "#2B7A49"}

# Encabezados exactos del Google Form: así la respuesta se procesa igual que en el dashboard
H = {
    "acepta": "¿Aceptas participar en esta encuesta?",
    "matric": "¿Estás actualmente matriculado/a en una carrera de pregrado?",
    "metodo": "¿Tienes un método o plan de estudio definido (horario, resúmenes, repasos planificados)?",
    "amon": "En este ciclo, ¿cuántas amonestaciones o sanciones formales te ha impuesto la universidad? ",
    "sueno": "En días de clase, ¿cuántas horas duermes por noche en promedio?",
    "E1": "En las últimas 2 semanas me sentí agobiado/a por mis responsabilidades académicas.",
    "E2": "En las últimas 2 semanas me sentí tranquilo/a y con ánimo para estudiar.",
    "aten": "Para verificar tu atención en esta pregunta, marca la opción 4.",
    "E3": "En las últimas 2 semanas me sentí con energía para cumplir mis actividades.",
    "R1": "En tus últimos 2 ciclos, ¿en cuántos cursos desaprobaste o te retiraste?",
    "R2a": "He pensado en dejar la universidad.",
    "R2b": "He pensado en cambiarme de carrera.",
    "R2c": "Dudo de que pueda terminar mi carrera.",
    "apoyo": "¿Qué tipo de apoyo te ayudaría más ahora? (marca todas las que apliquen)",
    "ciclo": "¿En qué ciclo de tu carrera estás?",
    "carrera": "Carrera",
}
PC = {  # preguntas por curso: clave → (texto, tipo, ayuda)
    "nota": ("¿Cuál es tu nota en el curso? (0 a 20)", "num20", None),
    "asis": ("¿A qué porcentaje de las clases asististe? (0 a 100)", "num100", None),
    "horas": ("En una semana típica, ¿cuántas horas dedicas (o dedicabas) a estudiar el curso fuera de clase? (0 a 10)", "num10", None),
    "C1": ("Entiendo (o entendía) los contenidos cuando se explican en clase.", "lik", ACUERDO),
    "C2": ("Con frecuencia siento (o sentía) que no entiendo lo que se enseña.", "lik", ACUERDO),
    "C3": ("Los temas del curso me resultan (o resultaron) interesantes.", "lik", ACUERDO),
    "C4": ("Voy (o iba) a clases solo por cumplir, sin interés real.", "lik", ACUERDO),
    "part": ("¿Con qué frecuencia participas (o participabas) en clase: preguntas, comentarios, trabajos en grupo?", "lik", FRECUENCIA),
    "R3": ("¿Qué tan en riesgo sientes (o sentiste) tu desempeño en el curso?", "lik", RIESGO),
}


def likert(texto, key, ayuda=ACUERDO):
    return st.radio(f"{texto}  \n:gray[{ayuda}]", LIK, index=None, horizontal=True, key=key)


def numero(texto, key, maximo, paso):
    return st.number_input(texto, min_value=0.0, max_value=float(maximo), value=None, step=paso, key=key, placeholder="Escribe un número")


def reiniciar():
    for k in list(st.session_state.keys()):
        del st.session_state[k]


st.title("¿Cómo vas este ciclo?")
st.caption("Encuesta anónima · Desfuzzycando el Aprendizaje · Inteligencia Computacional, Universidad del Pacífico")
st.write("Responde sobre tus cursos y sobre ti. Al final verás tu **bienestar integral estimado** (de 5 a 95) "
         "y recomendaciones según tus respuestas. Toma unos 5 minutos.")

# ---------------- resultado (si ya envió) ----------------
if st.session_state.get("resultado"):
    R = st.session_state["resultado"]
    v = R["valor"]
    nv = fe.nivel(v["I"])
    st.divider()
    st.subheader("Tu resultado")
    st.markdown(f"<div style='font-size:3.6rem;font-weight:700;line-height:1;color:{COL[nv]}'>{v['I']:.1f}"
                f"<span style='font-size:1.2rem;color:gray'> / 95</span></div>"
                f"<div style='font-size:1.2rem;font-weight:600;color:{COL[nv]};margin:.3rem 0 1rem'>Bienestar {nv}</div>",
                unsafe_allow_html=True)
    st.write({"bajo": "Varias áreas necesitan atención. Las recomendaciones de abajo son un buen punto de partida.",
              "medio": "Vas razonablemente, con algunas áreas por reforzar.",
              "alto": "Vas bien en general. Mantén lo que te está funcionando."}[nv])
    cols = st.columns(3)
    for c, b, pista in zip(cols, ("A", "C", "Co"), ("notas, asistencia, horas", "entendimiento, interés, método",
                                                     "sueño, ánimo, participación")):
        c.metric(fe.NOMBRE_BLOQUE[b], f"{v[b]:.0f}", fe.nivel(v[b]), delta_color="off")
        c.progress(min(max(v[b] / 100, 0.0), 1.0))
        c.caption(pista)
    st.subheader("Recomendaciones")
    recs = [r for r in st.session_state["recs"] if not r["interna"]]
    for r in recs:
        st.info(f"{r['msg']}  \n*{r['src']}*")
    if not recs:
        st.info("No hay una señal puntual que corregir. Revisa la dimensión más baja para ver dónde reforzar.")
    st.caption("Estimación con un sistema difuso jerárquico a partir de tus respuestas. Orienta; no es un diagnóstico. "
               "Si algo de lo que sientes te preocupa, Bienestar Estudiantil puede ayudarte.")
    if st.session_state.get("aviso_guardado"):
        st.caption(st.session_state["aviso_guardado"])
    st.button("Responder de nuevo", on_click=reiniciar)
    st.stop()

# ---------------- encuesta ----------------
st.divider()
acepta = st.radio(H["acepta"], ["Sí", "No"], index=None, key="acepta")
if acepta == "No":
    st.info("Gracias por tu tiempo. No se guardará ninguna respuesta.")
    st.stop()
matric = st.radio(H["matric"], ["Sí", "No"], index=None, key="matric")
if matric == "No":
    st.info("Esta encuesta es para estudiantes de pregrado. ¡Gracias!")
    st.stop()
if acepta is None or matric is None:
    st.stop()

st.header("Sobre ti")
resp = {}
resp["metodo"] = st.radio(H["metodo"], ["Sí", "No"], index=None, horizontal=True, key="metodo")
resp["amon"] = st.radio(H["amon"].strip(), AMON, index=None, horizontal=True, key="amon")
resp["sueno"] = st.radio(H["sueno"], SUENO, index=None, horizontal=True, key="sueno")
resp["E1"] = likert(H["E1"], "E1")
resp["E2"] = likert(H["E2"], "E2")
resp["aten"] = st.radio(H["aten"], LIK, index=None, horizontal=True, key="aten")
resp["E3"] = likert(H["E3"], "E3")

st.header("Tus cursos")
st.caption("Responde por cada curso que llevas o llevaste. Si son varios, se promedian.")
lleva, porcurso = {}, {}
for cu in CURSOS:
    with st.container(border=True):
        lleva[cu] = st.radio(f"¿Llevas o llevaste {cu}?", LLEVA, index=None, key=f"lleva_{cu}")
        if lleva[cu] and lleva[cu].startswith("S"):
            d = {}
            for k, (txt, tipo, ayuda) in PC.items():
                key = f"{cu}_{k}"
                if tipo == "num20":
                    d[k] = numero(txt, key, 20, 0.5)
                elif tipo == "num100":
                    d[k] = numero(txt, key, 100, 1.0)
                elif tipo == "num10":
                    d[k] = numero(txt, key, 10, 0.5)
                else:
                    d[k] = likert(txt, key, ayuda)
            porcurso[cu] = d

st.header("Tu situación académica")
resp["R1"] = st.number_input(H["R1"], min_value=0, max_value=20, value=None, step=1, key="R1", placeholder="Escribe un número")
resp["R2a"] = likert(H["R2a"], "R2a")
resp["R2b"] = likert(H["R2b"], "R2b")
resp["R2c"] = likert(H["R2c"], "R2c")
resp["apoyo"] = st.multiselect(H["apoyo"], APOYO, key="apoyo", placeholder="Elige una o varias")
resp["ciclo"] = st.selectbox(H["ciclo"], CICLOS, index=None, key="ciclo", placeholder="Elige tu ciclo")
resp["carrera"] = st.text_input(H["carrera"], key="carrera")

st.divider()
if st.button("Enviar y ver mi resultado", type="primary"):
    faltan = [k for k in ("metodo", "amon", "sueno", "E1", "E2", "aten", "E3", "R1", "R2a", "R2b", "R2c") if resp[k] is None]
    if not resp["apoyo"]:
        faltan.append("apoyo")
    if not resp["ciclo"]:
        faltan.append("ciclo")
    if not any(v and v.startswith("S") for v in lleva.values()):
        st.error("Marca al menos un curso que lleves o hayas llevado.")
        st.stop()
    faltan += [f"{cu}: {k}" for cu, d in porcurso.items() for k, val in d.items() if val is None]
    if faltan or any(v is None for v in lleva.values()):
        st.error("Te faltan algunas respuestas. Revisa las preguntas sin marcar y vuelve a enviar.")
        st.stop()

    # Fila con los encabezados del Form → mismo procesamiento que el dashboard
    fila = {H["acepta"]: acepta, H["matric"]: matric, H["metodo"]: resp["metodo"], H["amon"]: resp["amon"],
            H["sueno"]: resp["sueno"], H["E1"]: resp["E1"], H["E2"]: resp["E2"], H["aten"]: resp["aten"], H["E3"]: resp["E3"],
            H["R1"]: resp["R1"], H["R2a"]: resp["R2a"], H["R2b"]: resp["R2b"], H["R2c"]: resp["R2c"],
            H["apoyo"]: ", ".join(resp["apoyo"]), H["ciclo"]: resp["ciclo"], H["carrera"]: resp["carrera"]}
    for cu in CURSOS:
        fila[f"¿Llevas o llevaste {cu}?"] = lleva[cu]
        for k, (txt, _, _) in PC.items():
            fila[f"[{cu}] {txt}"] = porcurso.get(cu, {}).get(k)
    p = datos.procesar_formulario(pd.DataFrame([fila]))[0]
    if any(math.isnan(p["x"][v]) for v in datos.VARS):
        st.error("No se pudo calcular el resultado: revisa que todas las respuestas estén completas.")
        st.stop()
    res = fe.evaluar(p["x"])
    st.session_state["resultado"] = res
    st.session_state["recs"] = fe.recomendaciones(p["x"], res, para="estudiante")

    # Guardar en el Google Sheet (si está configurado)
    try:
        from guardar_respuesta import guardar_respuesta
        aux = lambda v: "" if v is None or (isinstance(v, float) and math.isnan(v)) else round(float(v), 4)
        guardar_respuesta(p["x"], cursos=p["cursos"], R1=aux(p["R1"]), R2=aux(p["R2"]), R3=aux(p["R3"]),
                          carrera=resp["carrera"], ciclo=resp["ciclo"], apoyo=resp["apoyo"], atencion=int(resp["aten"]))
        st.session_state["aviso_guardado"] = "Tu respuesta quedó registrada de forma anónima. ¡Gracias por participar!"
    except Exception as e:  # sin conexión configurada o error de Google: el estudiante igual ve su resultado
        st.session_state["aviso_guardado"] = ""
        print("No se pudo guardar la respuesta:", repr(e))
    st.rerun()
