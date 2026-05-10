import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import pytz
import json
import io

# --- 1. CONFIGURACIÓN ---
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
    except: return ["GENERAL"]

def generar_sku(cat, sub):
    prefijo = f"{cat[:3]}-{sub[:3]}".upper()
    try:
        res = supabase.table("productos").select("codigo").like("codigo", f"{prefijo}%").execute()
        secuencias = [int(r['codigo'].split('-')[-1]) for r in res.data if '-' in r['codigo']]
        proximo = max(secuencias) + 1 if secuencias else 1
        return f"{prefijo}-{proximo:04d}"
    except: return f"{prefijo}-0001"

# --- 3. MANEJO DE SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []
if "edit_id" not in st.session_state: st.session_state.edit_id = None
if "temp_matriz" not in st.session_state: st.session_state.temp_matriz = {}

# --- 4. LOGIN ---
if not st.session_state.auth:
    st.title("⚖️ Acceso TumultoFlow")
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

# --- 5. NAVEGACIÓN (CON BOTÓN DE CIERRE SESIÓN) ---
with st.sidebar:
    st.title("⚖️ MENU")
    opciones_menu = ["Ventas", "Inventario"]
    if st.session_state.role == "admin": 
        opciones_menu += ["Configuración", "Reportes"]
    
    menu = st.radio("Ir a:", opciones_menu)
    
    st.divider()
    if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
        st.session_state.auth = False
        st.session_state.role = None
        st.session_state.carrito = []
        st.rerun()

# --- SECCIÓN: VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        busq = st.text_input("🔍 Buscar producto por nombre o código...")
        if busq:
            df_p = df_p[df_p['nombre'].str.contains(busq, case=False) | df_p['codigo'].str.contains(busq, case=False)]
        
        if not df_p.empty:
            sel_list = [f"{r['codigo']} - {r['nombre']}" for _, r in df_p.iterrows()]
            sel = st.selectbox("Seleccionar Producto", sel_list)
            item = df_p[df_p['codigo'] == sel.split(" - ")[0]].iloc[0]
            
            c1, c2 = st.columns([1, 2])
            with c1:
                if item.get('foto_path'): st.image(item['foto_path'], width=200)
            
            with c2:
                try:
                    matriz = json.loads(item['descripcion']) if item['descripcion'] and item['descripcion'].startswith('{') else None
                except: matriz = None

                if matriz:
                    v_col = st.selectbox("Color", list(matriz.keys()))
                    v_tal = st.selectbox("Talla / Pieza", list(matriz[v_col].keys()))
                    stock_v = matriz[v_col][v_tal]
                    st.metric("Disponible", stock_v)
                    v_cant = st.number_input("Cantidad", 1, max(1, int(stock_v)))
                    nombre_venta = f"{item['nombre']} ({v_col}-{v_tal})"
                else:
                    v_cant = st.number_input("Cantidad", 1, int(item['stock']))
                    nombre_venta = item['nombre']
                    v_col, v_tal = None, None

                v_pre = st.number_input("Precio", value=float(item['precio_pub']))
                if st.button("➕ Agregar al Carrito"):
                    st.session_state.carrito.append({
                        "id": item['id'], "codigo": item['codigo'], "nombre": nombre_venta,
                        "cantidad": v_cant, "precio": v_pre, "precio_inv": float(item['precio_inv']),
                        "es_matriz": bool(matriz), "v_col": v_col, "v_tal": v_tal
                    })
                    st.toast("Agregado")

        if st.session_state.carrito:
            st.divider()
            st.subheader("🛒 Carrito Actual")
            st.table(pd.DataFrame(st.session_state.carrito)[['nombre', 'cantidad', 'precio']])
            if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
                for p in st.session_state.carrito:
                    prod_db = supabase.table("productos").select("*").eq("id", p['id']).execute().data[0]
                    nuevo_total = prod_db['stock'] - p['cantidad']
                    if p['es_matriz']:
                        m_act = json.loads(prod_db['descripcion'])
                        m_act[p['v_col']][p['v_tal']] -= p['cantidad']
                        supabase.table("productos").update({"stock": nuevo_total, "descripcion": json.dumps(m_act)}).eq("id", p['id']).execute()
                    else:
                        supabase.table("productos").update({"stock": nuevo_total}).eq("id", p['id']).execute()
                    
                    meta_venta = json.dumps({"es_matriz": p['es_matriz'], "v_col": p['v_col'], "v_tal": p['v_tal']})
                    supabase.table("ventas").insert({
                        "producto": p['nombre'], "codigo_prod": p['codigo'], "cantidad": p['cantidad'],
                        "precio_total": p['precio'] * p['cantidad'], "ganancia": (p['precio'] - p['precio_inv']) * p['cantidad'],
                        "vendedor": st.session_state.role.upper(), "fecha_venta": datetime.now(ZONA_LOCAL).isoformat(), "color": meta_venta
                    }).execute()
                st.session_state.carrito = []
                st.success("Venta Registrada"); st.rerun()

