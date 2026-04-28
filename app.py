import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import pytz

# --- 1. CONFIGURACIÓN Y CONEXIÓN ---
ZONA_LOCAL = pytz.timezone('America/Mexico_City')

SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="TUMULTOFLOW", layout="wide", page_icon="⚖️")

# --- 2. GESTIÓN DE SESIÓN ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acceso")
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
st.sidebar.error(f"👤 Sesión: {role.upper()}")
if st.sidebar.button("🚪 CERRAR SESIÓN"):
    st.session_state.auth = False
    st.rerun()

st.sidebar.markdown("---")
menu = st.sidebar.radio("Navegación", ["Ventas", "Inventario", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])

# --- 4. VENTAS ---
if menu == "Ventas":
    st.header("💰 Nueva Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).order("nombre").execute()
    if res.data:
        df_full = pd.DataFrame(res.data)
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            categorias = ["Todas"] + sorted(df_full['categoria'].unique().tolist()) if 'categoria' in df_full.columns else ["Todas"]
            cat_sel = st.selectbox("📁 Filtrar por Categoría", categorias)
        with col_f2:
            busqueda_cod = st.text_input("🔍 Buscar por Código")

        df_filtrado = df_full.copy()
        if cat_sel != "Todas": df_filtrado = df_filtrado[df_filtrado['categoria'] == cat_sel]
        if busqueda_cod: df_filtrado = df_filtrado[df_filtrado['codigo'].astype(str).str.contains(busqueda_cod)]

        if not df_filtrado.empty:
            prod_nom = st.selectbox("📦 Seleccionar Producto", df_filtrado['nombre'])
            item = df_filtrado[df_filtrado['nombre'] == prod_nom].iloc[0]
            
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                if item.get('foto_path'): st.image(item['foto_path'], width=350)
            with col_v2:
                st.subheader(item['nombre'])
                vendedor_txt = st.text_input("👤 Nombre del Vendedor")
                metodo_pago = st.selectbox("💳 Método de Pago", ["Efectivo", "Transferencia", "Tarjeta"])
                
                variantes = {}
                if item.get('colores'):
                    try:
                        for p in item['colores'].split(','):
                            if ':' in p:
                                c, s = p.split(':')
                                variantes[c.strip()] = int(s.strip())
                    except: variantes = {}

                color_sel = None
                stock_max = int(item['stock'])
                if variantes:
                    color_sel = st.selectbox("🎨 Color", list(variantes.keys()))
                    stock_max = variantes[color_sel]
                
                precio_v = st.number_input("Precio ($)", value=float(item['precio_pub']))
                cant = st.number_input("Cantidad", 1, max_value=max(1, stock_max))
                
                if st.button("🚀 Confirmar Venta"):
                    if not vendedor_txt:
                        st.warning("⚠️ Ingresa el nombre del vendedor.")
                    else:
                        nueva_cadena_colores = item['colores']
                        if variantes:
                            variantes[color_sel] -= cant
                            nueva_cadena_colores = ", ".join([f"{k}:{v}" for k, v in variantes.items()])
                        
                        supabase.table("productos").update({"stock": int(item['stock'] - cant), "colores": nueva_cadena_colores}).eq("id", item['id']).execute()
                        detalle = f"{item['nombre']} ({color_sel})" if color_sel else item['nombre']
                        supabase.table("ventas").insert({
                            "fecha_venta": datetime.now(ZONA_LOCAL).strftime("%Y-%m-%d %H:%M:%S"), 
                            "producto": detalle, "codigo_prod": str(item['codigo']),
                            "vendedor": vendedor_txt, "metodo_pago": metodo_pago,
                            "cantidad": cant, "precio_total": precio_v * cant, 
                            "ganancia": (precio_v - item['precio_inv']) * cant if role == "admin" else 0
                        }).execute()
                        st.success("¡Venta registrada!")
                        st.rerun()

# --- 5. INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    
    res_i = supabase.table("productos").select("*").order("codigo").execute()
    df_i = pd.DataFrame(res_i.data).fillna("") if res_i.data else pd.DataFrame()

    t_exist, t_reg = st.tabs(["Existencias", "Registro Nuevo"])

    with t_exist:
        st.subheader("📋 Lista de Existencias")
        
        if role == "admin":
            cols_to_show = ['id', 'foto_path', 'codigo', 'nombre', 'categoria', 'stock', 'precio_pub', 'precio_inv', 'colores', 'descripcion']
            # CONFIGURACIÓN DE SELECCIÓN EXPLÍCITA
            selection_mode = "single_row" 
        else:
            cols_to_show = ['foto_path', 'codigo', 'nombre', 'categoria', 'stock', 'precio_pub', 'colores']
            selection_mode = None

        # TABLA CON DETECTOR DE SELECCIÓN
        df_editado = st.data_editor(
            df_i[[c for c in cols_to_show if c in df_i.columns]],
            column_config={
                "id": None, 
                "foto_path": st.column_config.ImageColumn("Imagen"),
                "precio_inv": st.column_config.NumberColumn("Inv ($)", format="$%.2f"),
                "precio_pub": st.column_config.NumberColumn("Pub ($)", format="$%.2f")
            },
            hide_index=False,
            use_container_width=True,
            disabled=True if role == "equipo" else False,
            key="editor_central"
        )

        # Lógica de captura de selección corregida
        selected_rows = []
        if "editor_central" in st.session_state:
            # Intentamos obtener la selección de las dos formas posibles en Streamlit
            selection_data = st.session_state["editor_central"].get("selection", {})
            selected_rows = selection_data.get("rows", [])

        if role == "admin":
            if st.button("💾 Guardar cambios de edición rápida"):
                for idx, row in df_editado.iterrows():
                    upd_data = {
                        "codigo": row['codigo'], "nombre": row['nombre'], "categoria": row['categoria'], 
                        "stock": int(row['stock']), "precio_pub": float(row['precio_pub']), 
                        "precio_inv": float(row['precio_inv']), "colores": row['colores'], "descripcion": row['descripcion']
                    }
                    supabase.table("productos").update(upd_data).eq("id", row['id']).execute()
                st.success("Cambios guardados.")
                st.rerun()

            # PANEL DE ACCIONES
            if selected_rows:
                st.markdown("---")
                idx_sel = selected_rows[0]
                item_sel = df_i.iloc[idx_sel]
                
                st.info(f"📍 Producto seleccionado: **{item_sel['nombre']}**")
                
                c_act1, c_act2 = st.columns(2)
                with c_act1:
                    st.write("📷 **Cambiar Imagen**")
                    n_img = st.file_uploader("Nueva foto", type=["jpg", "png"], key="up_img")
                    if st.button("🚀 Actualizar Foto"):
                        if n_img:
                            fname = f"{item_sel['codigo']}_{datetime.now().strftime('%H%M%S')}.jpg"
                            supabase.storage.from_("fotos").upload(fname, n_img.getvalue(), {"content-type":"image/jpeg"})
                            new_url = supabase.storage.from_("fotos").get_public_url(fname)
                            supabase.table("productos").update({"foto_path": new_url}).eq("id", item_sel['id']).execute()
                            st.success("Imagen actualizada.")
                            st.rerun()
                
                with c_act2:
                    st.write("🗑️ **Eliminar Registro**")
                    if st.button("❌ Borrar Producto Permanentemente"):
                        supabase.table("productos").delete().eq("id", item_sel['id']).execute()
                        st.error("Producto eliminado.")
                        st.rerun()
            else:
                st.warning("👈 Selecciona una fila haciendo clic en el número del índice o en el círculo a la izquierda para ver opciones de borrado.")

    if role == "admin":
        with t_reg:
            st.subheader("🆕 Registrar Producto")
            with st.form("f_reg", clear_on_submit=True):
                c1, c2 = st.columns(2)
                cod = c1.text_input("Código")
                nom = c2.text_input("Nombre")
                cat = c1.selectbox("Categoría", ["ELECTRÓNICA", "HERRAMIENTAS", "HOGAR", "PAPELERÍA", "BELLEZA Y SALUD", "MODA Y ACCESORIOS", "DEPORTES", "JUGUETES", "MASCOTAS"])
                inv = c1.number_input("Costo Inversión", 0.0)
                pub = c2.number_input("Precio Público", 0.0)
                stk = c1.number_input("Cantidad inicial", 0)
                col_input = c2.text_input("Variantes (Ej: Rojo:5, Azul:10)")
                desc = st.text_area("Descripción")
                foto = st.camera_input("Foto")
                if st.form_submit_button("Guardar Producto"):
                    stock_f = stk
                    if col_input:
                        try: stock_f = sum([int(p.split(':')[1]) for p in col_input.split(',') if ':' in p])
                        except: pass
                    url = ""
                    if foto:
                        fname = f"{cod}.jpg"
                        supabase.storage.from_("fotos").upload(fname, foto.getvalue(), {"content-type":"image/jpeg", "x-upsert":"true"})
                        url = supabase.storage.from_("fotos").get_public_url(fname)
                    supabase.table("productos").insert({
                        "codigo": cod, "nombre": nom, "categoria": cat, "precio_inv": inv, 
                        "precio_pub": pub, "stock": stock_f, "descripcion": desc, 
                        "foto_path": url, "colores": col_input
                    }).execute()
                    st.success("¡Producto Guardado!")
                    st.rerun()

# --- 6. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes de Ventas")
    res_v = supabase.table("ventas").select("*").order("id", desc=True).execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data).fillna("---")
        cols_rep = ['id', 'fecha_venta', 'vendedor', 'metodo_pago', 'codigo_prod', 'producto', 'cantidad', 'precio_total', 'ganancia']
        df_m = df_v[[c for c in cols_rep if c in df_v.columns]]
        st.dataframe(df_m, use_container_width=True, hide_index=True)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Venta Total", f"${df_v['precio_total'].astype(float).sum():,.2f}")
        if 'ganancia' in df_v.columns:
            c2.metric("Ganancia", f"${df_v['ganancia'].astype(float).sum():,.2f}")
        c3.metric("Unidades Vendidas", int(df_v['cantidad'].astype(float).sum()))
