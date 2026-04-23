import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from streamlit_barcode_scanner import st_barcode_scanner # Nueva librería

# --- 1. CONFIGURACIÓN DE CONEXIÓN ---
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Duo POS", layout="wide", page_icon="⚖️")

# --- LOGIN (Simplificado para el ejemplo) ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Acceso Duo")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if u == "admin" and p == "admin123":
            st.session_state.authenticated, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "venta123":
            st.session_state.authenticated, st.session_state.role = True, "equipo"
            st.rerun()
    st.stop()

role = st.session_state.role
menu = st.sidebar.radio("Ir a:", ["Ventas", "Inventario", "Reportes"] if role=="admin" else ["Ventas", "Inventario"])

# --- 4. MÓDULO DE VENTAS (Con Escáner) ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    
    with st.expander("📷 Escanear Código para Venta"):
        barcode_venta = st_barcode_scanner()
    
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    productos = res.data
    
    if productos:
        df_prod = pd.DataFrame(productos)
        
        # Si escaneó algo, intentamos pre-seleccionar el producto
        indice_default = 0
        if barcode_venta:
            match = df_prod[df_prod['codigo'] == barcode_venta]
            if not match.empty:
                indice_default = int(match.index[0])
                st.success(f"Código detectado: {barcode_venta}")

        col1, col2 = st.columns([1, 1])
        with col1:
            opcion_prod = st.selectbox("Producto", df_prod['nombre'], index=indice_default)
            prod_data = df_prod[df_prod['nombre'] == opcion_prod].iloc[0]
            if prod_data['foto_path']: st.image(prod_data['foto_path'], width=300)

        with col2:
            st.subheader(prod_data['nombre'])
            precio_final = st.number_input("Precio ($)", value=float(prod_data['precio_pub']))
            cant = st.number_input("Cantidad", min_value=1, max_value=int(prod_data['stock']), step=1)
            if st.button("Confirmar Venta"):
                ganancia = (precio_final - prod_data['precio_inv']) * cant
                supabase.table("productos").update({"stock": int(prod_data['stock'] - cant)}).eq("id", prod_data['id']).execute()
                supabase.table("ventas").insert({"fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "producto": prod_data['nombre'], "cantidad": int(cant), "precio_total": float(precio_final * cant), "ganancia": float(ganancia)}).execute()
                st.success("Venta Exitosa")
                st.rerun()

# --- 5. MÓDULO DE INVENTARIO (Con Escáner para Registro) ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    t1, t2 = st.tabs(["Registrar Nuevo", "Existencias"])
    
    with t1:
        st.subheader("Escanear Código de Barras")
        # El escáner aparece aquí arriba
        barcode_nuevo = st_barcode_scanner()
        
        with st.form("registro_nube", clear_on_submit=True):
            c1, c2 = st.columns(2)
            # El código se llena solo si el escáner detecta algo
            cod = c1.text_input("Código / SKU", value=barcode_nuevo if barcode_nuevo else "")
            nom = c2.text_input("Nombre del Producto")
            inv = c1.number_input("Costo Inversión", min_value=0.0) if role == "admin" else 0.0
            pub = c2.number_input("Precio Venta", min_value=0.0)
            stk = st.number_input("Cantidad Inicial", min_value=0, step=1)
            foto = st.camera_input("Capturar Foto")
            
            if st.form_submit_button("Guardar"):
                try:
                    url_foto = ""
                    if foto:
                        nombre_img = f"{cod}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
                        supabase.storage.from_("fotos").upload(nombre_img, foto.getvalue(), {"content-type": "image/jpeg"})
                        url_foto = supabase.storage.from_("fotos").get_public_url(nombre_img)
                    
                    supabase.table("productos").insert({"codigo": cod, "nombre": nom, "stock": stk, "precio_inv": inv, "precio_pub": pub, "foto_path": url_foto}).execute()
                    st.success("✅ Guardado")
                except Exception as e: st.error(f"Error: {e}")

    with t2:
        res = supabase.table("productos").select("*").execute()
        if res.data:
            df_inv = pd.DataFrame(res.data)
            st.data_editor(df_inv[['foto_path', 'codigo', 'nombre', 'stock', 'precio_pub']], column_config={"foto_path": st.column_config.ImageColumn("Imagen")}, hide_index=True)
