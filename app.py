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

# --- CLASE PARA EL PDF DESCARGABLE ---
class CatalogoPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'CATÁLOGO DE PRODUCTOS - DUO LEGAL', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generar_pdf_descargable(productos):
    pdf = CatalogoPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    curr_x, curr_y = 10, 30
    for i, r in enumerate(productos):
        col = i % 3
        if i > 0 and col == 0:
            curr_y += 75
            curr_x = 10
            if curr_y > 220: pdf.add_page(); curr_y = 30
        
        foto_url = r.get('foto_path')
        if foto_url and str(foto_url).startswith('http'):
            try:
                resp = requests.get(foto_url, timeout=4)
                if resp.status_code == 200:
                    pdf.image(BytesIO(resp.content), x=curr_x + 5, y=curr_y, w=45, h=45)
            except: pass
        
        pdf.set_xy(curr_x, curr_y + 48)
        pdf.set_font('Arial', 'B', 9)
        pdf.multi_cell(55, 4, r['nombre'][:40], align='C')
        pdf.set_x(curr_x)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(46, 125, 50)
        pdf.cell(55, 8, f"${r['precio_pub']:,.2f}", ln=True, align='C')
        pdf.set_text_color(0,0,0)
        curr_x += 60
    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# --- CSS PARA EL CATÁLOGO VISUAL ---
st.markdown("""
    <style>
    .product-card {
        border: 2px solid #f0f2f6;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        background-color: white;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .product-name { font-weight: bold; font-size: 1.1em; margin: 10px 0; color: #1f1f1f; }
    .product-price { color: #2e7d32; font-weight: 800; font-size: 1.5em; background: #e8f5e9; padding: 5px 10px; border-radius: 8px; display: inline-block; }
    .product-sku { color: #666; font-size: 0.8em; }
    </style>
""", unsafe_allow_html=True)

# --- 2. FUNCIONES DE APOYO ---
def obtener_config(tipo):
    try:
        res = supabase.table("configuracion").select("id, valor").eq("tipo", tipo).execute()
        return res.data if res.data else []
    except: return []

def generar_sku(cat, sub):
    prefijo = f"{cat[:3]}-{sub[:3]}".upper()
    try:
        res = supabase.table("productos").select("codigo").like("codigo", f"{prefijo}%").execute()
        secuencias = [int(r['codigo'].split('-')[-1]) for r in res.data if '-' in r['codigo']]
        proximo = max(secuencias) + 1 if secuencias else 1
        return f"{prefijo}-{proximo:04d}"
    except: return f"{prefijo}-0001"

def cargar_json_seguro(campo):
    try:
        if campo and str(campo).strip().startswith('{'): return json.loads(campo)
        return {"_info_extra": str(campo) if campo else ""}
    except: return {"_info_extra": ""}

def subir_imagen_supabase(archivo, sku):
    if archivo is None: return None
    try:
        extension = archivo.name.split(".")[-1]
        nombre_archivo = f"{sku}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"
        supabase.storage.from_('fotos').upload(nombre_archivo, archivo.getvalue())
        return supabase.storage.from_('fotos').get_public_url(nombre_archivo)
    except: return None

# --- 3. MANEJO DE SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []
if "edit_id" not in st.session_state: st.session_state.edit_id = None
if "temp_matriz" not in st.session_state: st.session_state.temp_matriz = {}

# --- 4. LOGIN ---
if not st.session_state.auth:
    st.title("⚖️ Acceso Duo Legal")
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
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.auth = False; st.rerun()

# --- SECCIONES (VENTAS SE MANTIENE IGUAL) ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    metodos = [m['valor'] for m in obtener_config("metodo_pago")] or ["EFECTIVO"]
    vendedores = [v['valor'] for v in obtener_config("vendedor")] or ["TIENDA"]
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        busq_v = st.text_input("🔍 Buscar para vender...")
        if busq_v: df_p = df_p[df_p['nombre'].str.contains(busq_v, case=False) | df_p['codigo'].str.contains(busq_v, case=False)]
        if not df_p.empty:
            sel_list = [f"{r['codigo']} - {r['nombre']}" for _, r in df_p.iterrows()]
            sel = st.selectbox("Seleccionar Producto", sel_list)
            item = df_p[df_p['codigo'] == sel.split(" - ")[0]].iloc[0]
            c1, c2 = st.columns([1, 2])
            with c1:
                foto_v = item.get('foto_path')
                if foto_v: st.image(foto_v, width=250)
            with c2:
                data_desc = cargar_json_seguro(item['descripcion'])
                matriz = {k: v for k, v in data_desc.items() if k != "_info_extra"}
                if matriz:
                    v_col = st.selectbox("Color", list(matriz.keys()))
                    v_tal = st.selectbox("Talla", list(matriz[v_col].keys()))
                    v_cant = st.number_input("Cantidad", 1, int(matriz[v_col][v_tal]))
                else:
                    v_col, v_tal, v_cant = "N/A", "N/A", st.number_input("Cantidad", 1, int(item['stock']))
                v_pre = st.number_input("Precio", value=float(item['precio_pub']))
                if st.button("➕ Agregar al Carrito", use_container_width=True):
                    st.session_state.carrito.append({"temp_id": datetime.now().timestamp(), "id": item['id'], "Producto": item['nombre'], "Cantidad": v_cant, "Precio": v_pre, "Color": v_col, "Talla": v_tal, "Vendedor": "TIENDA", "precio_inv": float(item['precio_inv']), "codigo": item['codigo'], "es_matriz": bool(matriz)})
                    st.success("Agregado")

    if st.session_state.carrito:
        st.divider()
        if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
            for p in st.session_state.carrito:
                supabase.table("ventas").insert({"producto": p['Producto'], "cantidad": p['Cantidad'], "precio_total": p['Precio']*p['Cantidad'], "ganancia": (p['Precio']-p['precio_inv'])*p['Cantidad'], "fecha_venta": datetime.now(ZONA_LOCAL).isoformat()}).execute()
            st.session_state.carrito = []; st.success("Venta realizada"); st.rerun()

