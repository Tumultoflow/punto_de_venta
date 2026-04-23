import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- 1. CONFIGURACIÓN DE CONEXIÓN ---
# Sustituye con tus credenciales de Supabase
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"

# Inicializar cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Duo POS", layout="wide", page_icon="📦")

# --- 3. SISTEMA DE AUTENTICACIÓN ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Acceso al Sistema Duo")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if u == "admin" and p == "admin123":
            st.session_state.authenticated, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "venta123":
            st.session_state.authenticated, st.session_state.role = True, "equipo"
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.stop()

# --- 4. NAVEGACIÓN ---
role = st.session_state.role
st.sidebar.title(f"Sesión: {role.upper()}")
opciones = ["Ventas", "Inventario"]
if role == "admin":
    opciones.append("Reportes")

menu = st.sidebar.radio("Ir a:", opciones)

# --- 5. MÓDULO DE VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    
    # Obtener productos con stock de Supabase
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    productos = res.data
    
    if productos:
        df_prod = pd.DataFrame(productos)
        col1, col2 = st.columns([1, 1])
        
        with col1:
            opcion_prod = st.selectbox("Selecciona Producto", df_prod['nombre'])
            prod_data = df_prod[df_prod['nombre'] == opcion_prod].iloc[0]
            if prod_data['foto_path']:
                st.image(prod_data['foto_path'], width=350)
            else:
                st.info("Sin imagen")

        with col2:
            st.subheader(prod_data['nombre'])
            st.write(f"**Código:** {prod_data['codigo']}")
            st.write(f"**Stock:** {prod_data['stock']}")
            
            precio_final = st.number_input("Precio de Venta Actual ($)", value=float(prod_data['precio_pub']))
            cant = st.number_input("Cantidad a vender", min_value=1, max_value=int(prod_data['stock']), step=1)
            
            if st.button("Confirmar Venta"):
                # Cálculos
                ganancia_u = precio_final - prod_data['precio_inv']
                ganancia_total = ganancia_u * cant
                nuevo_stock = int(prod_data['stock'] - cant)
                
                # Actualizar Stock
                supabase.table("productos").update({"stock": nuevo_stock}).eq("id", prod_data['id']).execute()
                
                # Registrar Venta
                venta = {
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "producto": prod_data['nombre'],
                    "cantidad": int(cant),
                    "precio_total": float(precio_final * cant),
                    "ganancia": float(ganancia_total)
                }
                supabase.table("ventas").insert(venta).execute()
                
                st.success("✅ Venta registrada y stock actualizado")
                st.balloons()
                st.rerun()
    else:
        st.warning("No hay productos disponibles en el inventario.")

# --- 6. MÓDULO DE INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Mercancía")
    t1, t2 = st.tabs(["Registrar/Actualizar", "Existencias"])
    
    with t1:
        st.subheader("Alta de Producto")
        with st.form("registro_nube", clear_on_submit=True):
            c1, c2 = st.columns(2)
            cod = c1.text_input("Código / SKU")
            nom = c2.text_input("Nombre del Producto")
            inv = c1.number_input("Precio de Inversión (Costo)", min_value=0.0) if role == "admin" else 0.0
            pub = c2.number_input("Precio de Venta Sugerido", min_value=0.0)
            stk = st.number_input("Cantidad Inicial", min_value=0, step=1)
            foto = st.camera_input("Capturar Foto")
            
            if st.form_submit_button("Guardar en Nube"):
                try:
                    url_foto = ""
                    if foto:
                        nombre_img = f"{cod}.jpg"
                        # Subir a Storage
                        supabase.storage.from_("fotos").upload(
                            path=nombre_img,
                            file=foto.getvalue(),
                            file_options={"content-type": "image/jpeg", "x-upsert": "true"}
                        )
                        url_foto = supabase.storage.from_("fotos").get_public_url(nombre_img)
                    
                    # Insertar en tabla
                    nuevo_p = {
                        "codigo": cod, "nombre": nom, "stock": stk,
                        "precio_inv": inv, "precio_pub": pub, "foto_path": url_foto
                    }
                    supabase.table("productos").insert(nuevo_p).execute()
                    st.success("✅ Producto guardado permanentemente")
                except Exception as e:
                    st.error(f"Error: {e}")

    with t2:
        res = supabase.table("productos").select("*").execute()
        if res.data:
            df_inv = pd.DataFrame(res.data)
            columnas = ['id', 'codigo', 'nombre', 'stock', 'precio_pub']
            if role == "admin": columnas.append('precio_inv')
            st.dataframe(df_inv[columnas], use_container_width=True)
            
            if role == "admin":
                id_del = st.number_input("ID para eliminar", min_value=1, step=1)
                if st.button("🗑️ Eliminar Producto"):
                    supabase.table("productos").delete().eq("id", id_del).execute()
                    st.rerun()

# --- 7. MÓDULO DE REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes de Venta y Utilidad")
    res_v = supabase.table("ventas").select("*").execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Ventas Totales ($)", f"${df_v['precio_total'].sum():,.2f}")
        col_m2.metric("Ganancia Neta ($)", f"${df_v['ganancia'].sum():,.2f}")
        
        st.write("### Historial de Movimientos")
        st.dataframe(df_v.sort_values(by="fecha", ascending=False), use_container_width=True)
    else:
        st.info("No hay historial de ventas.")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.authenticated = False
    st.rerun()
