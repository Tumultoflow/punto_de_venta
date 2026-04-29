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

# --- 2. FUNCIONES DE BASE DE DATOS ---
def obtener_categorias():
    try:
        res = supabase.table("configuracion").select("valor").eq("tipo", "categoria").execute()
        cats = [r['valor'] for r in res.data]
        return sorted(cats) if cats else ["GENERAL"]
    except:
        return ["GENERAL"]

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
menu = st.sidebar.radio("Menú", ["Ventas", "Inventario", "Configuración", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])

# --- 4. VENTAS ---
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
            st.info(f"Código: {item['codigo']} | Existencia: {item['stock']}")
        with c2:
            v_precio = st.number_input("💵 Precio Final (Editable)", value=float(item['precio_pub']))
            v_fecha = st.date_input("📅 Fecha", datetime.now(ZONA_LOCAL))
            v_cant = st.number_input("Cantidad", 1, int(item['stock']))
            v_vendedor = st.text_input("👤 Vendedor")
            if st.button("🚀 Confirmar Venta"):
                supabase.table("productos").update({"stock": int(item['stock'] - v_cant)}).eq("id", item['id']).execute()
                supabase.table("ventas").insert({
                    "producto": item['nombre'], "codigo_prod": item['codigo'],
                    "cantidad": v_cant, "precio_total": v_precio * v_cant,
                    "fecha_venta": v_fecha.isoformat(), "vendedor": v_vendedor,
                    "ganancia": (v_precio - item['precio_inv']) * v_cant
                }).execute()
                st.success("Venta guardada")
                st.rerun()

# --- 5. INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    res_i = supabase.table("productos").select("*").order("categoria").execute()
    df_i = pd.DataFrame(res_i.data) if res_i.data else pd.DataFrame()
    lista_cats = obtener_categorias()

    t_lista, t_nuevo = st.tabs(["📋 Existencias", "🆕 Nuevo Producto"])

    with t_lista:
        if role == "admin" and not df_i.empty:
            p_sel = st.selectbox("🛠️ Gestionar Producto:", ["-- Seleccionar --"] + sorted(df_i['nombre'].tolist()))
            if p_sel != "-- Seleccionar --":
                it = df_i[df_i['nombre'] == p_sel].iloc[0]
                with st.expander("📝 Editar Información / Eliminar", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        e_nom = st.text_input("Nombre", value=it['nombre'])
                        e_cat = st.selectbox("Categoría", lista_cats, index=lista_cats.index(it['categoria']) if it['categoria'] in lista_cats else 0)
                        e_sub = st.text_input("Subcategoría", value=it.get('subcategoria', ''))
                        e_col = st.text_input("Colores", value=it.get('colores', ''))
                        if st.button("💾 Guardar Cambios"):
                            seq = it['codigo'].split('-')[-1] if "-" in it['codigo'] else "001"
                            n_cod = f"{e_cat[:3].upper()}-{e_sub[:2].upper()}-{e_nom[:3].upper()}-{seq}"
                            supabase.table("productos").update({
                                "nombre": e_nom, "categoria": e_cat, 
                                "subcategoria": e_sub, "colores": e_col, "codigo": n_cod
                            }).eq("id", it['id']).execute()
                            st.rerun()
                    with col2:
                        nueva_img = st.file_uploader("Actualizar Imagen", type=["jpg", "png"])
                        if st.button("🖼️ Guardar Foto"):
                            if nueva_img:
                                fname = f"PROD_{it['id']}.jpg"
                                supabase.storage.from_("fotos").upload(fname, nueva_img.getvalue(), {"x-upsert":"true"})
                                url = supabase.storage.from_("fotos").get_public_url(fname)
                                supabase.table("productos").update({"foto_path": url}).eq("id", it['id']).execute()
                                st.rerun()
                        if st.button("🗑️ ELIMINAR PRODUCTO"):
                            supabase.table("productos").delete().eq("id", it['id']).execute()
                            st.rerun()

        # ORDEN DE COLUMNAS SOLICITADO
        st.data_editor(
            df_i,
            column_order=("foto_path", "codigo", "stock", "categoria", "subcategoria", "colores", "precio_inv", "precio_pub", "nombre"),
            column_config={
                "foto_path": st.column_config.ImageColumn("Imagen"),
                "codigo": "Código",
                "stock": "Stock",
                "categoria": "Categoría",
                "subcategoria": "Subcategoría",
                "colores": "Colores",
                "precio_inv": st.column_config.NumberColumn("Costo Inversión", format="$%.2f"),
                "precio_pub": st.column_config.NumberColumn("Precio Público", format="$%.2f"),
                "nombre": "Nombre del Producto"
            },
            use_container_width=True,
            hide_index=True
        )

    with t_nuevo:
        if role == "admin":
            with st.form("nuevo_p"):
                c1, c2 = st.columns(2)
                n_nom = c1.text_input("Nombre*")
                n_cat = c2.selectbox("Categoría*", lista_cats)
                n_sub = c1.text_input("Subcategoría*")
                n_col = c2.text_input("Colores")
                n_inv = c1.number_input("Inversión")
                n_pub = c2.number_input("Público")
                n_stk = c1.number_input("Stock", step=1)
                if st.form_submit_button("🚀 Crear"):
                    res_c = supabase.table("productos").select("id", count="exact").eq("categoria", n_cat).eq("subcategoria", n_sub).execute()
                    n_seq = str((res_c.count or 0) + 1).zfill(3)
                    n_cod = f"{n_cat[:3].upper()}-{n_sub[:2].upper()}-{n_nom[:3].upper()}-{n_seq}"
                    supabase.table("productos").insert({
                        "codigo": n_cod, "nombre": n_nom, "categoria": n_cat, 
                        "subcategoria": n_sub, "colores": n_col, 
                        "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk
                    }).execute()
                    st.rerun()

# --- 6. CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
    st.subheader("📁 Categorías")
    c_nueva = st.text_input("Nueva Categoría").upper()
    if st.button("➕ Añadir"):
        if c_nueva:
            try:
                supabase.table("configuracion").insert({"tipo": "categoria", "valor": c_nueva}).execute()
                st.success("Añadida")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    
    st.divider()
    res_conf = supabase.table("configuracion").select("*").eq("tipo", "categoria").execute()
    if res_conf.data:
        for c in res_conf.data:
            col_a, col_b = st.columns([4, 1])
            col_a.write(c['valor'])
            if col_b.button("🗑️", key=f"del_cat_{c['id']}"):
                supabase.table("configuracion").delete().eq("id", c['id']).execute()
                st.rerun()

# --- 7. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes")
    res_v = supabase.table("ventas").select("*").execute()
    if res_v.data:
        df_r = pd.DataFrame(res_v.data)
        st.metric("Ventas Totales", f"${df_r['precio_total'].sum():,.2f}")
        st.dataframe(df_r, use_container_width=True)