# --- SECCIÓN: INVENTARIO (CON BOTÓN PDF REAL) ---
elif menu == "Inventario":
    st.header("📦 Inventario y Catálogo")
    tabs_opc = ["📋 Lista", "🆕 Registrar Nuevo", "✏️ Editor", "🖨️ Catálogo"] if st.session_state.role == "admin" else ["📋 Lista", "🖨️ Catálogo"]
    pestañas = st.tabs(tabs_opc)

    with pestañas[0]: # LISTA
        res_i = supabase.table("productos").select("*").order("codigo").execute()
        if res_i.data: st.dataframe(pd.DataFrame(res_i.data)[["codigo", "nombre", "stock", "precio_pub"]], use_container_width=True)

    if st.session_state.role == "admin":
        with pestañas[1]: # REGISTRAR NUEVO (Tu lógica de SKU)
            n_cat = st.selectbox("Categoría", ["GENERAL"], key="n_cat")
            n_sub = st.selectbox("Subcategoría", ["GENERAL"], key="n_sub")
            n_sku = st.text_input("SKU", value=generar_sku(n_cat, n_sub))
            n_nom = st.text_input("Nombre")
            n_pub = st.number_input("Precio Público", 0.0)
            n_inv = st.number_input("Precio Inversión", 0.0)
            n_foto = st.file_uploader("Foto", type=["jpg","png","jpeg"])
            if st.button("🚀 GUARDAR PRODUCTO"):
                url = subir_imagen_supabase(n_foto, n_sku)
                supabase.table("productos").insert({"codigo": n_sku, "nombre": n_nom, "precio_pub": n_pub, "precio_inv": n_inv, "stock": 0, "descripcion": "{}", "foto_path": url}).execute()
                st.success("Guardado"); st.rerun()

    # PESTAÑA CATÁLOGO MEJORADA
    idx_cat = 3 if st.session_state.role == "admin" else 1
    with pestañas[idx_cat]:
        st.subheader("🖼️ Vista de Catálogo")
        res_cat = supabase.table("productos").select("*").order("nombre").execute()
        
        if res_cat.data:
            # BOTÓN DE DESCARGA REAL
            if st.button("📥 DESCARGAR CATÁLOGO EN PDF (CON FOTOS)", type="primary", use_container_width=True):
                with st.spinner("Generando PDF profesional..."):
                    pdf_bytes = generar_pdf_descargable(res_cat.data)
                    st.download_button("✅ CLIC AQUÍ PARA GUARDAR ARCHIVO", pdf_bytes, "catalogo_duo_legal.pdf", "application/pdf", use_container_width=True)
            
            st.divider()
            # VISTA EN PANTALLA (TU DISEÑO CSS)
            cols = st.columns(4)
            for i, r in enumerate(res_cat.data):
                with cols[i % 4]:
                    f_url = r.get('foto_path') or "https://via.placeholder.com/150"
                    st.markdown(f"""
                        <div class="product-card">
                            <img src="{f_url}" style="width:100%; height:140px; object-fit:contain; margin-bottom:10px;">
                            <div class="product-sku">{r['codigo']}</div>
                            <div class="product-name">{r['nombre'][:35]}</div>
                            <div class="product-price">${r['precio_pub']:,.2f}</div>
                        </div>
                    """, unsafe_allow_html=True)

# (Secciones de Configuración y Reportes se mantienen iguales)
elif menu == "Configuración" and st.session_state.role == "admin":
    st.header("⚙️ Configuración")
    # ... (tu código original de configuración)
