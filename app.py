import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import pytz

# --- 1. CONFIGURACIÓN Y CONEXIÓN ---
ZONA_LOCAL = pytz.timezone('America/Mexico_City')
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="TUMULTOFLOW", layout="wide", page_icon="⚖️")

# --- 2. FUNCIONES DE APOYO Y LÓGICA DE SKU ---

def obtener_config(tipo):
    try:
        res = supabase.table("configuracion").select("valor").eq("tipo", tipo).execute()
        return sorted([r['valor'] for r in res.data]) if res.data else ["GENERAL"]
    except:
        return ["GENERAL"]

def generar_sku(cat, sub):
    """Genera el siguiente SKU disponible para una combinación cat-sub."""
    prefijo = f"{cat[:3]}-{sub[:3]}".upper()
    try:
        res = supabase.table("productos").select("codigo").like("codigo", f"{prefijo}%").execute()
        codigos = [r['codigo'] for r in res.data]
        secuencias = []
        for c in codigos:
            try: secuencias.append(int(c.split('-')[-1]))
            except: continue
        proximo = max(secuencias) + 1 if secuencias else 1
        return f"{prefijo}-{proximo:04d}"
    except:
        return f"{prefijo}-0001"

def validar_duplicado(sku, id_actual=None):
    query = supabase.table("productos").select("id").eq("codigo", sku.upper())
    if id_actual:
        query = query.neq("id", id_actual)
    res = query.execute()
    return len(res.data) > 0

def reestructurar_todos_los_codigos():
    """Reasigna códigos a TODA la base de datos desde 0001."""
    productos = supabase.table("productos").select("*").order("created_at").execute()
    if not productos.data: return
    contadores = {}
    for p in productos.data:
        prefijo = f"{p['categoria'][:3]}-{p['subcategoria'][:3]}".upper()
        contadores[prefijo] = contadores.get(prefijo, 0) + 1
        nuevo_sku = f"{prefijo}-{contadores[prefijo]:04d}"
        supabase.table("productos").update({"codigo": nuevo_sku}).eq("id", p['id']).execute()

# --- 3. AUTENTICACIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []

if not st.session_state.auth:
    st.title("🔐 Acceso")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "admin1": 
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "equipo1": 
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
    st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown(f"**Usuario:** `{st.session_state.role.upper()}`")
    menu = st.radio("Menú Principal", ["Ventas", "Inventario", "Configuración", "Reportes"] if st.session_state.role == "admin" else ["Ventas", "Inventario"])
    if st.button("🚪 CERRAR SESIÓN", use_container_width=True):
        st.session_state.auth = False
        st.session_state.carrito = []
        st.rerun()

