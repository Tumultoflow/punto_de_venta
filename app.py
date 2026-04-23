import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from datetime import datetime

# --- CONFIGURACIÓN DE CONEXIÓN CORREGIDA ---
# Nota: He añadido las comillas y corregido la URL
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"

# Conectar a Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Duo - Gestión Total", layout="wide", page_icon="📦")

if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- LOGIN ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Acceso al Sistema")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "admin123":
            st.session_state.authenticated, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "venta123":
            st.session_state.authenticated, st.session_state.role = True, "equipo"
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.stop()

# --- NAVEGACIÓN ---
role = st.session_state.role
st.sidebar.title(f"Usuario: {role.upper()}")

opciones = ["Ventas", "Inventario"]
if role == "admin":
    opciones.append("Reportes")

menu = st.sidebar.radio("Ir a:", opciones)

# --- MÓDULO VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    
    # Traer productos desde Supabase
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    productos = res.data
    
    if productos:
        df_prod = pd.DataFrame(productos)
        col1, col2 = st.columns([1, 1])
        with col1:
            opcion_prod = st.selectbox("Producto", df_prod['nombre'])
            prod_data = df_prod[df_prod['nombre'] == opcion_prod].iloc[0]
            if prod_data['foto_path'] and os.path.exists(prod_data['foto_path']):
                st.image(prod_data['foto_path'], width=300)
        
        with col2:
            st.subheader(prod_data['nombre'])
            precio_final = st.number_input("Precio de Venta ($)", value=float(prod_data['precio_pub']))
            cant = st.number_input("Cantidad", min_value=1, max_value=int(prod_data['stock']), step=1)
            
            if st.button("Confirmar Venta"):
                ganancia_total = (precio_final - prod_data['precio_inv']) * cant
                # 1. Actualizar Stock en Supabase
                nuevo_stock = int(prod_data['stock'] - cant)
                supabase.table("productos").update({"stock": nuevo_stock}).eq("id", prod_data['id']).execute()
                
                # 2. Registrar Venta en Supabase
                fecha_v = datetime.now().strftime("%Y-%m-%d %H:%M")
                venta_data = {
                    "fecha": fecha_v,
                    "producto": prod_data['nombre'],
                    "cantidad": int(cant),
                    "precio_total": float(precio_final * cant),
                    "ganancia": float(ganancia_total)
                }
                supabase.table("ventas").insert(venta_data).execute()
                
                st.success("✅ Venta registrada en la nube")
                st.rerun()
    else:
        st.warning("No hay productos con stock disponible.")

# --- MÓDULO INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Mercancía")
    t1, t2 = st.tabs(["Registrar Nuevo", "Lista de Existencias"])
    
    with t1:
        with st.form("form_registro"):
            c1, c2 = st.columns(2)
            cod = c1.text_input("Código / SKU")
            nom = c2.text_input("Nombre del Producto")
            inv = c1.number_input("Precio Inversión", min_value=0.0) if role == "admin" else 0.0
            pub = c2.number_input("Precio Público Sugerido", min_value=0.0)
            stk = st.number_input("Cantidad", min_value=0, step=1)
            foto = st.camera_input("Foto")
            
            if st.form_submit_button("Guardar en Nube"):
                path_foto = f"fotos/{cod}.jpg" if foto else ""
                if foto:
                    with open(path_foto, "wb") as f: f.write(foto.getbuffer())
                
                nuevo_prod = {
                    "codigo": cod, "nombre": nom, "stock": stk, 
                    "precio_inv": inv, "precio_pub": pub, "foto_path": path_foto
                }
                supabase.table("productos").insert(nuevo_prod).execute()
                st.success("¡Guardado exitosamente en Supabase!")

    with t2:
        res = supabase.table("productos").select("*").execute()
        if res.data:
            df_inv = pd.DataFrame(res.data)
            # Ocultar columnas sensibles si no es admin
            cols_mostrar = ['id', 'codigo', 'nombre', 'stock', 'precio_pub']
            if role == "admin": cols_mostrar.append('precio_inv')
            
            st.dataframe(df_inv[cols_mostrar], use_container_width=True)
            
            if role == "admin":
                id_del = st.number_input("ID para eliminar", min_value=1, step=1)
                if st.button("Eliminar"):
                    supabase.table("productos").delete().eq("id", id_del).execute()
                    st.rerun()

# --- MÓDULO REPORTES ---
elif menu == "Reportes":
    st.header("📊 Resumen Económico")
    res = supabase.table("ventas").select("*").execute()
    if res.data:
        df_v = pd.DataFrame(res.data)
        st.metric("Ganancia Total Real", f"${df_v['ganancia'].sum():,.2f}")
        st.dataframe(df_v)
    else:
        st.info("Aún no hay ventas.")

if st.sidebar.button("Salir"):
    st.session_state.authenticated = False
    st.rerun()
