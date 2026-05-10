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

st.set_page_config(page_title="TUMULTOFLOW", layout="wide")

# --- 2. FUNCIONES ---
def obtener_config(tipo):
    try:
        res = supabase.table("configuracion").select("valor").eq("tipo", tipo).execute()
        return [r['valor'] for r in res.data] if res.data else ["GENERAL"]
    except: return ["GENERAL"]

# --- 3. LOGIN (Simplificado para el ejemplo) ---
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "admin1": 
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
    st.stop()

menu = st.sidebar.radio("Navegación", ["Ventas", "Inventario", "Reportes"])

# --- SECCIÓN: VENTAS (CON SELECCIÓN DE VARIANTE) ---
if menu == "Ventas":
    st.header("💰 Punto de Venta por Variantes")
    res = supabase.table("productos").select("*").execute()
    
    if res.data:
        df_p = pd.DataFrame(res.data)
        busqueda = st.text_input("🔍 Buscar producto...")
        if busqueda:
            df_p = df_p[df_p['nombre'].str.contains(busqueda, case=False) | df_p['codigo'].str.contains(busqueda, case=False)]
        
        if not df_p.empty:
            sel_nom = st.selectbox("Producto", df_p['nombre'].tolist())
            item = df_p[df_p['nombre'] == sel_nom].iloc[0]
            
            # Decodificar el desglose de stock (asumimos que se guarda en 'descripcion' como JSON por ahora)
            try:
                stock_detallado = json.loads(item['descripcion']) if item['descripcion'].startswith('{') else {}
            except:
                stock_detallado = {}

            c1, c2 = st.columns(2)
            with c1:
                if item['foto_path']: st.image(item['foto_path'], width=250)
            
            with c2:
                if stock_detallado:
                    st.write("### Seleccionar Variante")
                    # El usuario elige Color y luego Talla
                    colores_disponibles = list(stock_detallado.keys())
                    v_col = st.selectbox("Color", colores_disponibles)
                    
                    tallas_disponibles = list(stock_detallado[v_col].keys())
                    v_tal = st.selectbox("Talla / Pieza", tallas_disponibles)
                    
                    stock_actual = stock_detallado[v_col][v_tal]
                    st.metric("Stock disponible", stock_actual)
                    
                    v_cant = st.number_input("Cantidad", 1, max(1, stock_actual))
                    v_pre = st.number_input("Precio", value=float(item['precio_pub']))
                    
                    if st.button("🛒 Agregar"):
                        # Aquí guardarías en el carrito (omitiendo por brevedad)
                        st.success(f"Agregado: {item['nombre']} - {v_col} ({v_tal})")
                else:
                    st.warning("Este producto no tiene variantes registradas correctamente.")

# --- SECCIÓN: INVENTARIO (REGISTRO DE MATRIZ) ---
elif menu == "Inventario":
    st.header("📦 Registro de Producto Único con Múltiples Variantes")
    
    with st.expander("➕ Registrar Nuevo Producto con Matriz", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            n_nom = st.text_input("Nombre del Producto (ej: Playera Premium)")
            n_sku = st.text_input("Código Base")
            n_pre = st.number_input("Precio Venta")
        
        with c2:
            st.write("**Definir Variantes (Stock)**")
            # Interfaz simple para agregar variantes
            if 'temp_matriz' not in st.session_state: st.session_state.temp_matriz = {}
            
            m_col = st.text_input("Color", placeholder="Rojo", key="m_col")
            m_tal = st.text_input("Talla / Piezas", placeholder="M", key="m_tal")
            m_cant = st.number_input("Cantidad", min_value=0, key="m_cant")
            
            if st.button("Añadir Variante a la lista"):
                if m_col and m_tal:
                    if m_col not in st.session_state.temp_matriz:
                        st.session_state.temp_matriz[m_col] = {}
                    st.session_state.temp_matriz[m_col][m_tal] = m_cant
                    st.toast("Variante anotada")

            # Mostrar tabla de lo que se va a guardar
            if st.session_state.temp_matriz:
                st.write("Lista actual:")
                for c, tallas in st.session_state.temp_matriz.items():
                    for t, q in tallas.items():
                        st.text(f"• {c} | {t} : {q} pzs")

        if st.button("🚀 GUARDAR PRODUCTO COMPLETO"):
            # Convertimos la matriz a texto JSON para guardarla en la descripción
            matriz_json = json.dumps(st.session_state.temp_matriz)
            total_stock = sum(sum(t.values()) for t in st.session_state.temp_matriz.values())
            
            supabase.table("productos").insert({
                "nombre": n_nom,
                "codigo": n_sku,
                "precio_pub": n_pre,
                "stock": total_stock,
                "descripcion": matriz_json, # Aquí vive la magia
                "color": "MULTIPLE", # Referencia visual
                "piezas": "VARIA"
            }).execute()
            
            st.session_state.temp_matriz = {}
            st.success("Producto guardado con éxito")
            st.rerun()
