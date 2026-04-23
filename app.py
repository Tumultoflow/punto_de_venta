import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime

# --- CONFIGURACIÓN DE CONEXIÓN ---
# Es aquí donde borras el texto genérico y pegas tus llaves reales
SUPABASE_URL = https://gfileauwnaarqvsndlby.supabase.co/rest/v1
SUPABASE_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema Duo - Gestión Total", layout="wide", page_icon="📦")

if not os.path.exists("fotos"):
    os.makedirs("fotos")

def conectar():
    return sqlite3.connect('negocio_pro.db', check_same_thread=False)

def inicializar_db():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, nombre TEXT, 
                       stock INTEGER, precio_inv REAL, precio_pub REAL, foto_path TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ventas 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, 
                       cantidad INTEGER, precio_total_cobrado REAL, ganancia_neta REAL)''')
    conn.commit()
    conn.close()

inicializar_db()

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

# Ahora AMBOS roles ven Ventas e Inventario
opciones = ["Ventas", "Inventario"]
if role == "admin":
    opciones.append("Reportes") # Solo tú ves las ganancias totales

menu = st.sidebar.radio("Ir a:", opciones)

# --- MÓDULO VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    conn = conectar()
    df_prod = pd.read_sql_query("SELECT * FROM productos WHERE stock > 0", conn)
    
    if not df_prod.empty:
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
                cursor = conn.cursor()
                cursor.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cant, prod_data['id']))
                fecha_v = datetime.now().strftime("%Y-%m-%d %H:%M")
                cursor.execute("INSERT INTO ventas (fecha, producto, cantidad, precio_total_cobrado, ganancia_neta) VALUES (?,?,?,?,?)",
                               (fecha_v, prod_data['nombre'], cant, precio_final * cant, ganancia_total))
                conn.commit()
                st.success("Venta registrada")
                st.rerun()
    conn.close()

# --- MÓDULO INVENTARIO (AMBOS ACCEDEN) ---
elif menu == "Inventario":
    st.header("📦 Gestión de Mercancía")
    t1, t2 = st.tabs(["Registrar Nuevo / Compras", "Lista de Existencias"])
    
    with t1:
        st.subheader("Dar de alta producto")
        with st.form("form_registro"):
            c1, c2 = st.columns(2)
            cod = c1.text_input("Código / SKU")
            nom = c2.text_input("Nombre del Producto")
            
            # Si es Admin ve precio de inversión, si es Equipo ponemos 0 por defecto o un campo oculto
            if role == "admin":
                inv = c1.number_input("Precio Inversión (Costo)", min_value=0.0)
            else:
                inv = 0.0 # El equipo no registra el costo, o puedes dejar que lo pongan si confías en ellos
            
            pub = c2.number_input("Precio Público Sugerido", min_value=0.0)
            stk = st.number_input("Cantidad que ingresa", min_value=0, step=1)
            foto = st.camera_input("Foto de la mercancía")
            
            if st.form_submit_button("Guardar en Sistema"):
                path = f"fotos/{cod}.jpg" if foto else ""
                if foto:
                    with open(path, "wb") as f: f.write(foto.getbuffer())
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO productos (codigo, nombre, stock, precio_inv, precio_pub, foto_path) VALUES (?,?,?,?,?,?)",
                               (cod, nom, stk, inv, pub, path))
                conn.commit()
                conn.close()
                st.success("¡Producto añadido al inventario!")

    with t2:
        conn = conectar()
        # Seleccionamos columnas según el rol para proteger tus datos
        if role == "admin":
            query = "SELECT id, codigo, nombre, stock, precio_inv, precio_pub FROM productos"
        else:
            query = "SELECT id, codigo, nombre, stock, precio_pub FROM productos"
            
        inventario_df = pd.read_sql_query(query, conn)
        st.dataframe(inventario_df, use_container_width=True)
        
        if role == "admin":
            id_del = st.number_input("ID para eliminar", min_value=1, step=1)
            if st.button("Eliminar permanentemente"):
                cursor = conn.cursor(); cursor.execute("DELETE FROM productos WHERE id = ?", (id_del,))
                conn.commit(); st.rerun()
        conn.close()

# --- MÓDULO REPORTES (SOLO ADMIN) ---
elif menu == "Reportes":
    st.header("📊 Resumen Económico")
    conn = conectar()
    df_ventas = pd.read_sql_query("SELECT * FROM ventas", conn)
    conn.close()
    if not df_ventas.empty:
        st.metric("Ganancia Total Acumulada", f"${df_ventas['ganancia_neta'].sum():,.2f}")
        st.dataframe(df_ventas)
    else:
        st.info("Sin ventas aún.")

if st.sidebar.button("Salir"):
    st.session_state.authenticated = False
    st.rerun()
