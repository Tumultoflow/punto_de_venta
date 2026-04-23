import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- 1. CONFIGURACIÓN DE CONEXIÓN ---
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"

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

role = st.session_state.role
st.sidebar.title(f"Sesión: {role.upper()}")
opciones = ["Ventas", "Inventario"]
if role == "admin":
    opciones.append("Reportes")

menu = st.sidebar.radio("Ir a:", opciones)

# --- 4. MÓDULO DE VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
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
                st.info("Sin imagen disponible")

        with col2:
            st.subheader(prod_data['nombre'])
            st.write(f"**Código:** {prod_data['codigo']}")
            st.write(f"**Stock actual:** {prod_data['stock']}")
            
            precio_final = st.number_input("Precio de Venta ($)", value=float(prod_data['precio_pub']))
            cant = st.number_input("Cantidad", min_value=1, max_value=int(prod_data['stock']), step=1)
            
            if st.button("Confirmar Venta"):
                ganancia_total = (precio_final - prod_data['precio_inv']) * cant
                nuevo_stock = int(prod_data['stock'] - cant)
                
                # Actualizar stock
                supabase.table("productos").update({"stock": nuevo_stock}).eq("id", prod_data['id']).execute()
                
                # Registrar venta
                venta = {
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "producto": prod_data['nombre'],
                    "cantidad": int(cant),
                    "precio_total": float(precio_final * cant),
                    "ganancia": float(ganancia_total)
                }
                supabase.table("ventas").insert(venta).execute()
                st.success(f"✅ Venta registrada: {prod_data['nombre']} x{cant}")
                st.balloons()
                st.rerun()
    else:
        st.warning("No hay productos con existencias.")

# --- 5. MÓDULO DE INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Mercancía")
    t1, t2 = st.tabs(["Registrar Nuevo", "Existencias Visuales"])
    
    with t1:
        st.subheader("Alta de Producto")
        with st.form("registro_nube", clear_on_submit=True):
            c1, c2 = st.columns(2)
            cod = c1.text_input("Código / SKU")
            nom = c2.text_input("Nombre del Producto")
            inv = c1.number_input("Precio Inversión (Costo)", min_value=0.0) if role == "admin" else 0.0
            pub = c2.number_input("Precio Venta Público", min_value=0.0)
            stk = st.number_input("Cantidad Inicial", min_value=0, step=1)
            foto = st.camera_input("Capturar Foto")
            
            if st.form_submit_button("Guardar en Nube"):
                if not cod or not nom:
                    st.error("Código y Nombre son obligatorios")
                else:
                    try:
                        url_foto = ""
                        if foto:
                            # Nombre único para evitar conflictos
                            nombre_img = f"{cod}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
                            supabase.storage.from_("fotos").upload(
                                path=nombre_img,
                                file=foto.getvalue(),
                                file_options={"content-type": "image/jpeg", "x-upsert": "true"}
                            )
                            url_foto = supabase.storage.from_("fotos").get_public_url(nombre_img)
                        
                        nuevo_p = {
                            "codigo": cod, "nombre": nom, "stock": stk,
                            "precio_inv": inv, "precio_pub": pub, "foto_path": url_foto
                        }
                        supabase.table("productos").insert(nuevo_p).execute()
                        st.success("✅ Producto y foto guardados correctamente")
                    except Exception as e:
                        st.error(f"Error técnico: {e}")

    with t2:
        res = supabase.table("productos").select("*").execute()
        if res.data:
            df_inv = pd.DataFrame(res.data)
            columnas_visibles = ['foto_path', 'codigo', 'nombre', 'stock', 'precio_pub']
            if role == "admin":
                columnas_visibles.append('precio_inv')

            # Tabla con imágenes renderizadas
            st.data_editor(
                df_inv[columnas_visibles],
                column_config={
                    "foto_path": st.column_config.ImageColumn("Imagen", help="Vista previa del producto"),
                    "precio_pub": st.column_config.NumberColumn("Precio Venta", format="$%.2f"),
                    "precio_inv": st.column_config.NumberColumn("Costo Inv.", format="$%.2f"),
                },
                hide_index=True,
                use_container_width=True,
                disabled=True
            )
            
            if role == "admin":
                st.write("---")
                id_del = st.number_input("ID para eliminar", min_value=1, step=1)
                if st.button("🗑️ Eliminar Producto Definitivamente"):
                    supabase.table("productos").delete().eq("id", id_del).execute()
                    st.rerun()

# --- 6. MÓDULO DE REPORTES ---
elif menu == "Reportes":
    st.header("📊 Resumen Económico (Solo Admin)")
    res_v = supabase.table("ventas").select("*").execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        c1, c2 = st.columns(2)
        c1.metric("Ingresos Totales", f"${df_v['precio_total'].sum():,.2f}")
        c2.metric("Utilidad Neta", f"${df_v['ganancia'].sum():,.2f}")
        
        st.subheader("Historial Detallado")
        st.dataframe(df_v.sort_values(by="fecha", ascending=False), use_container_width=True)
    else:
        st.info("No hay registros de ventas todavía.")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.authenticated = False
    st.rerun()
