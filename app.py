import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import pytz

# --- 1. CONFIGURACIÓN Y CONEXIÓN ---
ZONA_LOCAL = pytz.timezone('America/Mexico_City')

# Credenciales de Supabase
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="TUMULTOFLOW", layout="wide", page_icon="⚖️")

# --- 2. GESTIÓN DE SESIÓN ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acceso Duo Legal")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "admin1":
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "equipo1":
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
    st.stop()

role = st.session_state.role
st.sidebar.subheader(f"👤 Rol: {role.upper()}")
if st.sidebar.button("🚪 CERRAR SESIÓN"):
    st.session_state.auth = False
    st.rerun()

st.sidebar.markdown("---")
menu = st.sidebar.radio("Menú Principal", ["Ventas", "Inventario", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])

# --- 3. SECCIÓN DE VENTAS ---
if menu == "Ventas":
    st.header("💰 Nueva Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).order("nombre").execute()
    
    if res.data:
        df_full = pd.DataFrame(res.data)
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            categorias = ["Todas"] + sorted(df_full['categoria'].unique().tolist())
            cat_sel = st.selectbox("📁 Filtrar por Categoría", categorias)
        with col_f2:
            busqueda_cod = st.text_input("🔍 Buscar por Código")

        df_filtrado = df_full.copy()
        if cat_sel != "Todas": df_filtrado = df_filtrado[df_filtrado['categoria'] == cat_sel]
        if busqueda_cod: df_filtrado = df_filtrado[df_filtrado['codigo'].astype(str).str.contains(busqueda_cod.upper())]

        if not df_filtrado.empty:
            prod_nom = st.selectbox("📦 Seleccionar Producto para Venta", df_filtrado['nombre'])
            item = df_filtrado[df_filtrado['nombre'] == prod_nom].iloc[0]
            
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                if item.get('foto_path'): st.image(item['foto_path'], width=300)
            with col_v2:
                st.subheader(f"{item['nombre']} ({item['codigo']})")
                vendedor_txt = st.text_input("👤 Vendedor")
                metodo_pago = st.selectbox("💳 Método de Pago", ["Efectivo", "Transferencia", "Tarjeta"])
                precio_v = st.number_input("Precio de Venta ($)", value=float(item['precio_pub']))
                cant = st.number_input("Cantidad", 1, max_value=max(1, int(item['stock'])))
                
                if st.button("🚀 Confirmar Venta"):
                    if not vendedor_txt:
                        st.warning("⚠️ Ingresa el nombre del vendedor.")
                    else:
                        # Actualizar Stock
                        supabase.table("productos").update({"stock": int(item['stock'] - cant)}).eq("id", item['id']).execute()
                        # Registrar Venta
                        supabase.table("ventas").insert({
                            "fecha_venta": datetime.now(ZONA_LOCAL).strftime("%Y-%m-%d %H:%M:%S"), 
                            "producto": item['nombre'], "codigo_prod": str(item['codigo']),
                            "vendedor": vendedor_txt, "metodo_pago": metodo_pago,
                            "cantidad": cant, "precio_total": precio_v * cant, 
                            "ganancia": (precio_v - item['precio_inv']) * cant if role == "admin" else 0
                        }).execute()
                        st.success("¡Venta registrada exitosamente!")
                        st.rerun()

# --- 4. SECCIÓN DE INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    
    res_i = supabase.table("productos").select("*").order("categoria").execute()
    df_i = pd.DataFrame(res_i.data).fillna("") if res_i.data else pd.DataFrame()

    tab_lista, tab_nuevo = st.tabs(["📋 Existencias y Edición", "🆕 Registro Nuevo"])

    with tab_lista:
        if role == "admin" and not df_i.empty:
            st.subheader("🛠️ Panel de Edición Rápida")
            opciones_nombres = ["-- Selecciona un producto para gestionar --"] + sorted(df_i['nombre'].tolist())
            prod_seleccionado = st.selectbox("🔍 Buscar producto por nombre:", opciones_nombres)

            if prod_seleccionado != "-- Selecciona un producto para gestionar --":
                item_sel = df_i[df_i['nombre'] == prod_seleccionado].iloc[0]
                
                with st.expander(f"⚙️ Configuración para: {item_sel['nombre']}", expanded=True):
                    c_edit1, c_edit2 = st.columns(2)
                    with c_edit1:
                        st.write("📷 **Actualizar Imagen**")
                        n_img = st.file_uploader("Nueva foto (Sustituye la actual)", type=["jpg", "png"])
                        if st.button("✅ Guardar Nueva Imagen"):
                            if n_img:
                                fname = f"UPD_{item_sel['codigo']}_{datetime.now().strftime('%H%M%S')}.jpg"
                                supabase.storage.from_("fotos").upload(fname, n_img.getvalue(), {"content-type":"image/jpeg"})
                                new_url = supabase.storage.from_("fotos").get_public_url(fname)
                                supabase.table("productos").update({"foto_path": new_url}).eq("id", item_sel['id']).execute()
                                st.success("¡Imagen actualizada!")
                                st.rerun()
                    
                    with c_edit2:
                        st.write("🗑️ **Zona de Peligro**")
                        if st.button("❌ ELIMINAR ESTE PRODUCTO"):
                            supabase.table("productos").delete().eq("id", item_sel['id']).execute()
                            st.warning("Producto borrado de la base de datos.")
                            st.rerun()
            st.markdown("---")

        # Visualización de la Tabla
        st.subheader("📋 Inventario Actual")
        if not df_i.empty:
            # Ordenamos las columnas según tu preferencia
            cols_admin = ['foto_path', 'codigo', 'nombre', 'categoria', 'subcategoria', 'colores', 'stock', 'precio_pub', 'precio_inv', 'id']
            cols_equipo = ['foto_path', 'codigo', 'nombre', 'categoria', 'subcategoria', 'colores', 'stock', 'precio_pub']
            
            columnas_finales = [c for c in (cols_admin if role == "admin" else cols_equipo) if c in df_i.columns]
            
            st.data_editor(
                df_i[columnas_finales],
                column_config={
                    "foto_path": st.column_config.ImageColumn("Imagen"),
                    "precio_inv": st.column_config.NumberColumn("Costo ($)", format="$%.2f"),
                    "precio_pub": st.column_config.NumberColumn("Venta ($)", format="$%.2f"),
                    "id": None # Ocultamos el ID interno
                },
                hide_index=True,
                use_container_width=True,
                disabled=True # Deshabilitado para forzar uso del panel de arriba o edición por Excel
            )
        else:
            st.info("No hay productos en el inventario.")

    if role == "admin":
        with tab_nuevo:
            st.subheader("🆕 Alta de Producto con Código Automático")
            with st.form("f_nuevo", clear_on_submit=True):
                col1, col2 = st.columns(2)
                nombre_n = col1.text_input("Nombre del Producto*")
                cat_n = col2.selectbox("Categoría*", ["HOGAR", "ELECTRÓNICA", "PAPELERÍA", "BELLEZA", "MODA", "DEPORTES", "HERRAMIENTAS"])
                sub_n = col1.text_input("Subcategoría* (Ej: Cocina, Oficina)")
                
                inv_n = col2.number_input("Inversión ($)", 0.0)
                pub_n = col1.number_input("Precio Venta ($)", 0.0)
                stk_n = col2.number_input("Existencia Inicial", 0)
                
                colores_n = col1.text_input("Colores/Variantes", placeholder="Azul:5, Verde:3")
                desc_n = st.text_area("Descripción corta")
                foto_n = st.camera_input("Capturar Foto")

                if st.form_submit_button("🚀 Registrar Producto"):
                    if not nombre_n or not sub_n:
                        st.error("⚠️ El Nombre y la Subcategoría son obligatorios para generar el código.")
                    else:
                        # 1. GENERAR SECUENCIA (Count en Supabase)
                        res_count = supabase.table("productos").select("id", count="exact").eq("categoria", cat_n).eq("subcategoria", sub_n).execute()
                        num = (res_count.count if res_count.count is not None else 0) + 1
                        secuencia = str(num).zfill(3)

                        # 2. CONSTRUIR CÓDIGO: CAT(3)-SUB(2)-NOM(3)-SEQ(3)
                        cod_auto = f"{cat_n[:3].upper()}-{sub_n[:2].upper()}-{nombre_n[:3].upper()}-{secuencia}"

                        # 3. SUBIR FOTO
                        url_f = ""
                        if foto_n:
                            f_name = f"{cod_auto}.jpg"
                            supabase.storage.from_("fotos").upload(f_name, foto_n.getvalue(), {"content-type":"image/jpeg", "x-upsert":"true"})
                            url_f = supabase.storage.from_("fotos").get_public_url(f_name)

                        # 4. INSERTAR
                        supabase.table("productos").insert({
                            "codigo": cod_auto, "nombre": nombre_n, "categoria": cat_n, 
                            "subcategoria": sub_n, "precio_inv": inv_n, "precio_pub": pub_n, 
                            "stock": stk_n, "foto_path": url_f, "colores": colores_n, "descripcion": desc_n
                        }).execute()
                        
                        st.success(f"✅ ¡Producto Guardado! Código: {cod_auto}")
                        st.rerun()

# --- 5. SECCIÓN DE REPORTES ---
elif menu == "Reportes":
    st.header("📊 Análisis de Ventas")
    res_v = supabase.table("ventas").select("*").order("id", desc=True).execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        st.dataframe(df_v, use_container_width=True, hide_index=True)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Venta Total", f"${df_v['precio_total'].sum():,.2f}")
        c2.metric("Ganancia Est.", f"${df_v['ganancia'].sum():,.2f}")
        c3.metric("Unidades Vendidas", int(df_v['cantidad'].sum()))
