import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import pytz
import io
import json

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
if "role" not in st.session_state: st.session_state.role = None
if "carrito" not in st.session_state: st.session_state.carrito = []
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

# --- 5. NAVEGACIÓN ---
with st.sidebar:
    st.title("⚖️ MENU")
    opc = ["Ventas", "Inventario"]
    if st.session_state.role == "admin": opc += ["Configuración", "Reportes"]
    menu = st.radio("Sección", opc)
    if st.button("Cerrar Sesión"):
        st.session_state.auth = False
        st.rerun()

# --- SECCIÓN: VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).order("codigo").execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        busqueda_v = st.text_input("🔍 Buscar producto...", placeholder="Nombre, código o variante")
        if busqueda_v:
            df_p = df_p[df_p.apply(lambda r: busqueda_v.lower() in str(r['nombre']).lower() or busqueda_v.lower() in str(r['codigo']).lower(), axis=1)]
        
        if not df_p.empty:
            sel_nom = st.selectbox("Seleccionar Producto", df_p['nombre'].tolist())
            item = df_p[df_p['nombre'] == sel_nom].iloc[0]
            
            c1, c2 = st.columns([1, 2])
            with c1:
                if item.get('foto_path'): st.image(item['foto_path'], width=200)
            
            with c2:
                # Verificar si tiene matriz de stock en la descripción
                try:
                    matriz = json.loads(item['descripcion']) if item['descripcion'].startswith('{') else None
                except: matriz = None

                if matriz:
                    v_col = st.selectbox("Color", list(matriz.keys()))
                    v_tal = st.selectbox("Talla / Piezas", list(matriz[v_col].keys()))
                    st.metric("Disponible", matriz[v_col][v_tal])
                    max_v = int(matriz[v_col][v_tal])
                    v_cant = st.number_input("Cantidad", 1, max_v if max_v > 0 else 1)
                    nombre_final = f"{item['nombre']} ({v_col} - {v_tal})"
                else:
                    st.info(f"Opciones: {item.get('color', 'N/A')}")
                    v_cant = st.number_input("Cantidad", 1, int(item['stock']))
                    nombre_final = item['nombre']

                v_pre = st.number_input("Precio unitario", value=float(item['precio_pub']))
                if st.button("➕ Agregar al Carrito"):
                    st.session_state.carrito.append({
                        "id": item['id'], "codigo": item['codigo'], "nombre": nombre_final,
                        "cantidad": v_cant, "precio": v_pre, "precio_inv": float(item['precio_inv']),
                        "es_matriz": bool(matriz), "v_col": v_col if matriz else None, "v_tal": v_tal if matriz else None
                    })
                    st.toast("Agregado!")

        if st.session_state.carrito:
            st.divider()
            st.table(pd.DataFrame(st.session_state.carrito)[['codigo', 'nombre', 'cantidad', 'precio']])
            if st.button("🚀 FINALIZAR VENTA", type="primary"):
                for p in st.session_state.carrito:
                    # Actualizar Stock General
                    prod_db = supabase.table("productos").select("*").eq("id", p['id']).execute().data[0]
                    nuevo_total = prod_db['stock'] - p['cantidad']
                    
                    # Si es matriz, actualizar JSON
                    if p['es_matriz']:
                        m_act = json.loads(prod_db['descripcion'])
                        m_act[p['v_col']][p['v_tal']] -= p['cantidad']
                        supabase.table("productos").update({"stock": nuevo_total, "descripcion": json.dumps(m_act)}).eq("id", p['id']).execute()
                    else:
                        supabase.table("productos").update({"stock": nuevo_total}).eq("id", p['id']).execute()
                    
                    supabase.table("ventas").insert({
                        "producto": p['nombre'], "codigo_prod": p['codigo'], "cantidad": p['cantidad'],
                        "precio_total": p['precio'] * p['cantidad'], "vendedor": st.session_state.role,
                        "fecha_venta": datetime.now(ZONA_LOCAL).isoformat()
                    }).execute()
                st.session_state.carrito = []
                st.success("Venta realizada"); st.rerun()

# --- SECCIÓN: INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    cats, subs = obtener_config("categoria"), obtener_config("subcategoria")
    tabs = st.tabs(["📋 Lista", "🆕 Nuevo Producto (Matriz)"])
    
    with tabs[0]:
        res = supabase.table("productos").select("*").execute()
        if res.data:
            df_i = pd.DataFrame(res.data)
            st.dataframe(df_i[['codigo', 'nombre', 'stock', 'precio_pub']])

    with tabs[1]:
        st.subheader("Registro Único con Múltiples Variantes")
        col1, col2 = st.columns(2)
        with col1:
            n_cat = st.selectbox("Categoría", cats)
            n_sub = st.selectbox("Subcategoría", subs)
            n_sku = st.text_input("Código", value=generar_sku(n_cat, n_sub))
            n_nom = st.text_input("Nombre del Producto")
            n_pre_v = st.number_input("Precio Venta")
            n_pre_c = st.number_input("Precio Costo")
            n_foto = st.file_uploader("Imagen", type=['jpg','png'])
        
        with col2:
            st.write("**Añadir Variantes (Color/Talla)**")
            m_col = st.text_input("Color", key="m_col_in")
            m_tal = st.text_input("Talla/Pieza", key="m_tal_in")
            m_cant = st.number_input("Cantidad", 0, key="m_cant_in")
            if st.button("Añadir Variante"):
                if m_col and m_tal:
                    if m_col not in st.session_state.temp_matriz: st.session_state.temp_matriz[m_col] = {}
                    st.session_state.temp_matriz[m_col][m_tal] = m_cant
            
            if st.session_state.temp_matriz:
                st.write(st.session_state.temp_matriz)
                if st.button("🗑️ Limpiar Variantes"): st.session_state.temp_matriz = {}; st.rerun()

        if st.button("🚀 GUARDAR PRODUCTO EN BASE DE DATOS"):
            if n_nom and n_foto and st.session_state.temp_matriz:
                fn = f"{n_sku}.jpg"
                supabase.storage.from_("fotos").upload(fn, n_foto.getvalue())
                url = supabase.storage.from_("fotos").get_public_url(fn)
                total = sum(sum(t.values()) for t in st.session_state.temp_matriz.values())
                
                supabase.table("productos").insert({
                    "codigo": n_sku, "nombre": n_nom, "precio_pub": n_pre_v, "precio_inv": n_pre_c,
                    "stock": total, "descripcion": json.dumps(st.session_state.temp_matriz),
                    "foto_path": url, "categoria": n_cat, "subcategoria": n_sub
                }).execute()
                st.session_state.temp_matriz = {}
                st.success("Producto Registrado"); st.rerun()

# --- SECCIÓN: CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
    colA, colB = st.columns(2)
    with colA:
        tipo = st.selectbox("Añadir:", ["categoria", "subcategoria"])
        valor = st.text_input("Nombre").upper()
        if st.button("Guardar"):
            supabase.table("configuracion").insert({"tipo": tipo, "valor": valor}).execute()
            st.rerun()
    with colB:
        res_c = supabase.table("configuracion").select("*").execute()
        st.write(pd.DataFrame(res_c.data) if res_c.data else "Vacio")

# --- SECCIÓN: REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        st.dataframe(pd.DataFrame(res_v.data), use_container_width=True)
