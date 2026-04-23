import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema de Gestión Duo", layout="wide", page_icon="⚖️")

# Crear carpetas necesarias
if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- FUNCIONES DE BASE DE DATOS ---
def conectar():
    return sqlite3.connect('negocio_pro.db', check_same_thread=False)

def inicializar_db():
    conn = conectar()
    cursor = conn.cursor()
    # Productos: Código, Nombre, Stock, Inversión, Público, Foto
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, nombre TEXT, 
                       stock INTEGER, precio_inv REAL, precio_pub REAL, foto_path TEXT)''')
    # Ventas: Fecha, Producto, Cantidad, Precio Final Cobrado, Ganancia Real
    cursor.execute('''CREATE TABLE IF NOT EXISTS ventas 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, producto TEXT, 
                       cantidad INTEGER, precio_total_cobrado REAL, ganancia_neta REAL)''')
    conn.commit()
    conn.close()

inicializar_db()

# --- SISTEMA DE LOGIN ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Acceso al Sistema de Control")
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
st.sidebar.title(f"Bienvenido: {role.capitalize()}")
opciones = ["Ventas"]
if role == "admin":
    opciones += ["Inventario", "Reportes"]

menu = st.sidebar.radio("Navegación", opciones)

# --- MÓDULO DE VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    conn = conectar()
    df_prod = pd.read_sql_query("SELECT * FROM productos WHERE stock > 0", conn)
    
    if not df_prod.empty:
        col_busqueda, col_detalles = st.columns([1, 1])
        
        with col_busqueda:
            opcion_prod = st.selectbox("Selecciona Producto o busca por Código", df_prod['nombre'])
            prod_data = df_prod[df_prod['nombre'] == opcion_prod].iloc[0]
            if prod_data['foto_path'] and os.path.exists(prod_data['foto_path']):
                st.image(prod_data['foto_path'], width=350)
            else:
                st.info("Sin imagen disponible")

        with col_detalles:
            st.subheader(prod_data['nombre'])
            st.write(f"**SKU/Código:** {prod_data['codigo']}")
            st.write(f"**Stock disponible:** {prod_data['stock']}")
            
            # Ajuste manual de precio
            precio_base = float(prod_data['precio_pub'])
            precio_final = st.number_input("Precio de Venta ($)", value=precio_base, help="Puedes cambiar el precio manualmente para esta venta.")
            
            cant = st.number_input("Cantidad", min_value=1, max_value=int(prod_data['stock']), step=1)
            total_operacion = precio_final * cant
            st.markdown(f"### Total a Cobrar: **${total_operacion:,.2f}**")
            
            if st.button("Confirmar y Registrar Venta"):
                # Cálculo de ganancia basado en el precio que se puso manualmente
                ganancia_unidad = precio_final - prod_data['precio_inv']
                ganancia_total = ganancia_unidad * cant
                
                cursor = conn.cursor()
                # 1. Restar Stock
                cursor.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cant, prod_data['id']))
                # 2. Guardar Venta
                fecha_v = datetime.now().strftime("%Y-%m-%d %H:%M")
                cursor.execute("INSERT INTO ventas (fecha, producto, cantidad, precio_total_cobrado, ganancia_neta) VALUES (?,?,?,?,?)",
                               (fecha_v, prod_data['nombre'], cant, total_operacion, ganancia_total))
                conn.commit()
                st.balloons()
                st.success("Venta realizada correctamente.")
                st.rerun()
    else:
        st.warning("No hay productos en inventario con stock disponible.")
    conn.close()

# --- MÓDULO DE INVENTARIO (ADMIN) ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    t1, t2 = st.tabs(["Agregar / Editar", "Ver y Eliminar"])
    
    with t1:
        with st.form("form_inv"):
            c1, c2 = st.columns(2)
            cod = c1.text_input("Código / SKU")
            nom = c2.text_input("Nombre del Producto")
            inv = c1.number_input("Precio Inversión (Costo)", min_value=0.0)
            pub = c2.number_input("Precio Público (Sugerido)", min_value=0.0)
            stk = st.number_input("Cantidad (Stock)", min_value=0, step=1)
            foto = st.camera_input("Capturar foto")
            
            if st.form_submit_button("Guardar Producto"):
                path = f"fotos/{cod}.jpg" if foto else ""
                if foto:
                    with open(path, "wb") as f: f.write(foto.getbuffer())
                
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO productos (codigo, nombre, stock, precio_inv, precio_pub, foto_path) VALUES (?,?,?,?,?,?)",
                               (cod, nom, stk, inv, pub, path))
                conn.commit()
                conn.close()
                st.success("Producto registrado exitosamente.")

    with t2:
        conn = conectar()
        inventario_df = pd.read_sql_query("SELECT id, codigo, nombre, stock, precio_inv, precio_pub FROM productos", conn)
        st.dataframe(inventario_df, use_container_width=True)
        
        id_del = st.number_input("ID del producto a eliminar", min_value=1, step=1)
        if st.button("🗑️ Eliminar Producto"):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM productos WHERE id = ?", (id_del,))
            conn.commit()
            st.warning(f"Producto {id_del} eliminado.")
            st.rerun()
        conn.close()

# --- MÓDULO DE REPORTES (ADMIN) ---
elif menu == "Reportes":
    st.header("📊 Reporte de Ganancias y Ventas")
    conn = conectar()
    df_ventas = pd.read_sql_query("SELECT * FROM ventas", conn)
    conn.close()
    
    if not df_ventas.empty:
        # Métricas principales
        total_ingresos = df_ventas['precio_total_cobrado'].sum()
        total_ganancia = df_ventas['ganancia_neta'].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Ingresos Totales", f"${total_ingresos:,.2f}")
        m2.metric("Ganancia Neta Real", f"${total_ganancia:,.2f}")
        m3.metric("Núm. de Ventas", len(df_ventas))
        
        st.subheader("Historial Detallado")
        st.dataframe(df_ventas.sort_values(by="fecha", ascending=False), use_container_width=True)
    else:
        st.info("Aún no hay ventas registradas.")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.authenticated = False
    st.rerun()
