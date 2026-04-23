import streamlit as st
import pandas as pd
import sqlite3
from PIL import Image
import os

# Configuración de la página
st.set_page_config(page_title="Gestión de Negocio", layout="wide")

# Crear carpeta para fotos si no existe
if not os.path.exists("fotos_productos"):
    os.makedirs("fotos_productos")

# --- FUNCIONES DE BASE DE DATOS ---
def conectar():
    conn = sqlite3.connect('inventario_online.db')
    return conn

def crear_tablas():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, stock INTEGER, 
                       precio_inv REAL, precio_pub REAL, foto_path TEXT)''')
    conn.commit()
    conn.close()

crear_tablas()

# --- INTERFAZ DE USUARIO ---
st.sidebar.title("Navegación")
menu = st.sidebar.radio("Ir a:", ["Punto de Venta", "Inventario / Registro"])

if menu == "Inventario / Registro":
    st.header("📦 Registro de Mercancía")
    
    with st.form("nuevo_producto"):
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre del Producto")
            stock = st.number_input("Stock Inicial", min_value=0, step=1)
        with col2:
            p_inv = st.number_input("Precio de Inversión", min_value=0.0)
            p_pub = st.number_input("Precio al Público", min_value=0.0)
        
        # Opción para foto
        foto = st.camera_input("Capturar foto del producto")
        
        enviado = st.form_submit_button("Guardar Producto")
        
        if enviado and nombre:
            path_foto = ""
            if foto:
                path_foto = f"fotos_productos/{nombre}.jpg"
                with open(path_foto, "wb") as f:
                    f.write(foto.getbuffer())
            
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO productos (nombre, stock, precio_inv, precio_pub, foto_path) VALUES (?,?,?,?,?)",
                           (nombre, stock, p_inv, p_pub, path_foto))
            conn.commit()
            conn.close()
            st.success(f"Producto '{nombre}' guardado con éxito.")

elif menu == "Punto de Venta":
    st.header("💰 Punto de Venta")
    
    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()
    
    if not df.empty:
        producto_sel = st.selectbox("Selecciona un producto para vender", df['nombre'])
        datos_prod = df[df['nombre'] == producto_sel].iloc[0]
        
        c1, c2 = st.columns([1, 2])
        with c1:
            if datos_prod['foto_path'] and os.path.exists(datos_prod['foto_path']):
                st.image(datos_prod['foto_path'], width=200)
            else:
                st.info("Sin foto disponible")
        
        with c2:
            st.write(f"**Precio:** ${datos_prod['precio_pub']}")
            st.write(f"**Stock disponible:** {datos_prod['stock']}")
            cantidad = st.number_input("Cantidad a vender", min_value=1, max_value=int(datos_prod['stock']))
            
            if st.button("Confirmar Venta"):
                ganancia = (datos_prod['precio_pub'] - datos_prod['precio_inv']) * cantidad
                st.balloons()
                st.success(f"Venta realizada. Total: ${datos_prod['precio_pub'] * cantidad} | Ganancia: ${ganancia}")
    else:
        st.warning("No hay productos en el inventario.")