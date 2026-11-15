# Encuesta de bienestar integral (app para estudiantes)

Las mismas preguntas del Google Form. Al enviar, el estudiante ve su bienestar integral (5 a 95), sus tres
dimensiones y recomendaciones. La respuesta se guarda en el Google Sheet, en la pestaña `respuestas_streamlit`,
y aparece en el dashboard interno.

Usa el mismo motor (`fuzzy_engine.py`, `fis_v10_spec.json`) y el mismo procesamiento (`datos.py`) que el
dashboard, así que el puntaje del estudiante y el del dashboard son idénticos.

## Archivos

| Archivo | Qué hace |
|---|---|
| `app.py` | La encuesta y la pantalla de resultado |
| `fuzzy_engine.py`, `fis_v10_spec.json` | Sistema difuso jerárquico v10 (71 reglas) |
| `datos.py` | Convierte las respuestas en las 10 variables, igual que con el Form |
| `guardar_respuesta.py` | Escribe la respuesta en el Google Sheet |
| `requirements.txt` | Librerías |

## Secrets (Streamlit Cloud → la app → Settings → Secrets)

Solo esto (sin la contraseña del dashboard):

```toml
SHEET_ID = "id-de-la-hoja"

[gcp_service_account]
# los mismos campos que en el secrets.toml del dashboard
```

La hoja debe estar compartida como **Editor** con el `client_email` de la cuenta de servicio.
Si no hay secrets, la app funciona igual (el estudiante ve su resultado) pero no guarda la respuesta.

## Probar en local

```bash
pip install -r requirements.txt
streamlit run app.py
```
