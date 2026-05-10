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

# --- 2. CLASE PARA EL PDF (DISEÑO DE CATÁLOGO) ---
class CatalogoPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'CATÁLOGO DE PRODUCTOS - DUO LEGAL', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, f'Fecha: {datetime.now().strftime("%d/%m/%Y")}', 0, 1, 'C')
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
        col = i % items_per_row
        if i > 0 and col == 0:
            curr_y += 75 
            curr_x = margin_x
            if curr_y > 220:
                pdf.add_page()
                curr_y = 30

        # Imagen
        foto_url = p.get('foto_path')
        if foto_url and str(foto_url).startswith('http'):
            try:
                resp = requests.get(foto_url, timeout=5)
                if resp.status_code == 200:
                    img = BytesIO(resp.content)
                    pdf.image(img, x=curr_x + 5, y=curr_y, w=45, h=45)
            except:
                pdf.set_xy(curr_x + 5, curr_y + 20)
                pdf.set_font('Arial', 'I', 7)
                pdf.cell(45, 5, "[Imagen no disponible]", 0, 0, 'C')
        
        # Datos
        pdf.set_xy(curr_x, curr_y + 48)
        pdf.set_font('Arial', 'B', 9)
        pdf.multi_cell(55, 4, p['nombre'][:40], align='C')
        
        pdf.set_x(curr_x)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(46, 125, 50) 
        pdf.cell(55, 8, f"${p['precio_pub']:,.2f}", ln=True, align='C')
        pdf.set_text_color(0, 0, 0)
        
        pdf.set_x(curr_x)
        pdf.set_font('Arial', '', 8)
        pdf.cell(55, 4, f"Ref: {p['codigo']}", ln=True, align='C')
        
        curr_x += col_width

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# --- 3. FUNCIONES GENERALES ---
def obtener_config(tipo):
    try:
        res = supabase.table("configuracion").select("id, valor").eq("tipo", tipo).execute()
        return res.data if res.data else []
    except: return []

def cargar_json_seguro(campo):
    try:
        if campo and str(campo).strip().startswith('{'):
            return json.loads(campo)
        return {"_info_extra": str(campo) if campo else ""}
    except: return {"_info_extra": ""}

# --- 4. SESIÓN Y LOGIN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []
if "temp_matriz" not in st.session_state: st.session_state.temp_matriz = {}

if not st.session_state.auth:
    st.title("⚖️ Acceso TumultoFlow")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if (u == "admin" and p == "admin1") or (u == "equipo" and p == "equipo1"):
            st.session_state.auth, st.session_state.role = True, u
            st.rerun()
        else: st.error("Credenciales incorrectas")
    st.stop()

# --- 5. INTERFAZ ---
with st.sidebar:
    st.title(f"⚖️ {st.session_state.role.upper()}")
    opciones = ["Ventas", "Inventario"]
    if st.session_state.role == "admin": opciones += ["Configuración", "Reportes"]
    menu = st.radio("Sección", opciones)
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.auth = False
        st.rerun()

# --- SECCIONES ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        busq = st.text_input("🔍 Buscar...")
        if busq: df_p = df_p[df_p['nombre'].str.contains(busq, case=False) | df_p['codigo'].str.contains(busq, case=False)]
        
        if not df_p.empty:
            sel = st.selectbox("Producto", [f"{r['codigo']} - {r['nombre']}" for _, r in df_p.iterrows()])
            item = df_p[df_p['codigo'] == sel.split(" - ")[0]].iloc[0]
            
            c1, c2 = st.columns(2)
            with c1:
                if item.get('foto_path'): st.image(item['foto_path'], width=250)
            with c2:
                v_pre = st.number_input("Precio", value=float(item['precio_pub']))
                v_cant = st.number_input("Cantidad", 1, int(item['stock']))
                if st.button("➕ Agregar"):
                    st.session_state.carrito.append({
                        "id": item['id'], "Producto": item['nombre'], "Cantidad": v_cant, 
                        "Precio": v_pre, "codigo": item['codigo'], "precio_inv": float(item['precio_inv'])
                    })
                    st.success("Agregado al carrito")

    if st.session_state.carrito:
        st.divider()
        for i, p in enumerate(st.session_state.carrito):
            st.write(f"**{p['Cantidad']}x {p['Producto']}** - ${p['Precio']*p['Cantidad']:,.2f}")
        if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
            for p in st.session_state.carrito:
                supabase.table("ventas").insert({
                    "producto": p['Producto'], "cantidad": p['Cantidad'], "precio_total": p['Precio']*p['Cantidad'], 
                    "ganancia": (p['Precio']-p['precio_inv'])*p['Cantidad'], "fecha_venta": datetime.now(ZONA_LOCAL).isoformat()
                }).execute()
                # Actualizar stock simple
                res_s = supabase.table("productos").select("stock").eq("id", p['id']).execute()
                nuevo_stock = res_s.data[0]['stock'] - p['Cantidad']
                supabase.table("productos").update({"stock": nuevo_stock}).eq("id", p['id']).execute()
            st.session_state.carrito = []
            st.success("Venta guardada correctamente")
            st.rerun()

elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    tabs = st.tabs(["📋 Lista", "🖨️ Generar Catálogo PDF"])
    
    with tabs[0]:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            st.dataframe(pd.DataFrame(res.data)[["codigo", "nombre", "stock", "precio_pub"]], use_container_width=True)

    with tabs[1]:
        st.subheader("Catálogo con Imágenes")
        st.write("Presiona el botón para generar un archivo PDF profesional con todas las fotos.")
        res_cat = supabase.table("productos").select("codigo, nombre, precio_pub, foto_path").order("nombre").execute()
        
        if res_cat.data:
            if st.button("📥 GENERAR Y DESCARGAR PDF", type="primary", use_container_width=True):
                with st.spinner("Procesando imágenes... esto puede tardar un momento."):
                    pdf_bytes = generar_pdf_con_fotos(res_cat.data)
                    st.download_button(
                        label="✅ ARCHIVO LISTO - CLICK PARA DESCARGAR",
                        data=pdf_bytes,
                        file_name=f"Catalogo_DuoLegal_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

elif menu == "Configuración" and st.session_state.role == "admin":
    st.header("⚙️ Ajustes")
    # Lógica para categorías, vendedores, etc.
    st.write("Aquí puedes añadir métodos de pago o categorías.")

elif menu == "Reportes" and st.session_state.role == "admin":
    st.header("📊 Reporte de Ventas")
    res = supabase.table("ventas").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
        st.metric("Total Ventas", f"${df['precio_total'].sum():,.2f}")
        st.dataframe(df)
