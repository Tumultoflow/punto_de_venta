import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import pytz
import json

# --- CONFIGURACIÓN ---
ZONA_LOCAL = pytz.timezone('America/Mexico_City')
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "tu_clave_aqui" 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- MANEJO DE SESIÓN ---
if "carrito" not in st.session_state: 
    st.session_state.carrito = []

# --- SECCIÓN: VENTAS ---
st.header("💰 Punto de Venta")

# 1. Búsqueda y Selección
res = supabase.table("productos").select("*").gt("stock", 0).execute()
if res.data:
    df_p = pd.DataFrame(res.data)
    busq = st.text_input("🔍 Buscar producto...")
    if busq:
        df_p = df_p[df_p['nombre'].str.contains(busq, case=False) | df_p['codigo'].str.contains(busq, case=False)]
    
    if not df_p.empty:
        sel_nom = st.selectbox("Seleccionar Producto", df_p['nombre'].tolist())
        item = df_p[df_p['nombre'] == sel_nom].iloc[0]
        
        c1, c2 = st.columns([1, 2])
        with c1:
            if item.get('foto_path'): st.image(item['foto_path'], width=150)
        
        with c2:
            try:
                matriz = json.loads(item['descripcion']) if item['descripcion'] and item['descripcion'].startswith('{') else None
            except: matriz = None

            if matriz:
                v_col = st.selectbox("Color", list(matriz.keys()))
                v_tal = st.selectbox("Talla / Pieza", list(matriz[v_col].keys()))
                v_cant = st.number_input("Cantidad", 1, int(matriz[v_col][v_tal]))
            else:
                v_col, v_tal = "N/A", "N/A"
                v_cant = st.number_input("Cantidad", 1, int(item['stock']))

            v_pre = st.number_input("Precio", value=float(item['precio_pub']))
            
            if st.button("➕ Agregar a la venta"):
                st.session_state.carrito.append({
                    "temp_id": datetime.now().timestamp(), # ID temporal para poder borrarlo
                    "id": item['id'],
                    "Producto": item['nombre'],
                    "Cantidad": v_cant,
                    "Precio": v_pre,
                    "Color": v_col,
                    "Talla": v_tal,
                    "Fecha": datetime.now(ZONA_LOCAL).strftime("%d/%m/%Y %H:%M"),
                    "Vendedor": st.session_state.role.upper(),
                    "es_matriz": bool(matriz),
                    "codigo": item['codigo']
                })
                st.rerun()

# --- MOSTRAR Y CANCELAR VENTA ---
if st.session_state.carrito:
    st.divider()
    st.subheader("🛒 Artículos en la venta actual")
    
    # Creamos una lista para mostrar con opción de eliminar individual
    for i, p in enumerate(st.session_state.carrito):
        col_info, col_del = st.columns([5, 1])
        col_info.write(f"**{p['Cantidad']}x {p['Producto']}** ({p['Color']} - {p['Talla']}) - ${p['Precio'] * p['Cantidad']:,.2f}")
        # BOTÓN PARA CANCELAR UN SOLO ARTÍCULO
        if col_del.button("❌", key=f"del_{p['temp_id']}"):
            st.session_state.carrito.pop(i)
            st.rerun()

    st.divider()
    c_btn1, c_btn2 = st.columns(2)
    
    # BOTÓN PARA CANCELAR TODA LA VENTA
    if c_btn1.button("🗑️ VACÍAR CARRITO (CANCELAR TODO)", use_container_width=True):
        st.session_state.carrito = []
        st.toast("Venta cancelada")
        st.rerun()

    if c_btn2.button("🚀 FINALIZAR Y COBRAR", type="primary", use_container_width=True):
        # ... (Aquí va la lógica de guardar en base de datos que ya teníamos)
        st.success("Venta finalizada")
        st.session_state.carrito = []
        st.rerun()
