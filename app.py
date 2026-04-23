import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- 1. CONEXIÓN ---
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Sistema Duo POS", layout="wide", page_icon="⚖️")

# --- 2. SISTEMA DE ACCESO ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acceso al Sistema")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if u == "admin" and p == "admin123":
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "venta123":
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
    st.stop()

# --- 3. BARRA LATERAL (Menú y Cerrar Sesión) ---
role = st.session_state.role
st.sidebar.title(f"Bienvenido, {role.capitalize()}")
menu = st.sidebar.radio("Navegación", ["Ventas", "Inventario", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state.auth = False
    st.session_state.role = None
    st.rerun()

# --- 4. MÓDULO DE VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    
    if res.data:
        df = pd.DataFrame(res.data)
        prod_sel = st.selectbox("Buscar Producto", df['nombre'])
        item = df[df['nombre'] == prod_sel].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            if item.get('foto_path'): st.image(item['foto_path'], width=300)
        
        with col2:
            st.subheader(item['nombre'])
            p_venta = st.number_input("Precio de Venta ($)", value=float(item['precio_pub']))
            cant = st.number_input("Cantidad", 1, int(item['stock']))
            
            if st.button("Confirmar Venta"):
                ganancia = (p_venta - item['precio_inv']) * cant
                supabase.table("productos").update({"stock": int(item['stock']-cant)}).eq("id", item['id']).execute()
                supabase.table("ventas").insert({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "producto": item['nombre'],
                    "cantidad": cant,
                    "precio_total": p_venta * cant,
                    "ganancia": ganancia if role == "admin" else 0
                }).execute()
                st.success("Venta realizada")
                st.rerun()

# --- 5. MÓDULO DE INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario Completo")
    
    tabs_list = ["Existencias"]
    if role == "admin":
        tabs_list.insert(0, "Añadir Producto")
    
    selected_tabs = st.tabs(tabs_list)
    
    # Pestaña Añadir (Solo Admin)
    if role == "admin":
        with selected_tabs[0]:
            with st.form("registro_nuevo", clear_on_submit=True):
                c1, c2 = st.columns(2)
                cod = c1.text_input("Código")
                nom = c2.text_input("Nombre")
                inv = c1.number_input("Precio Inversión", min_value=0.0)
                pub = c2.number_input("Precio al Público", min_value=0.0)
                stk = st.number_input("Stock Inicial", min_value=0)
                desc = st.text_area("Descripción")
                foto = st.camera_input("Foto")
                
                if st.form_submit_button("Registrar"):
                    url = ""
                    if foto:
                        fname = f"{cod}.jpg"
                        supabase.storage.from_("fotos").upload(fname, foto.getvalue(), {"content-type":"image/jpeg", "x-upsert":"true"})
                        url = supabase.storage.from_("fotos").get_public_url(fname)
                    
                    supabase.table("productos").insert({
                        "codigo": cod, "nombre": nom, "descripcion": desc,
                        "precio_inv": inv, "precio_pub": pub, "stock": stk, "foto_path": url
                    }).execute()
                    st.success("Producto registrado")

  # Pestaña Existencias (Admin edita, Equipo solo ve)
    idx_ex = 1 if role == "admin" else 0
    with selected_tabs[idx_ex]:
        res_i = supabase.table("productos").select("*").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            
            # --- NUEVO ORDEN DE COLUMNAS ---
            # Movimos 'stock' y 'precio_pub' (Venta) antes de 'descripcion'
            columnas_ordenadas = ['id', 'foto_path', 'codigo', 'nombre', 'stock', 'precio_pub']
            
            # Si es admin, insertamos el precio de inversión (Costo) antes de la descripción también
            if role == "admin":
                columnas_ordenadas.append('precio_inv')
            
            # Dejamos la descripción al final para que no estorbe la vista rápida de números
            columnas_ordenadas.append('descripcion')
            
            # Filtro de seguridad: solo columnas que existen en el dataframe real
            cols_finales = [c for c in columnas_ordenadas if c in df_i.columns]

            st.info("💡 Haz doble clic en cualquier celda para editar (solo Admin).")
            
            # Mostramos el editor con el nuevo orden
            df_editado = st.data_editor(
                df_i[cols_finales],
                column_config={
                    "id": None, 
                    "foto_path": st.column_config.ImageColumn("Imagen"),
                    "nombre": st.column_config.TextColumn("Producto", width="medium"),
                    "stock": st.column_config.NumberColumn("Stock", format="%d"),
                    "precio_pub": st.column_config.NumberColumn("Venta ($)", format="$%.2f"),
                    "precio_inv": st.column_config.NumberColumn("Costo ($)", format="$%.2f"),
                    "descripcion": st.column_config.TextColumn("Descripción", width="large")
                },
                hide_index=True,
                use_container_width=True,
                disabled=False if role == "admin" else True
            )

            # Botón para guardar cambios (Solo Admin)
            if role == "admin":
                if st.button("💾 Guardar cambios en Inventario"):
                    for index, row in df_editado.iterrows():
                        datos_update = {
                            "nombre": row['nombre'],
                            "precio_pub": float(row['precio_pub']),
                            "stock": int(row['stock'])
                        }
                        if 'descripcion' in row: datos_update["descripcion"] = row['descripcion']
                        if 'precio_inv' in row: datos_update["precio_inv"] = float(row['precio_inv'])
                        
                        supabase.table("productos").update(datos_update).eq("id", row['id']).execute()
                    
                    st.success("¡Inventario actualizado!")
                    st.rerun()
