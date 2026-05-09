import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import pytz
import io

# --- 1. CONFIGURACIÓN Y CONEXIÓN ---
ZONA_LOCAL = pytz.timezone('America/Mexico_City')
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="TUMULTOFLOW", layout="wide", page_icon="⚖️")

# --- 2. FUNCIONES DE APOYO ---
def obtener_config(tipo):
    try:
        res = supabase.table("configuracion").select("valor").eq("tipo", tipo).execute()
        return sorted([r['valor'] for r in res.data]) if res.data else ["GENERAL"]
    except:
        return ["GENERAL"]

def generar_sku(cat, sub):
    if not cat or not sub: return "GEN-GEN-0001"
    prefijo = f"{cat[:3]}-{sub[:3]}".upper()
    try:
        res = supabase.table("productos").select("codigo").like("codigo", f"{prefijo}%").execute()
        secuencias = [int(r['codigo'].split('-')[-1]) for r in res.data if '-' in r['codigo']]
        proximo = max(secuencias) + 1 if secuencias else 1
        return f"{prefijo}-{proximo:04d}"
    except:
        return f"{prefijo}-0001"

def generar_html_catalogo(df):
    """Genera un archivo HTML con diseño de catálogo para imprimir."""
    html = """
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; }
            .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }
            .card { border: 1px solid #eee; padding: 10px; text-align: center; border-radius: 10px; page-break-inside: avoid; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
            .card img { max-width: 100%; height: 180px; object-fit: contain; margin-bottom: 10px; }
            .precio { font-size: 22px; color: #1a73e8; font-weight: bold; margin-top: 5px; }
            .sku { font-size: 11px; color: #888; text-transform: uppercase; }
            .nombre { font-size: 16px; font-weight: 600; height: 40px; overflow: hidden; }
            h1 { text-align: center; color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }
            @media print { .no-print { display: none; } body { margin: 0; } }
        </style>
    </head>
    <body>
        <h1>📦 CATÁLOGO DE PRODUCTOS - TUMULTOFLOW</h1>
        <div class="grid">
    """
    for _, r in df.iterrows():
        img = r['foto_path'] if r['foto_path'] else "https://via.placeholder.com/200"
        html += f"""
        <div class="card">
            <img src="{img}">
            <div class="sku">{r['codigo']}</div>
            <div class="nombre">{r['nombre']}</div>
            <div style="color: #555; font-size: 13px;">{r['categoria']}</div>
            <div class="precio">${r['precio_pub']:,.2f}</div>
        </div>
        """
    html += "</div></body></html>"
    return html

# --- 3. MANEJO DE SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "role" not in st.session_state: st.session_state.role = None
if "carrito" not in st.session_state: st.session_state.carrito = []

# --- 4. LOGIN ---
if not st.session_state.auth:
    st.title("⚖️ Acceso Sistema TumultoFlow")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if u == "admin" and p == "admin1": 
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "equipo1":
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
        else: st.error("Credenciales incorrectas")
    st.stop()

# --- 5. NAVEGACIÓN ---
with st.sidebar:
    st.title("⚖️ TUMULTOFLOW")
    st.write(f"Usuario: **{st.session_state.role.upper()}**")
    opc = ["Ventas", "Inventario"]
    if st.session_state.role == "admin": opc += ["Configuración", "Reportes"]
    menu = st.radio("Menú", opc)
    if st.button("Cerrar Sesión"):
        st.session_state.auth = False
        st.rerun()

# --- SECCIÓN VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).order("codigo").execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        sel = st.selectbox("Buscar Producto", [f"{r['codigo']} - {r['nombre']}" for r in res.data])
        item = df_p[df_p['codigo'] == sel.split(" - ")[0]].iloc[0]
        
        c1, c2 = st.columns([1, 2])
        with c1:
            if item.get('foto_path'): st.image(item['foto_path'], width=250)
        with c2:
            st.subheader(item['nombre'])
            v_cant = st.number_input("Cantidad a vender", 1, int(item['stock']))
            v_pre = st.number_input("Precio unitario", value=float(item['precio_pub']))
            if st.button("➕ Agregar al Carrito", use_container_width=True):
                st.session_state.carrito.append({
                    "id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'],
                    "cantidad": v_cant, "precio": v_pre, "precio_inv": float(item['precio_inv'])
                })
                st.toast("Producto agregado")

        if st.session_state.carrito:
            st.divider()
            df_c = pd.DataFrame(st.session_state.carrito)
            st.table(df_c[['codigo', 'nombre', 'cantidad', 'precio']])
            v_vendedor = st.text_input("Nombre del Vendedor", value="EQUIPO" if st.session_state.role == "equipo" else "ADMIN")
            
            if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
                try:
                    for p in st.session_state.carrito:
                        # 1. Descontar Stock
                        prod_db = supabase.table("productos").select("stock").eq("id", p['id']).execute()
                        nuevo_stock = int(prod_db.data[0]['stock']) - p['cantidad']
                        supabase.table("productos").update({"stock": nuevo_stock}).eq("id", p['id']).execute()
                        
                        # 2. Registrar Venta con números limpios
                        supabase.table("ventas").insert({
                            "producto": str(p['nombre']),
                            "codigo_prod": str(p['codigo']),
                            "cantidad": int(p['cantidad']),
                            "precio_total": float(p['precio'] * p['cantidad']),
                            "ganancia": float((p['precio'] - p['precio_inv']) * p['cantidad']),
                            "vendedor": v_vendedor.upper()
                        }).execute()
                    
                    st.session_state.carrito = []
                    st.success("¡Venta registrada con éxito!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar venta: {e}")

