import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- CONFIGURACIÓN ---
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Sistema Duo POS", layout="wide", page_icon="⚖️")

# --- LOGIN ---
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if (u == "admin" and p == "admin123") or (u == "equipo" and p == "venta123"):
            st.session_state.auth, st.session_state.role = True, u
            st.rerun()
    st.stop()

# --- MENU ---
menu = st.sidebar.radio("Ir a:", ["Ventas", "Inventario"])

if menu == "Ventas":
    st.header("💰 Ventas")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df = pd.DataFrame(res.data)
        prod_sel = st.selectbox("Producto", df['nombre'])
        data = df[df['nombre'] == prod_sel].iloc[0]
        if data['foto_path']: st.image(data['foto_path'], width=300)
        
        cant = st.number_input("Cantidad", 1, int(data['stock']))
        if st.button("Vender"):
            # Actualizar
            supabase.table("productos").update({"stock": int(data['stock']-cant)}).eq("id", data['id']).execute()
            st.success("¡Venta realizada!")
            st.rerun()

elif menu == "Inventario":
    st.header("📦 Inventario")
    with st.form("nuevo"):
        cod = st.text_input("Código")
        nom = st.text_input("Nombre")
        stk = st.number_input("Stock", 0)
        pub = st.number_input("Precio", 0.0)
        foto = st.camera_input("Foto")
        if st.form_submit_button("Guardar"):
            url = ""
            if foto:
                fname = f"{cod}.jpg"
                supabase.storage.from_("fotos").upload(fname, foto.getvalue(), {"content-type":"image/jpeg", "x-upsert":"true"})
                url = supabase.storage.from_("fotos").get_public_url(fname)
            supabase.table("productos").insert({"codigo":cod, "nombre":nom, "stock":stk, "precio_pub":pub, "precio_inv":0, "foto_path":url}).execute()
            st.success("Guardado")
