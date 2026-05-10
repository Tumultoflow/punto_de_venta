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

# --- 2. MOTOR DE PDF CON IMÁGENES ---
class CatalogoPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'CATÁLOGO DE PRODUCTOS - DUO LEGAL', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generar_pdf_con_fotos(productos):
    pdf = CatalogoPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    curr_x, curr_y = 10, 30
    for i, p in enumerate(productos):
        col = i % 3
        if i > 0 and col == 0:
            curr_y += 75
            curr_x = 10
            if curr_y > 220: pdf.add_page(); curr_y = 30
        
        foto_url = p.get('foto_path')
        if foto_url and str(foto_url).startswith('http'):
            try:
                resp = requests.get(foto_url, timeout=4)
                if resp.status_code == 200:
                    pdf.image(BytesIO(resp.content), x=curr_x + 5, y=curr_y, w=45, h=45)
            except: pass
        
        pdf.set_xy(curr_x, curr_y + 48)
        pdf.set_font('Arial', 'B', 9)
        pdf.multi_cell(55, 4, p['nombre'][:40], align='C')
        pdf.set_x(curr_x)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(46, 125, 50)
        pdf.cell(55, 8, f"${p['precio_pub']:,.2f}", ln=True, align='C')
        pdf.set_text_color(0,0,0)
        curr_x += 60
    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# --- 3. FUNCIONES DE APOYO ---
def obtener_config(tipo):
    res = supabase.table("configuracion").select("id, valor").eq("tipo", tipo).execute()
    return res.data if res.data else []

def cargar_json_seguro(campo):
    try:
        if campo and str(campo).strip().startswith('{'): return json.loads(campo)
        return {"_info_extra": str(campo) if campo else ""}
    except: return {"_info_extra": ""}

def subir_imagen(archivo, sku):
    if not archivo: return None
    ext = archivo.name.split(".")[-1]
    nom = f"{sku}_{datetime.now().strftime('%H%M%S')}.{ext}"
    supabase.storage.from_('fotos').upload(nom, archivo.getvalue())
    return supabase.storage.from_('fotos').get_public_url(nom)

# --- 4. SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []
if "temp_matriz" not in st.session_state: st.session_state.temp_matriz = {}
if "edit_id" not in st.session_state: st.session_state.edit_id = None

# --- 5. LOGIN ---
if not st.session_state.auth:
    st.title("⚖️ Acceso Duo Legal")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if (u == "admin" and p == "admin1") or (u == "equipo" and p == "equipo1"):
            st.session_state.auth, st.session_state.role = True, u
            st.rerun()
    st.stop()

# --- 6. NAVEGACIÓN ---
with st.sidebar:
    st.title(f"MODO: {st.session_state.role.upper()}")
    menu = st.radio("Menú", ["Ventas", "Inventario", "Config", "Reportes"] if st.session_state.role == "admin" else ["Ventas", "Inventario"])
    if st.button("Cerrar Sesión"): st.session_state.auth = False; st.rerun()

