import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta
import pytz
import json
import requests
from io import BytesIO
from fpdf import FPDF

# --- 1. CONFIGURACIÓN ---
ZONA_LOCAL = pytz.timezone('America/Mexico_City')
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="TUMULTOFLOW", layout="wide", page_icon="⚖️")

# --- 2. CLASE PARA GENERAR EL PDF CON IMÁGENES ---
class CatalogoPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'CATÁLOGO DE PRODUCTOS - DUO LEGAL', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, f'Generado el: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generar_pdf_con_fotos(productos):
    pdf = CatalogoPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    col_width = 60
    margin_x = 10
    curr_x = margin_x
    curr_y = 30
    items_per_row = 3
    
    for i, p in enumerate(productos):
        # Manejo de posición en cuadrícula
        col = i % items_per_row
        if i > 0 and col == 0:
            curr_y += 75  # Espacio vertical entre filas
            curr_x = margin_x
            
            # Si se acaba la página, resetear Y
            if curr_y > 220:
                pdf.add_page()
                curr_y = 30

        # Dibujar Imagen
        foto_url = p.get('foto_path')
        if foto_url and str(foto_url).startswith('http'):
            try:
                resp = requests.get(foto_url, timeout=5)
                if resp.status_code == 200:
                    img = BytesIO(resp.content)
                    pdf.image(img, x=curr_x + 5, y=curr_y, w=45, h=45)
            except:
                pdf.set_xy(curr_x, curr_y + 20)
                pdf.cell(55, 10, "[Error Imagen]", 0, 0, 'C')
        else:
            pdf.rect(curr_x + 10, curr_y + 10, 35, 25) # Cuadro vacío si no hay foto
            
        # Nombre y Precio debajo de la foto
        pdf.set_xy(curr_x, curr_y + 48)
        pdf.set_font('Arial', 'B', 9)
        pdf.multi_cell(55, 4, p['nombre'][:45], align='C')
        
        pdf.set_x(curr_x)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(46, 125, 50) # Verde
        pdf.cell(55, 8, f"${p['precio_pub']:,.2f}", ln=True, align='C')
        pdf.set_text_color(0,0,0)
        
        pdf.set_x(curr_x)
        pdf.set_font('Arial', '', 8)
        pdf.cell(55, 4, f"SKU: {p['codigo']}", ln=True, align='C')
        
        curr_x += col_width

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# --- 3. FUNCIONES DE APOYO ---
def obtener_config(tipo):
    try:
        res = supabase.table("configuracion").select("valor").eq("tipo", tipo).execute()
        return res.data if res.data else []
    except: return []

# --- 4. MANEJO DE SESIÓN Y LOGIN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []

if not st.session_state.auth:
    st.title("⚖️ Acceso Duo Legal")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if (u == "admin" and p == "admin1") or (u == "equipo" and p == "equipo1"):
            st.session_state.auth, st.session_state.role = True, u
            st.rerun()
    st.stop()

# --- 5. NAVEGACIÓN ---
with st.sidebar:
    st.title(f"Usuario: {st.session_state.role.upper()}")
    menu = st.radio("Menú", ["Ventas", "Inventario", "Reportes"] if st.session_state.role == "admin" else ["Ventas", "Inventario"])
    if st.button("Salir"):
        st.session_state.auth = False
        st.rerun()

# --- SECCIONES ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    # (Lógica simplificada de ventas para este ejemplo)
    st.write("Selecciona productos en Inventario para ver el catálogo.")

elif menu == "Inventario":
    st.header("📦 Inventario y Catálogo PDF")
    tabs = st.tabs(["📋 Lista", "🖨️ Generar PDF con Fotos"])
    
    with tabs[0]:
        res = supabase.table("productos").select("*").execute()
        if res.data:
            st.dataframe(pd.DataFrame(res.data)[["codigo", "nombre", "stock", "precio_pub"]])

    with tabs[1]:
        st.subheader("Configuración del Catálogo")
        st.info("Al presionar el botón, el sistema descargará las fotos de la base de datos y armará el archivo. Esto puede tardar unos segundos dependiendo de cuántos productos tengas.")
        
        res_cat = supabase.table("productos").select("codigo, nombre, precio_pub, foto_path").order("nombre").execute()
        
        if res_cat.data:
            if st.button("🚀 GENERAR Y DESCARGAR PDF AHORA", use_container_width=True, type="primary"):
                with st.spinner("Descargando imágenes y creando PDF..."):
                    try:
                        pdf_bytes = generar_pdf_con_fotos(res_cat.data)
                        st.download_button(
                            label="✅ PDF LISTO - CLIC PARA GUARDAR",
                            data=pdf_bytes,
                            file_name=f"Catalogo_DuoLegal_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Error al generar el PDF: {e}")

elif menu == "Reportes":
    st.header("📊 Resumen de Ventas")
    st.write("Solo disponible para administrador.")
