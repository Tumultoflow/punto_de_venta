import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- 1. CONFIGURACIÓN DE CONEXIÓN ---
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Sistema Duo POS", layout="wide", page_icon="⚖️")

# --- 2. SISTEMA DE ACCESO ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acceso al Sistema")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if u == "admin" and p == "admin123":
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "venta123":
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
    st.stop()

role = st.session_state.role
menu = st.sidebar.radio("Navegación", ["Ventas", "Inventario", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])

# --- 3. MÓDULO DE VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    
    if res.data:
        df = pd.DataFrame(res.data)
        prod_sel = st.selectbox("Buscar Producto", df['nombre'])
        item = df[df['nombre'] == prod_sel].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            if item['foto_path']: st.image(item['foto_path'], width=300)
            st.write(f"**Descripción:** {item.get('descripcion', 'N/A')}")
        
        with col2:
            st.subheader(item['nombre'])
            # EL EQUIPO PUEDE CAMBIAR EL PRECIO AQUÍ
            p_venta = st.number_input("Precio de Venta ($)", value=float(item['precio_pub']))
            cant = st.number_input("Cantidad", 1, int(item['stock']))
            
            if st.button("Confirmar Venta"):
                ganancia = (p_venta - item['precio_inv']) * cant
                supabase.table("productos").update({"stock": int(item['stock']-cant)}).eq("id", item['id']).execute()
                supabase.table("ventas").insert({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "producto": item['nombre'],
                    "cantidad": cant,
                    "precio_total": p_venta * cant,
                    "ganancia": ganancia if role == "admin" else 0 # Solo admin trackea ganancia real
                }).execute()
                st.success("Venta realizada correctamente")
                st.rerun()

# --- 4. MÓDULO DE INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario Completo")
    
    tabs = ["Existencias"]
    if role == "admin":
        tabs.insert(0, "Añadir Producto")
    
    selected_tabs = st.tabs(tabs)
    
    if role == "admin":
        with selected_tabs[0]:
            # ... (tu código de formulario de registro se queda igual) ...
            st.info("Asegúrate de llenar todos los campos")

    idx_existencias = 1 if role == "admin" else 0
    with selected_tabs[idx_existencias]:
        res_i = supabase.table("productos").select("*").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            
            # --- CORRECCIÓN DE KEYERROR ---
            # Solo mostramos las columnas que REALMENTE existen en tu Supabase
            cols_deseadas = ['foto_path', 'codigo', 'nombre', 'descripcion', 'precio_inv', 'precio_pub', 'stock']
            if role == "equipo":
                if 'precio_inv' in cols_deseadas: cols_deseadas.remove('precio_inv')
            
            # Filtramos para evitar el error si alguna columna no ha sido creada en Supabase
            cols_finales = [c for c in cols_deseadas if c in df_i.columns]
            
            st.data_editor(
                df_i[cols_finales],
                column_config={
                    "foto_path": st.column_config.ImageColumn("Imagen"),
                    "precio_inv": "Costo",
                    "precio_pub": "Venta"
                },
                hide_index=True,
                use_container_width=True,
                disabled=True if role == "equipo" else False
            )
