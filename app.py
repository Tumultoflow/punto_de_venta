import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import pytz

# --- 1. CONFIGURACIÓN ---
ZONA_LOCAL = pytz.timezone('America/Mexico_City')
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="TUMULTOFLOW", layout="wide", page_icon="⚖️")

# --- 2. LOGIN ---
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.title("🔐 Acceso")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "admin1": st.session_state.auth, st.session_state.role = True, "admin"
        elif u == "equipo" and p == "equipo1": st.session_state.auth, st.session_state.role = True, "equipo"
        st.rerun()
    st.stop()

role = st.session_state.role
if st.sidebar.button("🚪 CERRAR SESIÓN"):
    st.session_state.auth = False
    st.rerun()

menu = st.sidebar.radio("Menú", ["Ventas", "Inventario", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])

# --- 3. INVENTARIO (CON EDICIÓN DE CÓDIGOS) ---
if menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    res = supabase.table("productos").select("*").order("categoria").execute()
    df = pd.DataFrame(res.data).fillna("") if res.data else pd.DataFrame()

    tab_lista, tab_nuevo = st.tabs(["📋 Existencias y Edición", "🆕 Registro Nuevo"])

    with tab_lista:
        if role == "admin" and not df.empty:
            st.subheader("🛠️ Panel de Edición de Productos")
            prod_sel = st.selectbox("🔍 Selecciona un producto para editar su información o código:", ["-- Seleccionar --"] + sorted(df['nombre'].tolist()))
            
            if prod_sel != "-- Seleccionar --":
                item = df[df['nombre'] == prod_sel].iloc[0]
                
                with st.expander(f"📝 Editar: {item['nombre']} (Código actual: {item['codigo']})", expanded=True):
                    c1, c2 = st.columns(2)
                    # Campos editables
                    ed_nom = c1.text_input("Nombre del Producto", value=item['nombre'])
                    ed_cat = c2.selectbox("Categoría", ["HOGAR", "ELECTRÓNICA", "PAPELERÍA", "BELLEZA", "MODA", "DEPORTES", "HERRAMIENTAS"], index=0)
                    ed_sub = c1.text_input("Subcategoría", value=item.get('subcategoria', ''))
                    ed_stk = c2.number_input("Stock", value=int(item['stock']))
                    ed_inv = c1.number_input("Inversión ($)", value=float(item['precio_inv']))
                    ed_pub = c2.number_input("Venta ($)", value=float(item['precio_pub']))

                    if st.button("🔄 Guardar Cambios y Actualizar Código"):
                        # Extraemos la secuencia original (los últimos 3 dígitos del código viejo)
                        secuencia_actual = item['codigo'].split('-')[-1]
                        
                        # Generamos el nuevo código basado en los datos editados
                        nuevo_cod = f"{ed_cat[:3].upper()}-{ed_sub[:2].upper()}-{ed_nom[:3].upper()}-{secuencia_actual}"
                        
                        upd = {
                            "nombre": ed_nom, "categoria": ed_cat, "subcategoria": ed_sub,
                            "stock": ed_stk, "precio_inv": ed_inv, "precio_pub": ed_pub,
                            "codigo": nuevo_cod
                        }
                        supabase.table("productos").update(upd).eq("id", item['id']).execute()
                        st.success(f"✅ ¡Actualizado! El nuevo código es: {nuevo_cod}")
                        st.rerun()

        # Tabla visual
        st.subheader("📋 Lista de Productos")
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_nuevo:
        if role == "admin":
            st.subheader("🆕 Registrar Producto (Código Automático)")
            with st.form("f_nuevo", clear_on_submit=True):
                col1, col2 = st.columns(2)
                n_nom = col1.text_input("Nombre*")
                n_cat = col2.selectbox("Categoría*", ["HOGAR", "ELECTRÓNICA", "PAPELERÍA", "BELLEZA", "MODA", "DEPORTES", "HERRAMIENTAS"])
                n_sub = col1.text_input("Subcategoría*")
                n_inv, n_pub = col2.number_input("Inversión"), col1.number_input("Público")
                n_stk = col2.number_input("Stock inicial", step=1)
                
                if st.form_submit_button("🚀 Crear Producto"):
                    if n_nom and n_sub:
                        # Calcular secuencia nueva
                        count_res = supabase.table("productos").select("id", count="exact").eq("categoria", n_cat).eq("subcategoria", n_sub).execute()
                        seq = str((count_res.count or 0) + 1).zfill(3)
                        
                        # Crear código
                        n_cod = f"{n_cat[:3].upper()}-{n_sub[:2].upper()}-{n_nom[:3].upper()}-{seq}"
                        
                        supabase.table("productos").insert({
                            "codigo": n_cod, "nombre": n_nom, "categoria": n_cat, "subcategoria": n_sub,
                            "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk
                        }).execute()
                        st.success(f"Registrado con código: {n_cod}")
                        st.rerun()
