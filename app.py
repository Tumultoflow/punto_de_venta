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

# --- 2. LISTA MAESTRA DE CATEGORÍAS (Edítala aquí) ---
LISTA_CATEGORIAS = [
    "HOGAR", "ELECTRÓNICA", "PAPELERÍA", "BELLEZA", "MODA", 
    "DEPORTES", "HERRAMIENTAS", "JUGUETES", "MASCOTAS", "LEGAL"
]

st.set_page_config(page_title="TUMULTOFLOW", layout="wide", page_icon="⚖️")

# --- 3. LOGIN ---
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.title("🔐 Acceso Duo Legal")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "admin1": st.session_state.auth, st.session_state.role = True, "admin"
        elif u == "equipo" and p == "equipo1": st.session_state.auth, st.session_state.role = True, "equipo"
        st.rerun()
    st.stop()

role = st.session_state.role
menu = st.sidebar.radio("Menú", ["Ventas", "Inventario", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])

# --- 4. VENTAS (CON PRECIO Y FECHA EDITABLE) ---
if menu == "Ventas":
    st.header("💰 Nueva Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df_v = pd.DataFrame(res.data)
        sel = st.selectbox("📦 Seleccionar Producto", df_v['nombre'])
        item = df_v[df_v['nombre'] == sel].iloc[0]
        
        c1, c2 = st.columns(2)
        with c1:
            if item.get('foto_path'): st.image(item['foto_path'], width=250)
            st.info(f"Código: {item['codigo']} | Stock: {item['stock']}")
        
        with c2:
            # CAMPOS SOLICITADOS: Precio y Fecha editables
            v_precio = st.number_input("💵 Precio de Venta (Editable)", value=float(item['precio_pub']))
            v_fecha = st.date_input("📅 Fecha de Venta", datetime.now(ZONA_LOCAL))
            v_hora = st.time_input("⏰ Hora", datetime.now(ZONA_LOCAL))
            v_vendedor = st.text_input("👤 Vendedor")
            v_cant = st.number_input("Cantidad", 1, int(item['stock']))
            
            if st.button("🚀 Confirmar Venta"):
                fecha_completa = datetime.combine(v_fecha, v_hora).isoformat()
                # Actualizar Stock
                supabase.table("productos").update({"stock": int(item['stock'] - v_cant)}).eq("id", item['id']).execute()
                # Registrar Venta
                supabase.table("ventas").insert({
                    "producto": item['nombre'], "codigo_prod": item['codigo'],
                    "cantidad": v_cant, "precio_total": v_precio * v_cant,
                    "vendedor": v_vendedor, "fecha_venta": fecha_completa,
                    "ganancia": (v_precio - item['precio_inv']) * v_cant
                }).execute()
                st.success("✅ Venta registrada correctamente.")
                st.rerun()

# --- 5. INVENTARIO (CON EDICIÓN COMPLETA) ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    res_i = supabase.table("productos").select("*").order("categoria").execute()
    df_i = pd.DataFrame(res_i.data) if res_i.data else pd.DataFrame()

    t_lista, t_nuevo = st.tabs(["📋 Existencias y Edición", "🆕 Registro Nuevo"])

    with t_lista:
        if role == "admin" and not df_i.empty:
            p_edit = st.selectbox("🛠️ Editar producto o corregir código:", ["-- Seleccionar --"] + sorted(df_i['nombre'].tolist()))
            if p_edit != "-- Seleccionar --":
                it = df_i[df_i['nombre'] == p_edit].iloc[0]
                with st.expander("📝 Editar Información", expanded=True):
                    col_e1, col_e2 = st.columns(2)
                    e_nom = col_e1.text_input("Nombre", value=it['nombre'])
                    e_cat = col_e2.selectbox("Categoría", LISTA_CATEGORIAS, index=LISTA_CATEGORIAS.index(it['categoria']) if it['categoria'] in LISTA_CATEGORIAS else 0)
                    e_sub = col_e1.text_input("Subcategoría", value=it.get('subcategoria', ''))
                    e_inv = col_e2.number_input("Inversión ($)", value=float(it['precio_inv']))
                    e_pub = col_e1.number_input("Precio Venta ($)", value=float(it['precio_pub']))
                    e_stk = col_e2.number_input("Stock actual", value=int(it['stock']))

                    if st.button("🔄 Guardar Cambios y Re-generar Código"):
                        seq = it['codigo'].split('-')[-1] if "-" in it['codigo'] else "001"
                        nuevo_c = f"{e_cat[:3].upper()}-{e_sub[:2].upper()}-{e_nom[:3].upper()}-{seq}"
                        
                        upd = {"nombre": e_nom, "categoria": e_cat, "subcategoria": e_sub, "precio_inv": e_inv, "precio_pub": e_pub, "stock": e_stk, "codigo": nuevo_c}
                        supabase.table("productos").update(upd).eq("id", it['id']).execute()
                        st.success(f"✅ ¡Actualizado! Código nuevo: {nuevo_c}")
                        st.rerun()

        st.dataframe(df_i, use_container_width=True, hide_index=True)

    with t_nuevo:
        if role == "admin":
            with st.form("alta_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                n_nom = c1.text_input("Nombre*")
                n_cat = c2.selectbox("Categoría*", LISTA_CATEGORIAS)
                n_sub = c1.text_input("Subcategoría*")
                n_inv = c2.number_input("Costo Inversión")
                n_pub = c1.number_input("Precio Público")
                n_stk = c2.number_input("Stock Inicial", step=1)
                
                if st.form_submit_button("🚀 Crear Producto"):
                    if n_nom and n_sub:
                        res_c = supabase.table("productos").select("id", count="exact").eq("categoria", n_cat).eq("subcategoria", n_sub).execute()
                        n_seq = str((res_c.count or 0) + 1).zfill(3)
                        n_cod = f"{n_cat[:3].upper()}-{n_sub[:2].upper()}-{n_nom[:3].upper()}-{n_seq}"
                        supabase.table("productos").insert({"codigo": n_cod, "nombre": n_nom, "categoria": n_cat, "subcategoria": n_sub, "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk}).execute()
                        st.success(f"Producto creado: {n_cod}")
                        st.rerun()

# --- 6. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes")
    res_v = supabase.table("ventas").select("*").execute()
    if res_v.data:
        df_rep = pd.DataFrame(res_v.data)
        st.metric("Ventas Totales", f"${df_rep['precio_total'].sum():,.2f}")
        st.dataframe(df_rep, use_container_width=True)
