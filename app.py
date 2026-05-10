import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import pytz
import json

# --- 1. CONFIGURACIÓN ---
ZONA_LOCAL = pytz.timezone('America/Mexico_City')
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="TUMULTOFLOW", layout="wide", page_icon="⚖️")

# --- 2. SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []
if "temp_matriz" not in st.session_state: st.session_state.temp_matriz = {}

# --- LOGIN ---
if not st.session_state.auth:
    st.title("⚖️ Acceso TumultoFlow")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if u == "admin" and p == "admin1": 
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
    st.stop()

menu = st.sidebar.radio("MENÚ", ["Ventas", "Inventario", "Reportes / Anular"])

# --- SECCIÓN VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta (Variantes)")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    
    if res.data:
        df_p = pd.DataFrame(res.data)
        busq = st.text_input("🔍 Buscar por Nombre o Código...")
        if busq:
            df_p = df_p[df_p['nombre'].str.contains(busq, case=False) | df_p['codigo'].str.contains(busq, case=False)]
        
        if not df_p.empty:
            sel_nom = st.selectbox("Elegir Producto", df_p['nombre'].tolist())
            item = df_p[df_p['nombre'] == sel_nom].iloc[0]
            
            c1, c2 = st.columns(2)
            with c1:
                if item['foto_path']: st.image(item['foto_path'], width=250)
            
            with c2:
                try:
                    # Intentar cargar la matriz (Color -> Talla -> Stock)
                    matriz = json.loads(item['descripcion']) if item['descripcion'].startswith('{') else None
                except: matriz = None

                if matriz:
                    v_col = st.selectbox("Elegir Color", list(matriz.keys()))
                    v_tal = st.selectbox("Elegir Talla / Piezas", list(matriz[v_col].keys()))
                    st.metric("Disponible", matriz[v_col][v_tal])
                    
                    v_cant = st.number_input("Cantidad", 1, max(1, int(matriz[v_col][v_tal])))
                    nombre_venta = f"{item['nombre']} [{v_col} - {v_tal}]"
                else:
                    v_cant = st.number_input("Cantidad", 1, int(item['stock']))
                    nombre_venta = item['nombre']
                    v_col, v_tal = None, None

                if st.button("➕ Agregar al Carrito"):
                    st.session_state.carrito.append({
                        "id": item['id'], "nombre": nombre_venta, "cantidad": v_cant,
                        "precio": float(item['precio_pub']), "codigo": item['codigo'],
                        "es_matriz": bool(matriz), "color": v_col, "talla": v_tal
                    })
                    st.toast("Agregado")

        if st.session_state.carrito:
            st.subheader("🛒 Resumen")
            df_car = pd.DataFrame(st.session_state.carrito)
            st.table(df_car[['nombre', 'cantidad', 'precio']])
            
            if st.button("🚀 FINALIZAR VENTA", type="primary"):
                for p in st.session_state.carrito:
                    # 1. Obtener producto actual para descontar stock
                    prod = supabase.table("productos").select("*").eq("id", p['id']).execute().data[0]
                    nuevo_stock_total = prod['stock'] - p['cantidad']
                    
                    if p['es_matriz']:
                        m_db = json.loads(prod['descripcion'])
                        m_db[p['color']][p['talla']] -= p['cantidad']
                        supabase.table("productos").update({
                            "stock": nuevo_stock_total, 
                            "descripcion": json.dumps(m_db)
                        }).eq("id", p['id']).execute()
                    else:
                        supabase.table("productos").update({"stock": nuevo_stock_total}).eq("id", p['id']).execute()
                    
                    # 2. Registrar venta con detalle para poder cancelar después
                    detalle_json = json.dumps({"es_matriz": p['es_matriz'], "color": p['color'], "talla": p['talla']})
                    supabase.table("ventas").insert({
                        "producto": p['nombre'], "codigo_prod": p['codigo'], 
                        "cantidad": p['cantidad'], "precio_total": p['precio'] * p['cantidad'],
                        "vendedor": "ADMIN", "fecha_venta": datetime.now(ZONA_LOCAL).isoformat(),
                        "ganancia": 0, # Opcional: calcular con precio_inv
                        "color": detalle_json # Guardamos aquí los metadatos para anular
                    }).execute()
                
                st.session_state.carrito = []
                st.success("Venta realizada")
                st.rerun()

