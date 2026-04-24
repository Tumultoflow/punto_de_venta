import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- 1. CONEXIÓN ---
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="TUMULTOFLOW", layout="wide", page_icon="⚖️")

if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acceso Duo")
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
        prod = st.selectbox("Producto", df['nombre'])
        item = df[df['nombre'] == prod].iloc[0]
        col1, col2 = st.columns(2)
        with col1:
            if item.get('foto_path'): st.image(item['foto_path'], width=300)
        with col2:
            fecha_v = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.info(f"📅 Fecha: {fecha_v}")
            precio_v = st.number_input("Precio ($)", value=float(item['precio_pub']))
            cant = st.number_input("Cantidad", 1, int(item['stock']))
            if st.button("Confirmar Venta"):
                ganancia = (precio_v - item['precio_inv']) * cant
                supabase.table("productos").update({"stock": int(item['stock']-cant)}).eq("id", item['id']).execute()
                supabase.table("ventas").insert({
                    "fecha_venta": fecha_v, "producto": item['nombre'], "cantidad": cant,
                    "precio_total": precio_v * cant, "ganancia": ganancia if role == "admin" else 0
                }).execute()
                st.success("¡Venta Exitosa!")
                st.rerun()

# --- 5. INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    t1, t2 = st.tabs(["Registro", "Existencias"])
    
    if role == "admin":
        with t1:
            with st.form("f_reg", clear_on_submit=True):
                c1, c2 = st.columns(2)
                cod = c1.text_input("Código")
                nom = c2.text_input("Nombre")
                inv = c1.number_input("Inversión", 0.0); pub = c2.number_input("Público", 0.0)
                stk = c1.number_input("Stock", 0); f_ing = st.date_input("Fecha", datetime.now())
                desc = st.text_area("Descripción"); foto = st.camera_input("Foto")
                if st.form_submit_button("Guardar"):
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
    
    with t2:
        res_i = supabase.table("productos").select("*").execute()
        if res_i.data:
            df_original = pd.DataFrame(res_i.data)
            # Orden: Foto, Código, Nombre, Stock, Venta, (Costo solo admin), Ingreso, Descripción
            if role == "admin":
                cols_vista = ['id', 'foto_path', 'codigo', 'nombre', 'stock', 'precio_pub', 'precio_inv', 'fecha_ingreso', 'descripcion']
            else:
                cols_vista = ['foto_path', 'codigo', 'nombre', 'stock', 'precio_pub', 'fecha_ingreso', 'descripcion']
            
            cols_disponibles = [c for c in cols_vista if c in df_original.columns]
            
            st.subheader("Lista de Existencias")
            df_editado = st.data_editor(
                df_original[cols_disponibles],
                column_config={
                    "id": None,
                    "foto_path": st.column_config.ImageColumn("Imagen"),
                    "descripcion": st.column_config.TextColumn("Descripción", width="large")
                },
                hide_index=True,
                use_container_width=True,
                disabled=False if role == "admin" else True,
                key="editor_existencias"
            )

            if role == "admin":
                if st.button("💾 Guardar Cambios en Tabla"):
                    for index, row in df_editado.iterrows():
                        actualizacion = {
                            "codigo": row['codigo'], "nombre": row['nombre'],
                            "stock": int(row['stock']), "precio_pub": float(row['precio_pub']),
                            "descripcion": row['descripcion']
                        }
                        if 'precio_inv' in row: actualizacion["precio_inv"] = float(row['precio_inv'])
                        supabase.table("productos").update(actualizacion).eq("id", row['id']).execute()
                    st.success("¡Cambios guardados!")
                    st.rerun()

                st.markdown("---")
                st.subheader("🖼️ Cambiar Imagen")
                prod_edit = st.selectbox("Producto para foto", df_original['nombre'])
                nueva_foto = st.file_uploader("Nueva imagen", type=["jpg", "png", "jpeg"])
                if st.button("Confirmar Imagen"):
                    if nueva_foto:
                        item = df_original[df_original['nombre'] == prod_edit].iloc[0]
                        fname = f"{item['codigo']}_{datetime.now().strftime('%H%M%S')}.jpg"
                        supabase.storage.from_("fotos").upload(fname, nueva_foto.getvalue(), {"content-type":"image/jpeg", "x-upsert":"true"})
                        new_url = supabase.storage.from_("fotos").get_public_url(fname)
                        supabase.table("productos").update({"foto_path": new_url}).eq("id", item['id']).execute()
                        st.success("Imagen actualizada.")
                        st.rerun()

# --- 6. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes de Ventas")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        df_v['fecha_solo'] = pd.to_datetime(df_v['fecha_venta']).dt.date
        col_f1, col_f2 = st.columns(2)
        tipo = col_f1.selectbox("Filtro", ["Completo", "Por Día"])
        if tipo == "Por Día":
            f_busq = col_f2.date_input("Fecha", datetime.now())
            df_v = df_v[df_v['fecha_solo'] == f_busq]
        
        st.dataframe(df_v.drop(columns=['fecha_solo']), use_container_width=True)
        
        # Anulación
        st.markdown("---")
        st.subheader("🛑 Anulación")
        if not df_v.empty:
            opc = df_v['id'].astype(str) + " - " + df_v['producto']
            v_anular = st.selectbox("Venta a borrar", opc)
            if st.button("Anular"):
                id_v = int(v_anular.split(" - ")[0])
                v_sel = df_v[df_v['id'] == id_v].iloc[0]
                p_res = supabase.table("productos").select("stock").eq("nombre", v_sel['producto']).execute()
                if p_res.data:
                    n_stk = int(p_res.data[0]['stock']) + int(v_sel['cantidad'])
                    supabase.table("productos").update({"stock": n_stk}).eq("nombre", v_sel['producto']).execute()
                    supabase.table("ventas").delete().eq("id", id_v).execute()
                    st.warning("Venta anulada.")
                    st.rerun()
