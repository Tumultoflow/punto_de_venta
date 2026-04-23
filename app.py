import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Sistema Duo POS", layout="wide", page_icon="⚖️")

if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acceso Duo")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "admin123":
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "venta123":
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
    st.stop()

role = st.session_state.role
menu = st.sidebar.radio("Navegación", ["Ventas", "Inventario", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])

# --- 2. MÓDULO DE VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    
    if res.data:
        df = pd.DataFrame(res.data)
        prod_sel = st.selectbox("Buscar Producto", df['nombre'])
        item = df[df['nombre'] == prod_sel].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            if item['foto_path']: st.image(item['foto_path'], width=350)
            st.info(f"**Descripción:** {item.get('descripcion', 'Sin descripción')}")
        
        with col2:
            st.subheader(item['nombre'])
            # PRECIO EDITABLE AL MOMENTO
            precio_final = st.number_input("Precio de Venta Actual ($)", value=float(item['precio_pub']))
            cant = st.number_input("Cantidad", 1, int(item['stock']))
            
            if st.button("Confirmar Venta"):
                ganancia = (precio_final - item['precio_inv']) * cant
                # Actualizar Stock
                supabase.table("productos").update({"stock": int(item['stock']-cant)}).eq("id", item['id']).execute()
                # Registrar Venta con Fecha Actual
                supabase.table("ventas").insert({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "producto": item['nombre'],
                    "cantidad": cant,
                    "precio_total": precio_final * cant,
                    "ganancia": ganancia
                }).execute()
                st.success(f"Venta registrada. Total: ${precio_final * cant}")
                st.rerun()

# --- 3. MÓDULO DE INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    t1, t2 = st.tabs(["Añadir Producto", "Editar Existencias"])
    
    with t1:
        with st.form("nuevo_pro", clear_on_submit=True):
            c1, c2 = st.columns(2)
            cod = c1.text_input("Código / SKU")
            nom = c2.text_input("Nombre")
            desc = st.text_area("Descripción del producto")
            
            inv = c1.number_input("Precio Inversión (Costo)", min_value=0.0)
            pub = c2.number_input("Precio Venta Público", min_value=0.0)
            stk = c1.number_input("Stock Inicial", min_value=0)
            f_ingreso = c2.date_input("Fecha de Entrada", datetime.now())
            
            foto = st.camera_input("Foto del producto")
            
            if st.form_submit_button("Guardar Producto"):
                url = ""
                if foto:
                    fname = f"{cod}_{datetime.now().strftime('%S')}.jpg"
                    supabase.storage.from_("fotos").upload(fname, foto.getvalue(), {"content-type":"image/jpeg"})
                    url = supabase.storage.from_("fotos").get_public_url(fname)
                
                supabase.table("productos").insert({
                    "codigo": cod, "nombre": nom, "descripcion": desc,
                    "precio_inv": inv, "precio_pub": pub, "stock": stk,
                    "fecha_entrada": str(f_ingreso), "foto_path": url
                }).execute()
                st.success("Producto añadido al inventario.")

    with t2:
        st.subheader("Editor de Inventario (Cambia datos y presiona Enter)")
        res_i = supabase.table("productos").select("*").execute()
        if res_i.data:
            df_edit = pd.DataFrame(res_i.data)
            # Editor interactivo
            edited_df = st.data_editor(
                df_edit[['id', 'codigo', 'nombre', 'descripcion', 'precio_inv', 'precio_pub', 'stock', 'fecha_entrada']],
                num_rows="dynamic",
                key="prod_editor"
            )
            
            if st.button("Guardar Cambios en la Nube"):
                for index, row in edited_df.iterrows():
                    supabase.table("productos").update({
                        "nombre": row['nombre'],
                        "descripcion": row['descripcion'],
                        "precio_inv": float(row['precio_inv']),
                        "precio_pub": float(row['precio_pub']),
                        "stock": int(row['stock'])
                    }).eq("id", row['id']).execute()
                st.success("Base de datos actualizada correctamente.")

# --- 4. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Historial de Ventas")
    res_v = supabase.table("ventas").select("*").order("fecha", desc=True).execute()
    if res_v.data:
        st.dataframe(pd.DataFrame(res_v.data), use_container_width=True)
