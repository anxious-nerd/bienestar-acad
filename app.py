# app.py
import streamlit as st
import pathlib

# Set page title
st.set_page_config(page_title="HTML Viewer", layout="wide")

# Path to your HTML file (relative to this script)
html_path = pathlib.Path("Encuesta de Bienestar Integral.html")

# Validate file existence
if not html_path.exists():
    st.error(f"HTML file '{html_path}' not found in repository.")
else:
    # Read HTML content
    try:
        html_content = html_path.read_text(encoding="utf-8")
        # Render HTML inside Streamlit
        st.components.v1.html(html_content, height=800, scrolling=True)
    except Exception as e:
        st.error(f"Error reading HTML file: {e}")