# --- SECCIÓN INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Registro de Producto Único con Variantes")
    t1, t2 = st.tabs(["📋 Lista de Inventario", "🆕 Registrar Matriz"])
    
    with t1:
        res = supabase.table("productos").select("*").execute()
        if res.data:
            df_inv = pd.DataFrame(res.data)
            st.dataframe(df_inv[['codigo', 'nombre', 'stock', 'precio_pub']])
            # Aquí podrías añadir botones de edición si lo deseas
    
    with t2:
        c1, c2 = st.columns(2)
        with c1:
            n_nom = st.text_input("Nombre del Producto")
            n_sku = st.text_input("Código Base")
            n_pre = st.number_input("Precio Venta")
        with c2:
            st.write("**Definir Variantes**")
            m_col = st.text_input("Color (ej: Rojo)", key="m_c")
            m_tal = st.text_input("Talla / Piezas (ej: M)", key="m_t")
            m_can = st.number_input("Cantidad inicial", 0, key="m_q")
            if st.button("Añadir a la lista"):
                if m_col and m_tal:
                    if m_col not in st.session_state.temp_matriz: st.session_state.temp_matriz[m_col] = {}
                    st.session_state.temp_matriz[m_col][m_tal] = m_can
            st.write(st.session_state.temp_matriz)
        
        if st.button("🚀 Guardar Producto"):
            total = sum(sum(v.values()) for v in st.session_state.temp_matriz.values())
            supabase.table("productos").insert({
                "nombre": n_nom, "codigo": n_sku, "precio_pub": n_pre,
                "stock": total, "descripcion": json.dumps(st.session_state.temp_matriz),
                "precio_inv": 0, "color": "MATRIZ", "piezas": "MATRIZ"
            }).execute()
            st.session_state.temp_matriz = {}
            st.success("Guardado"); st.rerun()

# --- SECCIÓN REPORTES Y ANULACIÓN ---
elif menu == "Reportes / Anular":
    st.header("📊 Historial y Cancelaciones")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        st.dataframe(df_v[['id', 'fecha_venta', 'producto', 'cantidad', 'precio_total']], use_container_width=True)
        
        st.divider()
        id_anul = st.selectbox("Seleccionar ID de venta para CANCELAR", df_v['id'].tolist())
        
        if st.button("❌ ANULAR VENTA Y DEVOLVER STOCK"):
            v_data = df_v[df_v['id'] == id_anul].iloc[0]
            # 1. Recuperar metadatos (color/talla) del campo 'color' que usamos como JSON
            try:
                meta = json.loads(v_data['color'])
            except: meta = {"es_matriz": False}

            # 2. Devolver stock al producto
            p_db = supabase.table("productos").select("*").eq("codigo", v_data['codigo_prod']).execute().data[0]
            nuevo_total = p_db['stock'] + v_data['cantidad']
            
            if meta.get('es_matriz'):
                m_act = json.loads(p_db['descripcion'])
                # Devolver a la variante exacta
                m_act[meta['color']][meta['talla']] += v_data['cantidad']
                supabase.table("productos").update({
                    "stock": nuevo_total, "descripcion": json.dumps(m_act)
                }).eq("id", p_db['id']).execute()
            else:
                supabase.table("productos").update({"stock": nuevo_total}).eq("id", p_db['id']).execute()
            
            # 3. Eliminar registro de venta
            supabase.table("ventas").delete().eq("id", id_anul).execute()
            st.success("Venta anulada con éxito. Stock restaurado.")
            st.rerun()
