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

# --- MANEJO DE SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []

# --- LOGIN ---
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
    st.stop()

# --- NAVEGACIÓN ---
with st.sidebar:
    st.title("⚖️ MENU")
    opc = ["Ventas", "Inventario", "Configuración", "Reportes"]
    menu = st.radio("Ir a:", opc)
    st.divider()
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.auth = False
        st.rerun()

# --- SECCIÓN: VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta Detallado")
    
    # Obtener productos con stock
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    
    if res.data:
        df_p = pd.DataFrame(res.data)
        busq = st.text_input("🔍 Buscar producto...")
        if busq:
            df_p = df_p[df_p['nombre'].str.contains(busq, case=False) | df_p['codigo'].str.contains(busq, case=False)]
        
        if not df_p.empty:
            sel_nom = st.selectbox("Seleccionar Producto", df_p['nombre'].tolist())
            item = df_p[df_p['nombre'] == sel_nom].iloc[0]
            
            col_izq, col_der = st.columns([1, 2])
            
            with col_izq:
                if item.get('foto_path'): st.image(item['foto_path'], width=200)
            
            with col_der:
                # 1. Lógica de Variantes (Color/Talla)
                try:
                    matriz = json.loads(item['descripcion']) if item['descripcion'] and item['descripcion'].startswith('{') else None
                except: matriz = None

                if matriz:
                    v_col = st.selectbox("🎨 Color", list(matriz.keys()))
                    v_tal = st.selectbox("📏 Talla / Pieza", list(matriz[v_col].keys()))
                    stock_disp = matriz[v_col][v_tal]
                    st.metric("Disponible", stock_disp)
                    v_cant = st.number_input("Cantidad", 1, max(1, int(stock_disp)))
                else:
                    st.warning("Este producto no tiene matriz de variantes configurada.")
                    v_col, v_tal = "N/A", "N/A"
                    v_cant = st.number_input("Cantidad", 1, int(item['stock']))

                v_pre = st.number_input("Precio Unitario", value=float(item['precio_pub']))
                v_fecha = datetime.now(ZONA_LOCAL).strftime("%d/%m/%Y %H:%M")
                v_vendedor = st.session_state.role.upper()

                if st.button("➕ Agregar al Carrito", use_container_width=True):
                    st.session_state.carrito.append({
                        "id": item['id'],
                        "Producto": item['nombre'],
                        "Cantidad": v_cant,
                        "Precio": v_pre,
                        "Color": v_col,
                        "Talla": v_tal,
                        "Fecha": v_fecha,
                        "Vendedor": v_vendedor,
                        "es_matriz": bool(matriz),
                        "precio_inv": float(item['precio_inv']),
                        "codigo": item['codigo']
                    })
                    st.toast(f"Agregado: {item['nombre']}")

        # --- MOSTRAR CARRITO CON LAS 6 COLUMNAS SOLICITADAS ---
        if st.session_state.carrito:
            st.divider()
            st.subheader("🛒 Carrito de Venta")
            
            # Convertimos a DataFrame para mostrarlo como tabla limpia
            df_carrito = pd.DataFrame(st.session_state.carrito)
            
            # Mostramos exactamente lo que pediste: Cantidad, Precio, Color, Talla, Fecha, Vendedor
            st.table(df_carrito[["Producto", "Cantidad", "Precio", "Color", "Talla", "Fecha", "Vendedor"]])
            
            total_venta = sum(item['Cantidad'] * item['Precio'] for item in st.session_state.carrito)
            st.write(f"### Total a pagar: ${total_venta:,.2f}")

            if st.button("🚀 FINALIZAR VENTA Y DESCONTAR STOCK", type="primary", use_container_width=True):
                for p in st.session_state.carrito:
                    # Actualización de Stock en DB
                    prod_db = supabase.table("productos").select("*").eq("id", p['id']).execute().data[0]
                    nuevo_total = prod_db['stock'] - p['Cantidad']
                    
                    if p['es_matriz']:
                        m_act = json.loads(prod_db['descripcion'])
                        m_act[p['Color']][p['Talla']] -= p['Cantidad']
                        supabase.table("productos").update({"stock": nuevo_total, "descripcion": json.dumps(m_act)}).eq("id", p['id']).execute()
                    else:
                        supabase.table("productos").update({"stock": nuevo_total}).eq("id", p['id']).execute()
                    
                    # Registro en tabla Ventas (Guardando metadatos para reportes)
                    supabase.table("ventas").insert({
                        "producto": p['Producto'],
                        "codigo_prod": p['codigo'],
                        "cantidad": p['Cantidad'],
                        "precio_total": p['Precio'] * p['Cantidad'],
                        "vendedor": p['Vendedor'],
                        "fecha_venta": datetime.now(ZONA_LOCAL).isoformat(),
                        "color": json.dumps({"col": p['Color'], "tal": p['Talla']}) # Meta-data para anular
                    }).execute()
                
                st.session_state.carrito = []
                st.success("Venta realizada con éxito")
                st.rerun()
    else:
        st.info("No hay productos con stock disponible.")

# (El resto de las secciones: Inventario, Configuración y Reportes se mantienen igual que en la versión anterior)