# --- SECCIÓN INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Productos")
    cats, subs = obtener_config("categoria"), obtener_config("subcategoria")
    
    tabs = st.tabs(["📋 Catálogo e Impresión", "🆕 Nuevo Producto"])
    
    with tabs[0]:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            df_i = pd.DataFrame(res.data)
            
            # --- BOTONES DE DESCARGA ---
            st.subheader("📥 Exportar Catálogo")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                # Botón HTML Imprimible
                html_cat = generar_html_catalogo(df_i)
                st.download_button("🖼️ Descargar Catálogo con Fotos (HTML)", html_cat, "catalogo_tumultoflow.html", "text/html", use_container_width=True)
            with col_d2:
                # Botón Excel Corregido
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_i[['codigo', 'nombre', 'categoria', 'precio_pub', 'stock']].to_excel(writer, index=False)
                st.download_button("📊 Descargar Lista de Precios (Excel)", buffer.getvalue(), "lista_precios.xlsx", "application/vnd.ms-excel", use_container_width=True)
            
            st.divider()
            
            # --- TABLA DE GESTIÓN Y EDICIÓN ---
            sel_e = st.selectbox("Editar Producto:", ["-- Seleccionar --"] + [f"{r['codigo']} - {r['nombre']}" for r in res.data])
            if sel_e != "-- Seleccionar --":
                it = df_i[df_i['codigo'] == sel_e.split(" - ")[0]].iloc[0]
                with st.expander("✏️ Modificar Producto", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        e_nom = st.text_input("Nombre", it['nombre'])
                        e_cat = st.selectbox("Categoría", cats, index=cats.index(it['categoria']) if it['categoria'] in cats else 0)
                        e_sub = st.selectbox("Subcategoría", subs, index=subs.index(it['subcategoria']) if it['subcategoria'] in subs else 0)
                        e_sku = st.text_input("SKU (Código)", it['codigo'])
                    with c2:
                        e_pub = st.number_input("Precio Venta", value=float(it['precio_pub']))
                        e_inv = st.number_input("Costo", value=float(it['precio_inv'])) if st.session_state.role == "admin" else it['precio_inv']
                        e_stk = st.number_input("Stock", value=int(it['stock']))
                    
                    if st.button("💾 Actualizar"):
                        supabase.table("productos").update({
                            "nombre": e_nom, "categoria": e_cat, "subcategoria": e_sub,
                            "codigo": e_sku.upper(), "precio_pub": e_pub, "precio_inv": e_inv, "stock": e_stk
                        }).eq("id", it['id']).execute()
                        st.success("Cambios guardados")
                        st.rerun()

            st.dataframe(df_i, column_config={"foto_path": st.column_config.ImageColumn("Mini")}, use_container_width=True)

    with tabs[1]:
        if st.session_state.role == "admin":
            st.subheader("Crear Nuevo Artículo")
            n_cat = st.selectbox("Categoría ", cats)
            n_sub = st.selectbox("Subcategoría ", subs)
            n_sku = st.text_input("Código SKU Sugerido", value=generar_sku(n_cat, n_sub))
            n_nom = st.text_input("Nombre del Producto")
            c1, c2 = st.columns(2)
            n_inv = c1.number_input("Precio de Compra", 0.0)
            n_pub = c2.number_input("Precio de Venta", 0.0)
            n_stk = c1.number_input("Stock Inicial", 0)
            n_foto = st.file_uploader("Subir Imagen", type=['jpg','png','jpeg'])
            
            if st.button("🚀 GUARDAR PRODUCTO", use_container_width=True):
                if n_nom and n_foto:
                    fn = f"{n_sku}_{datetime.now().strftime('%H%M%S')}.jpg"
                    supabase.storage.from_("fotos").upload(fn, n_foto.getvalue())
                    url = supabase.storage.from_("fotos").get_public_url(fn)
                    supabase.table("productos").insert({
                        "codigo": n_sku.upper(), "nombre": n_nom, "categoria": n_cat, "subcategoria": n_sub,
                        "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk, "foto_path": url
                    }).execute()
                    st.success("Producto creado")
                    st.rerun()
        else:
            st.warning("Solo el administrador puede crear productos.")

# --- SECCIÓN CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración del Sistema")
    tipo = st.radio("Editar:", ["categoria", "subcategoria"], horizontal=True)
    nuevo_val = st.text_input(f"Nuevo {tipo}").upper()
    if st.button("Agregar"):
        supabase.table("configuracion").insert({"tipo": tipo, "valor": nuevo_val}).execute()
        st.rerun()
    
    res = supabase.table("configuracion").select("*").eq("tipo", tipo).execute()
    for r in res.data:
        c1, c2 = st.columns([5,1])
        c1.write(r['valor'])
        if c2.button("🗑️", key=r['id']):
            supabase.table("configuracion").delete().eq("id", r['id']).execute()
            st.rerun()

# --- SECCIÓN REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reporte de Ventas")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        st.metric("Total Ingresos", f"${df_v['precio_total'].sum():,.2f}")
        st.metric("Ganancia Estimada", f"${df_v['ganancia'].sum():,.2f}")
        st.dataframe(df_v, use_container_width=True)
