Para que tu sistema de Duo Legal tenga un control total sobre el tiempo, necesitamos que la base de datos registre automáticamente el momento exacto de cada movimiento.

Aquí tienes la actualización final para app.py que incluye el registro de fechas tanto para la entrada de mercancía (cuando el admin registra el producto) como para la salida por venta (cuando el equipo realiza el cobro).

Código de app.py con Fechas Automáticas
Python

import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- 1. CONEXIÓN ---
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Sistema Duo POS", layout="wide", page_icon="⚖️")

# --- 2. SISTEMA DE ACCESO ---
if "auth" not in st.session_state: st.session_state.auth = False

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

# --- 3. BARRA LATERAL ---
role = st.session_state.role
st.sidebar.title(f"Sesión: {role.capitalize()}")
menu = st.sidebar.radio("Navegación", ["Ventas", "Inventario", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state.auth = False
    st.rerun()

# --- 4. MÓDULO DE VENTAS (Con Fecha de Venta) ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    
    if res.data:
        df = pd.DataFrame(res.data)
        prod_sel = st.selectbox("Producto a vender", df['nombre'])
        item = df[df['nombre'] == prod_sel].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            if item.get('foto_path'): st.image(item['foto_path'], width=300)
        
        with col2:
            st.subheader(item['nombre'])
            p_final = st.number_input("Precio de Venta Actual ($)", value=float(item['precio_pub']))
            cant = st.number_input("Cantidad", 1, int(item['stock']))
            
            if st.button("Confirmar Venta"):
                fecha_v = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ganancia = (p_final - item['precio_inv']) * cant
                
                # Actualizar stock
                supabase.table("productos").update({"stock": int(item['stock']-cant)}).eq("id", item['id']).execute()
                
                # REGISTRO DE VENTA CON FECHA
                supabase.table("ventas").insert({
                    "fecha_venta": fecha_v,
                    "producto": item['nombre'],
                    "cantidad": cant,
                    "precio_total": p_final * cant,
                    "ganancia": ganancia if role == "admin" else 0
                }).execute()
                
                st.success(f"Venta registrada el {fecha_v}")
                st.rerun()

# --- 5. MÓDULO DE INVENTARIO (Con Fecha de Ingreso) ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    t_list = ["Existencias"]
    if role == "admin": t_list.insert(0, "Añadir Producto")
    tabs = st.tabs(t_list)
    
    if role == "admin":
        with tabs[0]:
            with st.form("nuevo_p", clear_on_submit=True):
                c1, c2 = st.columns(2)
                cod = c1.text_input("Código")
                nom = c2.text_input("Nombre")
                inv = c1.number_input("Costo (Inversión)", min_value=0.0)
                pub = c2.number_input("Precio Público", min_value=0.0)
                stk = c1.number_input("Stock Inicial", min_value=0)
                # EL ADMIN ELIGE O SE DEJA LA DE HOY
                f_ingreso = st.date_input("Fecha de Ingreso", datetime.now())
                desc = st.text_area("Descripción")
                foto = st.camera_input("Foto")
                
                if st.form_submit_button("Registrar"):
                    url = ""
                    if foto:
                        fname = f"{cod}.jpg"
                        supabase.storage.from_("fotos").upload(fname, foto.getvalue(), {"content-type":"image/jpeg", "x-upsert":"true"})
                        url = supabase.storage.from_("fotos").get_public_url(fname)
                    
                    # REGISTRO DE PRODUCTO CON FECHA DE INGRESO
                    supabase.table("productos").insert({
                        "codigo": cod, "nombre": nom, "descripcion": desc,
                        "precio_inv": inv, "precio_pub": pub, "stock": stk, 
                        "fecha_ingreso": str(f_ingreso), "foto_path": url
                    }).execute()
                    st.success("Producto guardado correctamente.")

    # PESTAÑA EXISTENCIAS
    idx = 1 if role == "admin" else 0
    with tabs[idx]:
        res_i = supabase.table("productos").select("*").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            orden = ['foto_path', 'codigo', 'nombre', 'stock', 'precio_pub', 'fecha_ingreso', 'descripcion']
            if role == "admin": orden.insert(5, 'precio_inv')
            
            st.data_editor(
                df_i[[c for c in orden if c in df_i.columns]],
                column_config={"foto_path": st.column_config.ImageColumn("Imagen")},
                hide_index=True, use_container_width=True, disabled=True if role == "equipo" else False
            )

# --- 6. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Historial de Ventas")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        st.dataframe(pd.DataFrame(res_v.data), use_container_width=True)