# --- SECCIÓN: INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    cats, subs = obtener_config("categoria"), obtener_config("subcategoria")
    tabs = st.tabs(["📋 Lista", "🆕 Nuevo con Variantes", "✏️ Editar"])

    with tabs[0]:
        busq_i = st.text_input("🔍 Buscar en lista...")
        res_i = supabase.table("productos").select("*").order("codigo").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            if busq_i: df_i = df_i[df_i['nombre'].str.contains(busq_i, case=False) | df_i['codigo'].str.contains(busq_i, case=False)]
            for _, r in df_i.iterrows():
                c_im, c_tx, c_ac = st.columns([1, 4, 1])
                if r['foto_path']: c_im.image(r['foto_path'], width=70)
                c_tx.write(f"**{r['codigo']}** - {r['nombre']}")
                c_tx.caption(f"Stock: {r['stock']} | P. Público: ${r['precio_pub']}")
                if c_ac.button("✏️", key=f"e_{r['id']}"):
                    st.session_state.edit_id = r['id']
                    st.rerun()
                st.divider()

    with tabs[1]:
        st.subheader("Registrar Producto y Variantes")
        c_n1, c_n2 = st.columns(2)
        with c_n1:
            n_cat = st.selectbox("Categoría", cats)
            n_sub = st.selectbox("Subcategoría", subs)
            n_sku = st.text_input("Código", value=generar_sku(n_cat, n_sub))
            n_nom = st.text_input("Nombre")
            n_pub = st.number_input("Precio Venta", 0.0)
            n_inv = st.number_input("Precio Costo", 0.0)
            n_foto = st.file_uploader("Imagen")
        with c_n2:
            st.write("**Panel de Variantes**")
            m_col = st.text_input("Color", key="mc")
            m_tal = st.text_input("Talla / Pieza", key="mt")
            m_can = st.number_input("Stock inicial", 0, key="mq")
            if st.button("Añadir Variante"):
                if m_col and m_tal:
                    if m_col not in st.session_state.temp_matriz: st.session_state.temp_matriz[m_col] = {}
                    st.session_state.temp_matriz[m_col][m_tal] = m_can
            st.write(st.session_state.temp_matriz)
            if st.button("Limpiar Variantes"): st.session_state.temp_matriz = {}

        if st.button("🚀 GUARDAR PRODUCTO"):
            total_stk = sum(sum(t.values()) for t in st.session_state.temp_matriz.values())
            url = ""
            if n_foto:
                fn = f"{n_sku}_{datetime.now().strftime('%H%M%S')}.jpg"
                supabase.storage.from_("fotos").upload(fn, n_foto.getvalue())
                url = supabase.storage.from_("fotos").get_public_url(fn)
            
            supabase.table("productos").insert({
                "codigo": n_sku, "nombre": n_nom, "precio_pub": n_pub, "precio_inv": n_inv,
                "stock": total_stk, "descripcion": json.dumps(st.session_state.temp_matriz),
                "foto_path": url, "categoria": n_cat, "subcategoria": n_sub
            }).execute()
            st.session_state.temp_matriz = {}
            st.success("Guardado!"); st.rerun()

    with tabs[2]:
        if st.session_state.edit_id:
            p_ed = supabase.table("productos").select("*").eq("id", st.session_state.edit_id).execute().data[0]
            e_nom = st.text_input("Nombre", value=p_ed['nombre'])
            e_pre = st.number_input("Precio Venta", value=float(p_ed['precio_pub']))
            e_stk = st.number_input("Stock Total (Ajuste Manual)", value=int(p_ed['stock']))
            if st.button("💾 Guardar Cambios"):
                supabase.table("productos").update({"nombre": e_nom, "precio_pub": e_pre, "stock": e_stk}).eq("id", st.session_state.edit_id).execute()
                st.session_state.edit_id = None
                st.rerun()
            if st.button("Cancelar"): st.session_state.edit_id = None; st.rerun()

# --- SECCIÓN: CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
    c1, c2 = st.columns(2)
    with c1:
        tipo = st.selectbox("Tipo", ["categoria", "subcategoria"])
        valor = st.text_input("Nombre").upper()
        if st.button("Añadir"):
            supabase.table("configuracion").insert({"tipo": tipo, "valor": valor}).execute()
            st.rerun()
    with c2:
        res_cfg = supabase.table("configuracion").select("*").execute()
        if res_cfg.data:
            df_cfg = pd.DataFrame(res_cfg.data)
            for _, r in df_cfg.iterrows():
                col1, col2 = st.columns([3, 1])
                col1.write(f"**{r['tipo']}**: {r['valor']}")
                if col2.button("🗑️", key=f"c_{r['id']}"):
                    supabase.table("configuracion").delete().eq("id", r['id']).execute(); st.rerun()

# --- SECCIÓN: REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes y Cancelaciones")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        st.dataframe(df_v[['id', 'fecha_venta', 'producto', 'cantidad', 'precio_total']])
        
        st.divider()
        id_can = st.selectbox("Anular Venta por ID", df_v['id'].tolist())
        if st.button("❌ ANULAR VENTA SELECCIONADA", type="primary"):
            v_info = df_v[df_v['id'] == id_can].iloc[0]
            p_db = supabase.table("productos").select("*").eq("codigo", v_info['codigo_prod']).execute().data[0]
            try:
                meta = json.loads(v_info['color'])
            except: meta = {"es_matriz": False}
            
            nuevo_stk = p_db['stock'] + v_info['cantidad']
            if meta.get('es_matriz'):
                m_act = json.loads(p_db['descripcion'])
                m_act[meta['v_col']][meta['v_tal']] += v_info['cantidad']
                supabase.table("productos").update({"stock": nuevo_stk, "descripcion": json.dumps(m_act)}).eq("id", p_db['id']).execute()
            else:
                supabase.table("productos").update({"stock": nuevo_stk}).eq("id", p_db['id']).execute()
            
            supabase.table("ventas").delete().eq("id", id_can).execute()
            st.success("Venta anulada"); st.rerun()
