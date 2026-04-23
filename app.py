import streamlit as st
import pandas as pd
import sqlite3
import os

# --- CONFIGURACIÓN Y SEGURIDAD ---
st.set_page_config(page_title="Sistema de Gestión Duo", layout="wide")

def check_password():
    """Retorna True si el usuario ingresó credenciales correctas."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔐 Acceso al Sistema")
        user = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar"):
            # Configura aquí tus contraseñas
            if user == "admin" and password == "admin123":
                st.session_state.authenticated = True
                st.session_state.role = "admin"
                st.rerun()
            elif user == "equipo" and password == "venta123":
                st.session_state.authenticated = True
                st.session_state.role = "equipo"
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
        return False
    return True

if check_password():
    role = st.session_state.role

    # --- LÓGICA DE BASE DE DATOS ---
    def conectar():
        return sqlite3.connect('inventario_online.db')

    # --- INTERFAZ ---
    st.sidebar.title(f"Sesión: {role.capitalize()}")
    
    # Restricción de Menú según Rol
    opciones = ["Punto de Venta"]
    if role == "admin":
        opciones.append("Inventario (Admin)")
    
    menu = st.sidebar.radio("Ir a:", opciones)

    if menu == "Punto de Venta":
        st.header("💰 Punto de Venta")
        conn = conectar()
        # El equipo NO consulta precios de inversión en el SQL por seguridad
        query = "SELECT id, nombre, stock, precio_pub, foto_path FROM productos"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if not df.empty:
            producto_sel = st.selectbox("Producto", df['nombre'])
            datos = df[df['nombre'] == producto_sel].iloc[0]
            
            c1, c2 = st.columns([1, 2])
            with c1:
                if datos['foto_path'] and os.path.exists(datos['foto_path']):
                    st.image(datos['foto_path'], width=250)
            with c2:
                st.subheader(datos['nombre'])
                st.write(f"### Precio: ${datos['precio_pub']}")
                st.write(f"Stock: {datos['stock']}")
                
                # Solo el admin ve el botón de "Ver detalles de costo" si fuera necesario
                if role == "admin":
                    st.info("Acceso Admin: Puedes ver reportes en el menú lateral.")
                
                cantidad = st.number_input("Cantidad", min_value=1, max_value=int(datos['stock']))
                if st.button("Registrar Venta"):
                    st.success("Venta procesada con éxito")
                    # Aquí iría la lógica de restar stock
        else:
            st.warning("No hay productos registrados.")

    elif menu == "Inventario (Admin)":
        st.header("⚙️ Panel de Administración")
        st.write("Aquí puedes ver costos de inversión y utilidades.")
        
        conn = conectar()
        df_admin = pd.read_sql_query("SELECT * FROM productos", conn)
        conn.close()
        
        # Calcular margen en el momento (solo para ojos del admin)
        df_admin['Margen $'] = df_admin['precio_pub'] - df_admin['precio_inv']
        st.dataframe(df_admin)

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.authenticated = False
        st.rerun()