# --- 4. SECCIÓN: VENTAS ---
if menu == "Ventas":
    st.header("💰 Nueva Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).order("codigo").execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        opciones = [f"{r['codigo']} - {r['nombre']}" for r in res.data]
        sel_prod = st.selectbox("📦 Seleccionar Producto", opciones)
        item = df_p[df_p['codigo'] == sel_prod.split(" - ")[0]].iloc[0]
        
        c1, c2 = st.columns([1, 2])
        with c1:
            if item.get('foto_path'): st.image(item['foto_path'], width=250)
            st.info(f"**Stock disponible:** {item['stock']}")
        
        with c2:
            colores = [c.strip().upper() for c in item['colores'].split(',') if c.strip()] if item.get('colores') else ["ÚNICO"]
            v_col = st.selectbox("🎨 Color", colores)
            v_cant = st.number_input("Cantidad", 1, int(item['stock']))
            v_pre = st.number_input("Precio Venta", value=float(item['precio_pub']))
            if st.button("➕ Añadir al Carrito"):
                st.session_state.carrito.append({
                    "id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'],
                    "color": v_col, "cantidad": v_cant, "precio": v_pre, 
                    "precio_inv": item['precio_inv'], "foto": item.get('foto_path')
                })
                st.toast("Añadido")

        if st.session_state.carrito:
            st.divider()
            st.subheader("🛒 Carrito")
            total_v = 0
            for i, p in enumerate(st.session_state.carrito):
                st.write(f"{p['nombre']} ({p['color']}) x{p['cantidad']} - **${p['precio']*p['cantidad']:,.2f}**")
                total_v += p['precio']*p['cantidad']
            
            v_vend = st.text_input("Vendedor", key="vendedor_input")
            if st.button("🚀 FINALIZAR VENTA", type="primary") and v_vend:
                for p in st.session_state.carrito:
                    stk_actual = supabase.table("productos").select("stock").eq("id", p['id']).execute().data[0]['stock']
                    supabase.table("productos").update({"stock": stk_actual - p['cantidad']}).eq("id", p['id']).execute()
                    supabase.table("ventas").insert({
                        "producto": p['nombre'], "codigo_prod": p['codigo'], "color": p['color'],
                        "cantidad": p['cantidad'], "precio_total": p['precio']*p['cantidad'],
                        "vendedor": v_vend, "ganancia": (p['precio'] - p['precio_inv']) * p['cantidad'],
                        "foto_path": p['foto'], "fecha_venta": datetime.now(ZONA_LOCAL).isoformat()
                    }).execute()
                st.session_state.carrito = []
                st.success("Venta realizada")
                st.rerun()

# --- 5. SECCIÓN: INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    cats = obtener_config("categoria")
    subs = obtener_config("subcategoria")
    
    if st.session_state.role == "admin":
        with st.expander("🛠️ Herramientas Críticas"):
            if st.button("♻️ REORGANIZAR TODOS LOS CÓDIGOS (RESET SECUENCIA)"):
                reestructurar_todos_los_codigos()
                st.success("Códigos reordenados")
                st.rerun()

    tab1, tab2 = st.tabs(["📋 Lista y Edición", "🆕 Agregar Nuevo"])
    
    with tab1:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            df_i = pd.DataFrame(res.data)
            if st.session_state.role == "admin":
                sel = st.selectbox("Editar producto:", ["-- Seleccionar --"] + [f"{r['codigo']} - {r['nombre']}" for r in res.data])
                if sel != "-- Seleccionar --":
                    it = df_i[df_i['codigo'] == sel.split(" - ")[0]].iloc[0]
                    with st.expander("Formulario de Edición", expanded=True):
                        c1, c2 = st.columns(2)
                        with c1:
                            e_nom = st.text_input("Nombre", value=it['nombre'], key=f"n_{it['id']}")
                            e_cat = st.selectbox("Categoría", cats, index=cats.index(it['categoria']) if it['categoria'] in cats else 0, key=f"c_{it['id']}")
                            e_sub = st.selectbox("Subcategoría", subs, index=subs.index(it['subcategoria']) if it['subcategoria'] in subs else 0, key=f"s_{it['id']}")
                        with c2:
                            # Lógica reactiva de SKU en edición
                            val_sku = generar_sku(e_cat, e_sub) if (e_cat != it['categoria'] or e_sub != it['subcategoria']) else it['codigo']
                            e_cod = st.text_input("Código SKU", value=val_sku, key=f"k_{it['id']}")
                            e_stk = st.number_input("Stock", value=int(it['stock']), key=f"st_{it['id']}")
                            e_pub = st.number_input("Precio", value=float(it['precio_pub']), key=f"p_{it['id']}")
                        
                        if st.button("💾 Guardar Cambios", key=f"b_{it['id']}"):
                            supabase.table("productos").update({"codigo": e_cod.upper(), "nombre": e_nom, "categoria": e_cat, "subcategoria": e_sub, "stock": e_stk, "precio_pub": e_pub}).eq("id", it['id']).execute()
                            st.rerun()
            st.dataframe(df_i, use_container_width=True)

    with tab2:
        with st.form("nuevo_p"):
            n_cat = st.selectbox("Categoría", cats)
            n_sub = st.selectbox("Subcategoría", subs)
            sku_auto = generar_sku(n_cat, n_sub)
            n_cod = st.text_input("Código", value=sku_auto)
            n_nom = st.text_input("Nombre")
            n_inv = st.number_input("Costo Inversión", 0.0)
            n_pub = st.number_input("Precio Venta", 0.0)
            n_stk = st.number_input("Stock Inicial", 1)
            foto = st.file_uploader("Foto", type=['jpg','png','jpeg'])
            if st.form_submit_button("🚀 Registrar"):
                if n_nom and foto:
                    fname = f"{n_cod}.jpg"
                    supabase.storage.from_("fotos").upload(fname, foto.getvalue())
                    url = supabase.storage.from_("fotos").get_public_url(fname)
                    supabase.table("productos").insert({"codigo": n_cod.upper(), "nombre": n_nom, "categoria": n_cat, "subcategoria": n_sub, "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk, "foto_path": url}).execute()
                    st.rerun()

# --- 6. SECCIÓN: CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
    t = st.radio("Editar:", ["Categorías", "Subcategorías"], horizontal=True)
    db_t = "categoria" if t == "Categorías" else "subcategoria"
    n_v = st.text_input("Nuevo valor").upper()
    if st.button("➕ Añadir") and n_v:
        supabase.table("configuracion").insert({"tipo": db_t, "valor": n_v}).execute(); st.rerun()
    res = supabase.table("configuracion").select("*").eq("tipo", db_t).execute()
    for r in res.data:
        c1, c2 = st.columns([5,1])
        c1.write(r['valor'])
        if c2.button("🗑️", key=r['id']):
            supabase.table("configuracion").delete().eq("id", r['id']).execute(); st.rerun()

# --- 7. SECCIÓN: REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_r = pd.DataFrame(res_v.data)
        st.metric("Total Ingresos", f"${df_r['precio_total'].sum():,.2f}")
        st.dataframe(df_r, use_container_width=True)
    else:
        st.info("No hay ventas registradas.")
