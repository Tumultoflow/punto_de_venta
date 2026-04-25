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

# --- 3. BARRA LATERAL ---
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
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
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
            
            variantes = {}
            if item.get('colores'):
                try:
                    for p in item['colores'].split(','):
                        if ':' in p:
                            c, s = p.split(':')
                            variantes[c.strip()] = int(s.strip())
                except: variantes = {}

            col_v1, col_v2 = st.columns(2)
            with col_v1:
                if item.get('foto_path'): st.image(item['foto_path'], width=350)
            with col_v2:
                color_sel = None
                stock_max = int(item['stock'])
                if variantes:
                    color_sel = st.selectbox("🎨 Color", list(variantes.keys()))
                    stock_max = variantes[color_sel]
                
                precio_v = st.number_input("Precio ($)", value=float(item['precio_pub']))
                cant = st.number_input("Cantidad", 1, max_value=max(1, stock_max))
                
                if st.button("🚀 Confirmar Venta"):
                    nueva_cadena_colores = item['colores']
                    if variantes:
                        variantes[color_sel] -= cant
                        nueva_cadena_colores = ", ".join([f"{k}:{v}" for k, v in variantes.items()])
                    
                    supabase.table("productos").update({"stock": int(item['stock'] - cant), "colores": nueva_cadena_colores}).eq("id", item['id']).execute()
                    detalle = f"{item['nombre']} ({color_sel})" if color_sel else item['nombre']
                    supabase.table("ventas").insert({"fecha_venta": datetime.now(ZONA_LOCAL).strftime("%Y-%m-%d %H:%M:%S"), "producto": detalle, "cantidad": cant, "precio_total": precio_v * cant, "ganancia": (precio_v - item['precio_inv']) * cant if role == "admin" else 0}).execute()
                    st.success(f"Vendido: {detalle}")
                    st.rerun()

# --- 5. INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    t1, t2 = st.tabs(["Registro Nuevo", "Existencias"])
    
    if role == "admin":
        with t1:
            with st.form("f_reg", clear_on_submit=True):
                c1, c2 = st.columns(2)
                cod = c1.text_input("Código")
                nom = c2.text_input("Nombre")
                cat = c1.text_input("Categoría", value="General")
                inv = c2.number_input("Inversión ($)", 0.0)
                pub = c1.number_input("Precio Público ($)", 0.0)
                stk = c2.number_input("Stock Global (si no hay colores)", 0)
                col_input = st.text_input("Colores (Ej: Rojo:5, Azul:10)")
                desc = st.text_area("Descripción")
                foto = st.camera_input("Foto")
                if st.form_submit_button("Guardar"):
                    stock_final = stk
                    if col_input:
                        try: stock_final = sum([int(p.split(':')[1]) for p in col_input.split(',') if ':' in p])
                        except: pass
                    url = ""
                    if foto:
                        fname = f"{cod}.jpg"
                        supabase.storage.from_("fotos").upload(fname, foto.getvalue(), {"content-type":"image/jpeg", "x-upsert":"true"})
                        url = supabase.storage.from_("fotos").get_public_url(fname)
                    supabase.table("productos").insert({"codigo": cod, "nombre": nom, "categoria": cat, "precio_inv": inv, "precio_pub": pub, "stock": stock_final, "descripcion": desc, "foto_path": url, "colores": col_input}).execute()
                    st.success("Guardado")
                    st.rerun()

    with t2:
        res_i = supabase.table("productos").select("*").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            df_i = df_i.fillna("")
            cols = ['id', 'foto_path', 'codigo', 'nombre', 'categoria', 'stock', 'precio_pub', 'colores', 'descripcion']
            
            st.subheader("Lista de Existencias")
            df_editado = st.data_editor(
                df_i[[c for c in cols if c in df_i.columns]],
                column_config={"id": None, "foto_path": st.column_config.ImageColumn("Imagen")},
                hide_index=True, use_container_width=True,
                disabled=True if role == "equipo" else False,
                key="ed_final"
            )

            if role == "admin":
                if st.button("💾 Guardar Cambios en Tabla"):
                    for _, row in df_editado.iterrows():
                        stk_upd = int(row['stock'])
                        if row['colores']:
                            try: stk_upd = sum([int(p.split(':')[1]) for p in row['colores'].split(',') if ':' in p])
                            except: pass
                        supabase.table("productos").update({"codigo": row['codigo'], "nombre": row['nombre'], "categoria": row['categoria'], "stock": stk_upd, "precio_pub": float(row['precio_pub']), "colores": row['colores'], "descripcion": row['descripcion']}).eq("id", row['id']).execute()
                    st.success("Actualizado")
                    st.rerun()

                st.markdown("---")
                # --- RESTAURACIÓN DE EDICIÓN DE IMAGEN Y BORRADO ---
                c_img, c_del = st.columns(2)
                with c_img:
                    st.subheader("🖼️ Actualizar Imagen")
                    p_img = st.selectbox("Producto a cambiar foto", df_i['nombre'], key="sel_img")
                    n_img = st.file_uploader("Nueva foto", type=["jpg", "png", "jpeg"])
                    if st.button("Actualizar Foto Ahora"):
                        if n_img:
                            item = df_i[df_i['nombre'] == p_img].iloc[0]
                            fname = f"{item['codigo']}_{datetime.now().strftime('%H%M%S')}.jpg"
                            supabase.storage.from_("fotos").upload(fname, n_img.getvalue(), {"content-type":"image/jpeg", "x-upsert":"true"})
                            new_url = supabase.storage.from_("fotos").get_public_url(fname)
                            supabase.table("productos").update({"foto_path": new_url}).eq("id", item['id']).execute()
                            st.success("Imagen actualizada")
                            st.rerun()
                with c_del:
                    st.subheader("🗑️ Borrar Producto")
                    p_del = st.selectbox("Producto a eliminar", df_i['nombre'], key="sel_del")
                    conf = st.checkbox(f"Confirmar borrado de {p_del}")
                    if st.button("❌ Eliminar Definitivamente"):
                        if conf:
                            id_b = df_i[df_i['nombre'] == p_del].iloc[0]['id']
                            supabase.table("productos").delete().eq("id", id_b).execute()
                            st.error("Producto eliminado")
                            st.rerun()

# --- 6. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes")
    res_v = supabase.table("ventas").select("*").order("id", desc=True).execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        st.dataframe(df_v, use_container_width=True)
        st.metric("Ventas Totales", f"${df_v['precio_total'].sum():,.2f}")
