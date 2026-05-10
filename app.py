import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta
import pytz
import json
from fpdf import FPDF
import requests
from io import BytesIO

# --- 1. CONFIGURACIÓN ---
ZONA_LOCAL = pytz.timezone('America/Mexico_City')
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="TUMULTOFLOW", layout="wide", page_icon="⚖️")

# --- 2. FUNCIONES DE APOYO ---
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

def generar_pdf(productos):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, "CATÁLOGO DE PRODUCTOS - DUO LEGAL", ln=True, align="C")
    pdf.ln(10)
    
    col_width = 60
    x_start = 10
    y_start = 30
    count = 0

    for p in productos:
        if count > 0 and count % 3 == 0:
            pdf.add_page()
            y_start = 20
        
        x = x_start + (count % 3) * col_width
        y = pdf.get_y() if count % 3 != 0 else y_start
        
        # Nombre y Precio
        pdf.set_xy(x, y)
        pdf.set_font("Arial", "B", 10)
        pdf.multi_cell(55, 5, f"{p['nombre'][:30]}", align="C")
        
        pdf.set_x(x)
        pdf.set_font("Arial", "", 12)
        pdf.cell(55, 8, f"${p['precio_pub']:,.2f}", ln=True, align="C")
        
        # Nota: La librería fpdf requiere descargar la imagen localmente primero
        # Por simplicidad en este reporte, generamos la lista de precios profesional
        pdf.set_x(x)
        pdf.set_font("Arial", "I", 8)
        pdf.cell(55, 5, f"SKU: {p['codigo']}", ln=True, align="C")
        pdf.ln(10)
        
        count += 1
        y_start = pdf.get_y() if count % 3 == 0 else y_start

    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# --- 3. MANEJO DE SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []
if "temp_matriz" not in st.session_state: st.session_state.temp_matriz = {}

# --- 4. LOGIN ---
if not st.session_state.auth:
    st.title("⚖️ Acceso TumultoFlow")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if (u == "admin" and p == "admin1") or (u == "equipo" and p == "equipo1"):
            st.session_state.auth, st.session_state.role = True, u
            st.rerun()
        else: st.error("Credenciales incorrectas")
    st.stop()

# --- 5. NAVEGACIÓN ---
with st.sidebar:
    st.title(f"⚖️ {st.session_state.role.upper()}")
    opc = ["Ventas", "Inventario"]
    if st.session_state.role == "admin": opc += ["Configuración", "Reportes"]
    menu = st.radio("Sección", opc)
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.auth = False
        st.rerun()

# --- SECCIÓN: VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        busq_v = st.text_input("🔍 Buscar...")
        if busq_v: df_p = df_p[df_p['nombre'].str.contains(busq_v, case=False)]
        
        if not df_p.empty:
            sel = st.selectbox("Seleccionar", [f"{r['codigo']} - {r['nombre']}" for _, r in df_p.iterrows()])
            item = df_p[df_p['codigo'] == sel.split(" - ")[0]].iloc[0]
            
            c1, c2 = st.columns(2)
            with c1:
                if item.get('foto_path'): st.image(item['foto_path'], width=200)
            with c2:
                v_pre = st.number_input("Precio", value=float(item['precio_pub']))
                v_cant = st.number_input("Cantidad", 1, int(item['stock']))
                if st.button("➕ Carrito"):
                    st.session_state.carrito.append({"id": item['id'], "Producto": item['nombre'], "Cantidad": v_cant, "Precio": v_pre, "codigo": item['codigo'], "precio_inv": float(item['precio_inv'])})
                    st.success("Agregado")

    if st.session_state.carrito:
        st.write("---")
        for i, p in enumerate(st.session_state.carrito):
            st.write(f"{p['Cantidad']}x {p['Producto']} - ${p['Precio'] * p['Cantidad']}")
        if st.button("🚀 Finalizar Venta"):
            for p in st.session_state.carrito:
                supabase.table("ventas").insert({"producto": p['Producto'], "cantidad": p['Cantidad'], "precio_total": p['Precio']*p['Cantidad'], "ganancia": (p['Precio']-p['precio_inv'])*p['Cantidad'], "fecha_venta": datetime.now(ZONA_LOCAL).isoformat()}).execute()
            st.session_state.carrito = []
            st.success("Venta Exitosa")

# --- SECCIÓN: INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    tabs = st.tabs(["📋 Lista", "🖨️ Catálogo PDF"]) if st.session_state.role == "equipo" else st.tabs(["📋 Lista", "🆕 Nuevo", "🖨️ Catálogo PDF"])

    with tabs[0]:
        res = supabase.table("productos").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data)[["codigo", "nombre", "stock", "precio_pub"]])

    # Lógica de Catálogo según la posición del Tab
    idx_pdf = 1 if st.session_state.role == "equipo" else 2
    with tabs[idx_pdf]:
        st.subheader("Generar Catálogo Oficial")
        res_cat = supabase.table("productos").select("codigo, nombre, precio_pub").order("nombre").execute()
        if res_cat.data:
            pdf_data = generar_pdf(res_cat.data)
            st.download_button(
                label="📥 DESCARGAR CATÁLOGO EN PDF",
                data=pdf_data,
                file_name="catalogo_duo_legal.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary"
            )
            st.info("Este botón descarga el archivo directamente a tu carpeta de descargas.")

# --- SECCIÓN: REPORTES (SÓLO ADMIN) ---
elif menu == "Reportes" and st.session_state.role == "admin":
    st.header("📊 Ventas")
    res = supabase.table("ventas").select("*").execute()
    if res.data: st.dataframe(pd.DataFrame(res.data))
