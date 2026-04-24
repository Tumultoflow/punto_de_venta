import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- 1. CONEXIÓN ---
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
        df = pd.DataFrame(res.data)
        prod = st.selectbox("Seleccionar Producto", df['nombre'])
        item = df[df['nombre'] == prod].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            if item.get('foto_path'): st.image(item['foto_path'], width=300)
        with col2:
            fecha_v = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.info(f"📅 Fecha de Venta: {fecha_v}")
            precio_v = st.number_input("Precio de Venta ($)", value=float(item['precio_pub']))
            cant = st.number_input("Cantidad", 1, int(item['stock']))
            
            if st.button("Confirmar Venta"):
                ganancia = (precio_v - item['precio_inv']) * cant
                # Actualizar stock
                supabase.table("productos").update({"stock": int(item['stock']-cant)}).eq("id", item['id']).execute()
                # Registrar venta
                supabase.table("ventas").insert({
                    "fecha_venta": fecha_v, "producto": item['nombre'], "cantidad": cant,
                    "precio_total": precio_v * cant, "ganancia": ganancia if role == "admin" else 0
                }).execute()
                st.success("✅ Venta registrada con éxito")
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
                f_ing = st.date_input("Fecha de Ingreso", datetime.now())
                desc = st.text_area("Descripción")
                foto = st.camera_input("Foto del producto")
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
                    st.success("Producto registrado")
                    st.rerun()

    with t2:
        res_i = supabase.table("productos").select("*").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            # Rellenar fechas vacías para que no desaparezca la columna
            if 'fecha_ingreso' in df_i.columns:
                df_i['fecha_ingreso'] = df_i['fecha_ingreso'].fillna("Sin fecha")
            
            # Definir columnas por rol
            if role == "admin":
                cols = ['id', 'foto_path', 'codigo', 'nombre', 'stock', 'precio_pub', 'precio_inv', 'fecha_ingreso', 'descripcion']
            else:
                cols = ['foto_path', 'codigo', 'nombre', 'stock', 'precio_pub', 'fecha_ingreso', 'descripcion']
            
            st.subheader("Lista de Existencias")
            df_editado = st.data_editor(
                df_i[[c for c in cols if c in df_i.columns]],
                column_config={
                    "id": None,
                    "foto_path": st.column_config.ImageColumn("Imagen"),
                    "fecha_ingreso": st.column_config.TextColumn("Fecha Ingreso"),
                    "descripcion": st.column_config.TextColumn("Descripción", width="medium")
                },
                hide_index=True, use_container_width=True,
                disabled=True if role == "equipo" else False,
                key="editor_existencias_final"
            )

            if role == "admin":
                if st.button("💾 Guardar Cambios en Tabla"):
                    for _, row in df_editado.iterrows():
                        upd = {
                            "codigo": row['codigo'], "nombre": row['nombre'],
                            "stock": int(row['stock']), "precio_pub": float(row['precio_pub']),
                            "descripcion": row['descripcion'], "fecha_ingreso": str(row['fecha_ingreso'])
                        }
                        if 'precio_inv' in row: upd["precio_inv"] = float(row['precio_inv'])
                        supabase.table("productos").update(upd).eq("id", row['id']).execute()
                    st.success("Base de datos actualizada")
                    st.rerun()

                st.markdown("---")
                st.subheader("🖼️ Actualizar Imagen")
                p_img = st.selectbox("Selecciona producto", df_i['nombre'])
                n_img = st.file_uploader("Subir imagen nueva", type=["jpg", "png", "jpeg"])
                if st.button("Cambiar Foto Ahora"):
                    if n_img:
                        item = df_i[df_i['nombre'] == p_img].iloc[0]
                        fname = f"{item['codigo']}_{datetime.now().strftime('%H%M%S')}.jpg"
                        supabase.storage.from_("fotos").upload(fname, n_img.getvalue(), {"content-type":"image/jpeg", "x-upsert":"true"})
                        new_url = supabase.storage.from_("fotos").get_public_url(fname)
                        supabase.table("productos").update({"foto_path": new_url}).eq("id", item['id']).execute()
                        st.success("Imagen actualizada correctamente")
                        st.rerun()

# --- 6. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes de Ventas")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        df_v['fecha_solo'] = pd.to_datetime(df_v['fecha_venta']).dt.date
        
        c_f1, c_f2 = st.columns(2)
        filtro = c_f1.selectbox("Ver reporte:", ["Completo", "Por Día Específico"])
        if filtro == "Por Día Específico":
            dia = c_f2.date_input("Selecciona el día", datetime.now())
            df_v = df_v[df_v['fecha_solo'] == dia]
        
        st.dataframe(df_v.drop(columns=['fecha_solo']), use_container_width=True)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Ventas", f"${df_v['precio_total'].sum():,.2f}")
        m2.metric("Ganancia", f"${df_v['ganancia'].sum():,.2f}")
        m3.metric("Unidades", f"{df_v['cantidad'].sum()}")

        st.markdown("---")
        st.subheader("🛑 Anulación de Ventas")
        if not df_v.empty:
            sel_v = st.selectbox("Venta a anular", df_v['id'].astype(str) + " - " + df_v['producto'])
            if st.button("Eliminar Venta y Devolver Stock"):
                id_v = int(sel_v.split(" - ")[0])
                v_sel = df_v[df_v['id'] == id_v].iloc[0]
                # Devolver stock
                p_res = supabase.table("productos").select("stock").eq("nombre", v_sel['producto']).execute()
                if p_res.data:
                    n_stk = int(p_res.data[0]['stock']) + int(v_sel['cantidad'])
                    supabase.table("productos").update({"stock": n_stk}).eq("nombre", v_sel['producto']).execute()
                    supabase.table("ventas").delete().eq("id", id_v).execute()
                    st.warning("Venta anulada con éxito")
                    st.rerun()