# --- SECCIÓN VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        busq = st.text_input("🔍 Buscar...")
        if busq: df_p = df_p[df_p['nombre'].str.contains(busq, case=False) | df_p['codigo'].str.contains(busq, case=False)]
        
        if not df_p.empty:
            sel = st.selectbox("Seleccionar", [f"{r['codigo']} - {r['nombre']}" for _, r in df_p.iterrows()])
            item = df_p[df_p['codigo'] == sel.split(" - ")[0]].iloc[0]
            
            c1, c2 = st.columns(2)
            with c1:
                if item.get('foto_path'): st.image(item['foto_path'], width=250)
            with c2:
                m_data = cargar_json_seguro(item['descripcion'])
                matriz = {k: v for k, v in m_data.items() if k != "_info_extra"}
                if matriz:
                    v_col = st.selectbox("Color", list(matriz.keys()))
                    v_tal = st.selectbox("Talla", list(matriz[v_col].keys()))
                    st.metric("Stock", matriz[v_col][v_tal])
                    v_cant = st.number_input("Cantidad", 1, int(matriz[v_col][v_tal]))
                else:
                    v_col, v_tal, v_cant = "N/A", "N/A", st.number_input("Cantidad", 1, int(item['stock']))
                
                if st.button("➕ Carrito", use_container_width=True):
                    st.session_state.carrito.append({
                        "id": item['id'], "Producto": item['nombre'], "Cantidad": v_cant, 
                        "Precio": float(item['precio_pub']), "Color": v_col, "Talla": v_tal,
                        "codigo": item['codigo'], "precio_inv": float(item['precio_inv']), "matriz": matriz
                    })
                    st.success("Añadido")

    if st.session_state.carrito:
        st.divider()
        for i, p in enumerate(st.session_state.carrito):
            st.write(f"**{p['Cantidad']}x {p['Producto']}** ({p['Color']}/{p['Talla']})")
        if st.button("🚀 FINALIZAR VENTA"):
            for p in st.session_state.carrito:
                # Actualizar DB y Stock
                supabase.table("ventas").insert({"producto": f"{p['Producto']} ({p['Color']})", "cantidad": p['Cantidad'], "precio_total": p['Precio']*p['Cantidad'], "ganancia": (p['Precio']-p['precio_inv'])*p['Cantidad'], "fecha_venta": datetime.now(ZONA_LOCAL).isoformat()}).execute()
            st.session_state.carrito = []; st.success("Venta realizada"); st.rerun()

# --- SECCIÓN INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario y Catálogo")
    tabs = st.tabs(["📋 Lista", "🆕 Registrar", "✏️ Editar", "🖨️ PDF"]) if st.session_state.role == "admin" else st.tabs(["📋 Lista", "🖨️ PDF"])
    
    # 📋 LISTA
    with tabs[0]:
        res_l = supabase.table("productos").select("*").execute()
        if res_l.data:
            df_l = pd.DataFrame(res_l.data)
            st.dataframe(df_l[["codigo", "nombre", "stock", "precio_pub"]])
            for _, r in df_l.iterrows():
                if st.session_state.role == "admin":
                    if st.button(f"Editar {r['codigo']}", key=f"btn_{r['id']}"):
                        st.session_state.edit_id = r['id']
                        st.session_state.temp_matriz = cargar_json_seguro(r['descripcion'])
                        st.info("Ve a la pestaña 'Editor'")

    # 🆕 REGISTRAR (ADMIN)
    if st.session_state.role == "admin":
        with tabs[1]:
            c1, c2 = st.columns(2)
            with c1:
                n_sku, n_nom = st.text_input("SKU"), st.text_input("Nombre")
                n_pub, n_inv = st.number_input("P. Venta"), st.number_input("P. Costo")
                n_foto = st.file_uploader("Foto")
            with c2:
                st.write("Variantes")
                vc, vt, vs = st.text_input("Color"), st.text_input("Talla"), st.number_input("Stock", 0)
                if st.button("Añadir Variante"):
                    st.session_state.temp_matriz.setdefault(vc.upper(), {})[vt.upper()] = int(vs)
                st.json(st.session_state.temp_matriz)
            if st.button("🚀 GUARDAR PRODUCTO"):
                url = subir_imagen(n_foto, n_sku)
                tot = sum(int(q) for c in st.session_state.temp_matriz.values() if isinstance(c, dict) for q in c.values())
                supabase.table("productos").insert({"codigo": n_sku, "nombre": n_nom, "precio_pub": n_pub, "precio_inv": n_inv, "stock": tot, "descripcion": json.dumps(st.session_state.temp_matriz), "foto_path": url}).execute()
                st.session_state.temp_matriz = {}; st.success("Guardado"); st.rerun()

    # 🖨️ PDF (ÚLTIMA PESTAÑA)
    idx_pdf = 3 if st.session_state.role == "admin" else 1
    with tabs[idx_pdf]:
        st.subheader("Generar Catálogo con Fotos")
        res_cat = supabase.table("productos").select("*").execute()
        if res_cat.data:
            if st.button("📥 DESCARGAR PDF", use_container_width=True):
                with st.spinner("Creando PDF..."):
                    bytes_pdf = generar_pdf_con_fotos(res_cat.data)
                    st.download_button("✅ CLIC AQUÍ PARA GUARDAR", bytes_pdf, "catalogo.pdf", "application/pdf")
