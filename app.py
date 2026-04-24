import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- 1. CONEXIÓN ---
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="TUMULTOFLOW", layout="wide")

if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "admin1":
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "equipo1":
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
    st.stop()

role = st.session_state.role
menu = st.sidebar.radio("Menú", ["Ventas", "Inventario", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])

# --- VENTAS (Aquí se registra la fecha) ---
if menu == "Ventas":
    st.header("💰 Nueva Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df = pd.DataFrame(res.data)
        prod = st.selectbox("Producto", df['nombre'])
        item = df[df['nombre'] == prod].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            if item.get('foto_path'): st.image(item['foto_path'], width=300)
        
        with col2:
            precio_v = st.number_input("Precio ($)", value=float(item['precio_pub']))
            cant = st.number_input("Cantidad", 1, int(item['stock']))
            
            if st.button("Confirmar Venta"):
                # CAPTURA DE FECHA ACTUAL
                ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ganancia = (precio_v - item['precio_inv']) * cant
                
                # 1. Descontar Stock
                supabase.table("productos").update({"stock": int(item['stock']-cant)}).eq("id", item['id']).execute()
                
                # 2. Guardar Venta con fecha_venta
                supabase.table("ventas").insert({
                    "fecha_venta": ahora,
                    "producto": item['nombre'],
                    "cantidad": cant,
                    "precio_total": precio_v * cant,
                    "ganancia": ganancia if role == "admin" else 0
                }).execute()
                
                st.success(f"Venta guardada: {ahora}")
                st.rerun()

# --- INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    t1, t2 = st.tabs(["Registro", "Existencias"])
    
    if role == "admin":
        with t1:
            with st.form("f_reg", clear_on_submit=True):
                cod = st.text_input("Código")
                nom = st.text_input("Nombre")
                inv = st.number_input("Inversión", 0.0)
                pub = st.number_input("Público", 0.0)
                stk = st.number_input("Stock", 0)
                f_ing = st.date_input("Fecha de Ingreso", datetime.now())
                desc = st.text_area("Descripción")
                foto = st.camera_input("Foto")
                if st.form_submit_button("Guardar"):
                    url = ""
                    if foto:
                        fname = f"{cod}.jpg"
                        supabase.storage.from_("fotos").upload(fname, foto.getvalue(), {"content-type":"image/jpeg", "x-upsert":"true"})
                        url = supabase.storage.from_("fotos").get_public_url(fname)
                    supabase.table("productos").insert({
                        "codigo": cod, "nombre": nom, "precio_inv": inv, "precio_pub": pub,
                        "stock": stk, "descripcion": desc, "fecha_ingreso": str(f_ing), "foto_path": url
                    }).execute()
                    st.success("Registrado")

    with t2:
        res_i = supabase.table("productos").select("*").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            # Orden de columnas que pediste
            cols = ['foto_path', 'codigo', 'nombre', 'stock', 'precio_pub', 'fecha_ingreso', 'descripcion']
            if role == "admin": cols.insert(5, 'precio_inv')
            st.data_editor(
                df_i[[c for c in cols if c in df_i.columns]],
                column_config={"foto_path": st.column_config.ImageColumn("Imagen")},
                hide_index=True, use_container_width=True, disabled=True if role == "equipo" else False
            )

# --- REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reporte de Ventas")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        st.dataframe(pd.DataFrame(res_v.data), use_container_width=True)
