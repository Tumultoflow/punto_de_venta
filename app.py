import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- 1. CONEXIÓN ---
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Duo POS", layout="wide")

if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "admin123":
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "venta123":
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
    st.stop()

role = st.session_state.role
menu = st.sidebar.radio("Menú", ["Ventas", "Inventario", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])

# --- VENTAS (Con visualización de fecha) ---
if menu == "Ventas":
    st.header("💰 Nueva Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df = pd.DataFrame(res.data)
        prod = st.selectbox("Seleccionar Producto", df['nombre'])
        item = df[df['nombre'] == prod].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            if item.get('foto_path'): st.image(item['foto_path'], width=300)
            st.write(f"**Descripción:** {item.get('descripcion', 'N/A')}")
        
        with col2:
            st.subheader(f"Vendiendo: {item['nombre']}")
            
            # --- APARTADO DE FECHA VISIBLE ---
            # Mostramos la fecha y hora actual que se guardará
            fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.info(f"📅 **Fecha de Venta:** {fecha_actual}")
            
            precio_v = st.number_input("Precio de Venta ($)", value=float(item['precio_pub']))
            cant = st.number_input("Cantidad", 1, int(item['stock']))
            
            if st.button("🚀 Confirmar y Registrar Venta"):
                ganancia = (precio_v - item['precio_inv']) * cant
                
                # 1. Actualizar Stock en la tabla productos
                supabase.table("productos").update({"stock": int(item['stock']-cant)}).eq("id", item['id']).execute()
                
                # 2. Insertar en la tabla ventas incluyendo la fecha
                supabase.table("ventas").insert({
                    "fecha_venta": fecha_actual,
                    "producto": item['nombre'],
                    "cantidad": cant,
                    "precio_total": precio_v * cant,
                    "ganancia": ganancia if role == "admin" else 0
                }).execute()
                
                st.success(f"✅ Venta exitosa registrada el {fecha_actual}")
                st.rerun()

# --- INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    t1, t2 = st.tabs(["Registro", "Existencias"])
    
    if role == "admin":
        with t1:
            with st.form("f_reg", clear_on_submit=True):
                c1, c2 = st.columns(2)
                cod = c1.text_input("Código")
                nom = c2.text_input("Nombre")
                inv = c1.number_input("Inversión", 0.0)
                pub = c2.number_input("Público", 0.0)
                stk = c1.number_input("Stock", 0)
                f_ing = st.date_input("Fecha de Ingreso", datetime.now())
                desc = st.text_area("Descripción")
                foto = st.camera_input("Foto")
                if st.form_submit_button("Guardar Producto"):
                    url = ""
                    if foto:
                        fname = f"{cod}.jpg"
                        supabase.storage.from_("fotos").upload(fname, foto.getvalue(), {"content-type":"image/jpeg", "x-upsert":"true"})
                        url = supabase.storage.from_("fotos").get_public_url(fname)
                    supabase.table("productos").insert({
                        "codigo": cod, "nombre": nom, "precio_inv": inv, "precio_pub": pub,
                        "stock": stk, "descripcion": desc, "fecha_ingreso": str(f_ing), "foto_path": url
                    }).execute()
                    st.success("Registrado en inventario")

    with t2:
        res_i = supabase.table("productos").select("*").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            # Orden: Foto, Código, Nombre, Stock, Venta, Ingreso, Descripción
            cols = ['foto_path', 'codigo', 'nombre', 'stock', 'precio_pub', 'fecha_ingreso', 'descripcion']
            if role == "admin": cols.insert(5, 'precio_inv')
            
            st.data_editor(
                df_i[[c for c in cols if c in df_i.columns]],
                column_config={"foto_path": st.column_config.ImageColumn("Imagen")},
                hide_index=True, use_container_width=True, disabled=True if role == "equipo" else False
            )

# --- REPORTES (Aquí es donde puedes ver todas las fechas de venta guardadas) ---
elif menu == "Reportes":
    st.header("📊 Historial de Ventas")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        # Aseguramos que la columna fecha_venta sea la primera en verse
        if 'fecha_venta' in df_v.columns:
            columnas = ['fecha_venta', 'producto', 'cantidad', 'precio_total']
            if role == "admin": columnas.append('ganancia')
            st.dataframe(df_v[columnas], use_container_width=True)
