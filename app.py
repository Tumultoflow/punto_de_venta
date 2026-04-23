import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from streamlit_zxing import st_zxing  # Escáner estable

# --- 1. CONFIGURACIÓN DE CONEXIÓN ---
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Duo POS", layout="wide", page_icon="⚖️")

# --- 3. AUTENTICACIÓN ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acceso al Sistema Duo")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if u == "admin" and p == "admin123":
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "venta123":
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")
    st.stop()

# --- 4. NAVEGACIÓN ---
role = st.session_state.role
menu_options = ["Ventas", "Inventario"]
if role == "admin": menu_options.append("Reportes")
menu = st.sidebar.radio("Navegación", menu_options)

# --- 5. MÓDULO DE VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    
    with st.expander("📷 Escanear Código de Barras"):
        scan = st_zxing(key='venta_scan')
        barcode = scan['barcode'] if scan else None

    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df = pd.DataFrame(res.data)
        
        # Auto-selección por escáner
        idx = 0
        if barcode:
            match = df[df['codigo'] == barcode]
            if not match.empty:
                idx = int(match.index[0])
                st.success(f"Producto detectado: {barcode}")

        col1, col2 = st.columns(2)
        with col1:
            prod_sel = st.selectbox("Selecciona Producto", df['nombre'], index=idx)
            item = df[df['nombre'] == prod_sel].iloc[0]
            if item['foto_path']: st.image(item['foto_path'], width=350)
        
        with col2:
            st.subheader(item['nombre'])
            st.write(f"Stock: {item['stock']} | Precio Sugerido: ${item['precio_pub']}")
            p_venta = st.number_input("Precio Final ($)", value=float(item['precio_pub']))
            cant = st.number_input("Cantidad", 1, int(item['stock']))
            
            if st.button("Confirmar Venta"):
                ganancia = (p_venta - item['precio_inv']) * cant
                # Actualizar stock
                supabase.table("productos").update({"stock": int(item['stock']-cant)}).eq("id", item['id']).execute()
                # Registrar venta
                supabase.table("ventas").insert({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "producto": item['nombre'],
                    "cantidad": cant,
                    "precio_total": p_venta * cant,
                    "ganancia": ganancia
                }).execute()
                st.success("Venta registrada con éxito")
                st.balloons()
                st.rerun()

# --- 6. MÓDULO DE INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    t1, t2 = st.tabs(["Registrar Producto", "Ver Existencias"])
    
    with t1:
        with st.expander("📷 Escanear Código para Registro"):
            scan_inv = st_zxing(key='inv_scan')
            barcode_inv = scan_inv['barcode'] if scan_inv else ""

        with st.form("form_inv", clear_on_submit=True):
            c1, c2 = st.columns(2)
            cod = c1.text_input("Código / SKU", value=barcode_inv)
            nom = c2.text_input("Nombre del Producto")
            costo = c1.number_input("Costo Inversión", min_value=0.0) if role == "admin" else 0.0
            p_pub = c2.number_input("Precio Venta Sugerido", min_value=0.0)
            stk_ini = st.number_input("Stock Inicial", min_value=0, step=1)
            foto = st.camera_input("Capturar Foto")
            
            if st.form_submit_button("Guardar en Nube"):
                url = ""
                if foto:
                    fname = f"{cod}_{datetime.now().strftime('%M%S')}.jpg"
                    supabase.storage.from_("fotos").upload(fname, foto.getvalue(), {"content-type":"image/jpeg"})
                    url = supabase.storage.from_("fotos").get_public_url(fname)
                
                supabase.table("productos").insert({
                    "codigo": cod, "nombre": nom, "stock": stk_ini,
                    "precio_inv": costo, "precio_pub": p_pub, "foto_path": url
                }).execute()
                st.success("Producto guardado permanentemente")

    with t2:
        res = supabase.table("productos").select("*").execute()
        if res.data:
            df_inv = pd.DataFrame(res.data)
            st.data_editor(
                df_inv[['foto_path', 'codigo', 'nombre', 'stock', 'precio_pub']],
                column_config={"foto_path": st.column_config.ImageColumn("Vista")},
                hide_index=True, use_container_width=True
            )

# --- 7. MÓDULO DE REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes Financieros")
    res_v = supabase.table("ventas").select("*").execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        st.metric("Utilidad Total", f"${df_v['ganancia'].sum():,.2f}")
        st.dataframe(df_v.sort_values(by="fecha", ascending=False), use_container_width=True)

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.auth = False
    st.rerun()
