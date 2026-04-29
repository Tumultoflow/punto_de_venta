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

# --- 2. GESTIÓN DE SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acceso Duo Legal")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "admin1": 
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "equipo1": 
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
    st.stop()

role = st.session_state.role
if st.sidebar.button("🚪 CERRAR SESIÓN"):
    st.session_state.auth = False
    st.rerun()

menu = st.sidebar.radio("Menú Principal", ["Ventas", "Inventario", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])

# --- 3. SECCIÓN DE VENTAS ---
if menu == "Ventas":
    st.header("💰 Nueva Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df_v = pd.DataFrame(res.data)
        busqueda = st.text_input("🔍 Buscar producto por nombre o código")
        df_f = df_v[df_v.apply(lambda r: busqueda.lower() in str(r).lower(), axis=1)] if busqueda else df_v
        
        if not df_f.empty:
            sel = st.selectbox("Selecciona Producto", df_f['nombre'])
            item = df_f[df_f['nombre'] == sel].iloc[0]
            
            c1, c2 = st.columns(2)
            with c1:
                if item.get('foto_path'): st.image(item['foto_path'], width=300)
            with c2:
                vendedor = st.text_input("👤 Vendedor")
                cant = st.number_input("Cantidad", 1, int(item['stock']))
                if st.button("🚀 Confirmar Venta"):
                    # Registrar y actualizar stock
                    new_stk = int(item['stock'] - cant)
                    supabase.table("productos").update({"stock": new_stk}).eq("id", item['id']).execute()
                    supabase.table("ventas").insert({
                        "producto": item['nombre'], "codigo_prod": item['codigo'],
                        "cantidad": cant, "precio_total": float(item['precio_pub']) * cant,
                        "vendedor": vendedor, "fecha_venta": datetime.now(ZONA_LOCAL).isoformat()
                    }).execute()
                    st.success("Venta realizada")
                    st.rerun()

# --- 4. SECCIÓN DE INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    res_i = supabase.table("productos").select("*").order("categoria").execute()
    df_i = pd.DataFrame(res_i.data) if res_i.data else pd.DataFrame()

    t_lista, t_nuevo = st.tabs(["📋 Existencias y Edición", "🆕 Registro Nuevo"])

    with t_lista:
        if role == "admin" and not df_i.empty:
            st.subheader("🛠️ Panel de Edición de Productos")
            # Selector para editar
            p_edit = st.selectbox("Selecciona para editar o corregir código:", ["-- Seleccionar --"] + sorted(df_i['nombre'].tolist()))
            
            if p_edit != "-- Seleccionar --":
                it = df_i[df_i['nombre'] == p_edit].iloc[0]
                with st.expander("📝 Formulario de Edición", expanded=True):
                    col_e1, col_e2 = st.columns(2)
                    e_nom = col_e1.text_input("Nombre", value=it['nombre'])
                    e_cat = col_e2.selectbox("Categoría", ["HOGAR", "ELECTRÓNICA", "PAPELERÍA", "BELLEZA", "MODA", "DEPORTES", "HERRAMIENTAS"], 
                                           index=["HOGAR", "ELECTRÓNICA", "PAPELERÍA", "BELLEZA", "MODA", "DEPORTES", "HERRAMIENTAS"].index(it['categoria']) if it['categoria'] in ["HOGAR", "ELECTRÓNICA", "PAPELERÍA", "BELLEZA", "MODA", "DEPORTES", "HERRAMIENTAS"] else 0)
                    e_sub = col_e1.text_input("Subcategoría", value=it.get('subcategoria', ''))
                    e_inv = col_e2.number_input("Inversión", value=float(it['precio_inv']))
                    e_pub = col_e1.number_input("Público", value=float(it['precio_pub']))
                    e_stk = col_e2.number_input("Stock", value=int(it['stock']))

                    if st.button("🔄 Actualizar Datos y Regenerar Código"):
                        try:
                            # 1. Obtener secuencia original
                            seq_orig = it['codigo'].split('-')[-1] if "-" in it['codigo'] else "001"
                            # 2. Generar nuevo código
                            nuevo_c = f"{e_cat[:3].upper()}-{e_sub[:2].upper()}-{e_nom[:3].upper()}-{seq_orig}"
                            
                            upd_data = {
                                "nombre": e_nom, "categoria": e_cat, "subcategoria": e_sub,
                                "precio_inv": e_inv, "precio_pub": e_pub, "stock": e_stk, "codigo": nuevo_c
                            }
                            # 3. Actualizar Producto
                            supabase.table("productos").update(upd_data).eq("id", it['id']).execute()
                            # 4. Actualizar Ventas relacionadas para no perder historial
                            supabase.table("ventas").update({"codigo_prod": nuevo_c}).eq("codigo_prod", it['codigo']).execute()
                            
                            st.success(f"✅ Actualizado con éxito. Nuevo Código: {nuevo_c}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error técnico: {e}. Revisa si la columna 'subcategoria' existe en Supabase.")

        st.markdown("---")
        st.subheader("📋 Tabla de Inventario")
        st.dataframe(df_i, use_container_width=True, hide_index=True)

    with t_nuevo:
        if role == "admin":
            st.subheader("🆕 Registrar Nuevo (Código Auto)")
            with st.form("f_alta", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n_nom = c1.text_input("Nombre*")
                n_cat = c2.selectbox("Categoría*", ["HOGAR", "ELECTRÓNICA", "PAPELERÍA", "BELLEZA", "MODA", "DEPORTES", "HERRAMIENTAS"])
                n_sub = c1.text_input("Subcategoría*")
                n_inv = c2.number_input("Costo Inversión")
                n_pub = c1.number_input("Precio Público")
                n_stk = c2.number_input("Stock Inicial", step=1)
                
                if st.form_submit_button("🚀 Guardar Producto"):
                    if n_nom and n_sub:
                        # Calcular secuencia por categoría y subcategoría
                        res_c = supabase.table("productos").select("id", count="exact").eq("categoria", n_cat).eq("subcategoria", n_sub).execute()
                        n_seq = str((res_c.count or 0) + 1).zfill(3)
                        n_cod = f"{n_cat[:3].upper()}-{n_sub[:2].upper()}-{n_nom[:3].upper()}-{n_seq}"
                        
                        supabase.table("productos").insert({
                            "codigo": n_cod, "nombre": n_nom, "categoria": n_cat, "subcategoria": n_sub,
                            "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk
                        }).execute()
                        st.success(f"Producto creado: {n_cod}")
                        st.rerun()
                    else:
                        st.warning("Nombre y Subcategoría son obligatorios.")

# --- 5. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reporte de Ventas")
    res_v = supabase.table("ventas").select("*").execute()
    if res_v.data:
        df_rep = pd.DataFrame(res_v.data)
        st.metric("Ventas Totales", f"${df_rep['precio_total'].sum():,.2f}")
        st.dataframe(df_rep, use_container_width=True)
