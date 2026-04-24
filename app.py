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
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df = pd.DataFrame(res.data)
        prod = st.selectbox("Seleccionar Producto", df['nombre'])
        item = df[df['nombre'] == prod].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            if item.get('foto_path'): st.image(item['foto_path'], width=300)
        with col2:
            ahora_local = datetime.now(ZONA_LOCAL)
            fecha_v = ahora_local.strftime("%Y-%m-%d %H:%M:%S")
            st.info(f"📅 Fecha y Hora Local: {fecha_v}")
            precio_v = st.number_input("Precio de Venta ($)", value=float(item['precio_pub']))
            cant = st.number_input("Cantidad", 1, int(item['stock']))
            
            if st.button("Confirmar Venta"):
                ganancia = (precio_v - item['precio_inv']) * cant
                supabase.table("productos").update({"stock": int(item['stock']-cant)}).eq("id", item['id']).execute()
                supabase.table("ventas").insert({
                    "fecha_venta": fecha_v, "producto": item['nombre'], "cantidad": cant,
                    "precio_total": precio_v * cant, "ganancia": ganancia if role == "admin" else 0
                }).execute()
                st.success("✅ Venta registrada")
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
                inv = c1.number_input("Costo Inversión ($)", 0.0)
                pub = c2.number_input("Precio Público ($)", 0.0)
                stk = c1.number_input("Stock Inicial", 0)
                f_ing = st.date_input("Fecha de Ingreso", datetime.now(ZONA_LOCAL))
                desc = st.text_area("Descripción")
                foto = st.camera_input("Foto")
                if st.form_submit_button("Guardar Producto"):
                    url = ""
                    if foto:
                        fname = f"{cod}.jpg"
                        supabase.storage.from_("fotos").upload(fname, foto.getvalue(), {"content-type":"image/jpeg", "x-upsert":"true"})
                        url = supabase.storage.from_("fotos").get_public_url(fname)
                    supabase.table("productos").insert({
                        "codigo": cod, "nombre": nom, "precio_inv": inv, "precio_pub": pub,
                        "stock": stk, "descripcion": desc, "fecha_ingreso": str(f_ing), "foto_path": url
                    }).execute()
                    st.success("Registrado")
                    st.rerun()
    
    with t2:
        res_i = supabase.table("productos").select("*").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            if 'fecha_ingreso' in df_i.columns:
                df_i['fecha_ingreso'] = df_i['fecha_ingreso'].fillna("Sin fecha")
            
            if role == "admin":
                cols = ['id', 'foto_path', 'codigo', 'nombre', 'stock', 'precio_pub', 'precio_inv', 'fecha_ingreso', 'descripcion']
            else:
                cols = ['foto_path', 'codigo', 'nombre', 'stock', 'precio_pub', 'fecha_ingreso', 'descripcion']
            
            st.subheader("Lista de Existencias")
            df_editado = st.data_editor(
                df_i[[c for c in cols if c in df_i.columns]],
                column_config={
                    "id": None,
                    "foto_path": st.column_config.ImageColumn("Imagen", width="small"),
                    "fecha_ingreso": st.column_config.TextColumn("Fecha Ingreso"),
                },
                hide_index=True, use_container_width=True,
                disabled=True if role == "equipo" else False,
                key="editor_existencias"
            )

            if role == "admin":
                if st.button("💾 Guardar Cambios de Texto/Stock"):
                    for _, row in df_editado.iterrows():
                        upd = {"codigo": row['codigo'], "nombre": row['nombre'], "stock": int(row['stock']), "precio_pub": float(row['precio_pub']), "descripcion": row['descripcion'], "fecha_ingreso": str(row['fecha_ingreso'])}
                        if 'precio_inv' in row: upd["precio_inv"] = float(row['precio_inv'])
                        supabase.table("productos").update(upd).eq("id", row['id']).execute()
                    st.success("Sincronizado")
                    st.rerun()

                st.markdown("---")
                
                # SECCIÓN DE CAMBIO DE IMAGEN Y BORRADO
                col_img, col_del = st.columns(2)
                
                with col_img:
                    st.subheader("🖼️ Cambiar Imagen")
                    p_img = st.selectbox("Producto a modificar foto", df_i['nombre'])
                    n_img = st.file_uploader("Nueva foto", type=["jpg", "png", "jpeg"])
                    if st.button("🚀 Actualizar Foto"):
                        if n_img:
                            item = df_i[df_i['nombre'] == p_img].iloc[0]
                            fname = f"{item['codigo']}_{datetime.now().strftime('%H%M%S')}.jpg"
                            supabase.storage.from_("fotos").upload(fname, n_img.getvalue(), {"content-type":"image/jpeg", "x-upsert":"true"})
                            new_url = supabase.storage.from_("fotos").get_public_url(fname)
                            supabase.table("productos").update({"foto_path": new_url}).eq("id", item['id']).execute()
                            st.success("Imagen actualizada")
                            st.rerun()

                with col_del:
                    st.subheader("🗑️ Borrar Producto")
                    st.warning("Esta acción eliminará el producto permanentemente.")
                    p_del = st.selectbox("Producto a eliminar", df_i['nombre'])
                    check_del = st.checkbox(f"Confirmar que deseo borrar '{p_del}'")
                    if st.button("❌ Eliminar Producto"):
                        if check_del:
                            id_borrar = df_i[df_i['nombre'] == p_del].iloc[0]['id']
                            supabase.table("productos").delete().eq("id", id_borrar).execute()
                            st.error(f"Producto '{p_del}' eliminado.")
                            st.rerun()
                        else:
                            st.info("Por favor, marca la casilla de confirmación para borrar.")

# --- 6. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        df_v['fecha_solo'] = pd.to_datetime(df_v['fecha_venta']).dt.date
        c_f1, c_f2 = st.columns(2)
        filtro = c_f1.selectbox("Ver:", ["Completo", "Por Día"])
        if filtro == "Por Día":
            dia = c_f2.date_input("Día", datetime.now(ZONA_LOCAL))
            df_v = df_v[df_v['fecha_solo'] == dia]
        
        st.dataframe(df_v.drop(columns=['fecha_solo']), use_container_width=True)
        st.metric("Ventas Totales", f"${df_v['precio_total'].sum():,.2f}")
