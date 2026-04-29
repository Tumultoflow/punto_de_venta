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
def obtener_config(tipo):
    try:
        res = supabase.table("configuracion").select("valor").eq("tipo", tipo).execute()
        items = [r['valor'] for r in res.data]
        return sorted(items) if items else ["GENERAL"]
    except:
        return ["GENERAL"]

# --- 3. SISTEMA DE AUTENTICACIÓN ---
if "auth" not in st.session_state: 
    st.session_state.auth = False

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

# --- BARRA LATERAL (Cerrar Sesión y Navegación) ---
with st.sidebar:
    st.markdown(f"**Usuario:** `{st.session_state.role.upper()}`")
    if st.button("🚪 CERRAR SESIÓN", use_container_width=True, type="primary"):
        st.session_state.auth = False
        st.session_state.role = None
        st.rerun()
    st.divider()

role = st.session_state.role
menu = st.sidebar.radio("Menú Principal", ["Ventas", "Inventario", "Configuración", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])

# --- 4. VENTAS ---
if menu == "Ventas":
    st.header("💰 Nueva Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).order("codigo").execute()
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

# --- 5. INVENTARIO (Con Privacidad de Precios y Orden Alfabético) ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    res_i = supabase.table("productos").select("*").order("codigo").execute()
    df_i = pd.DataFrame(res_i.data) if res_i.data else pd.DataFrame()
    
    lista_cats = obtener_config("categoria")
    lista_subs = obtener_config("subcategoria")

    tabs = ["📋 Existencias"]
    if role == "admin": tabs.append("🆕 Nuevo Producto")
    t_lista, *t_admin = st.tabs(tabs)

    with t_lista:
        if role == "admin" and not df_i.empty:
            st.subheader("🛠️ Gestionar Producto:")
            opciones_p = [f"{r['codigo']} - {r['nombre']}" for r in res_i.data]
            p_sel_raw = st.selectbox("Selecciona un producto para gestionar:", ["-- Seleccionar --"] + opciones_p)
            
            if p_sel_raw != "-- Seleccionar --":
                cod_sel = p_sel_raw.split(" - ")[0]
                it = df_i[df_i['codigo'] == cod_sel].iloc[0]
                with st.expander("📝 Editar Información / Eliminar", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        e_nom = st.text_input("Nombre", value=it['nombre'])
                        e_cat = st.selectbox("Categoría", lista_cats, index=lista_cats.index(it['categoria']) if it['categoria'] in lista_cats else 0)
                        e_sub = st.selectbox("Subcategoría", lista_subs, index=lista_subs.index(it['subcategoria']) if it['subcategoria'] in lista_subs else 0)
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
                        if st.button("🗑️ ELIMINAR"):
                            supabase.table("productos").delete().eq("id", it['id']).execute()
                            st.rerun()

        # Filtrado de columnas por rol
        columnas_visibles = ["foto_path", "codigo", "stock", "categoria", "subcategoria", "colores", "precio_pub", "nombre"]
        if role == "admin": columnas_visibles.insert(6, "precio_inv")

        st.data_editor(
            df_i,
            column_order=tuple(columnas_visibles),
            column_config={
                "foto_path": st.column_config.ImageColumn("Imagen"),
                "precio_inv": st.column_config.NumberColumn("Inversión ($)", format="$%.2f"),
                "precio_pub": st.column_config.NumberColumn("Venta ($)", format="$%.2f"),
                "stock": "Stock", "codigo": "Código"
            },
            use_container_width=True, hide_index=True
        )

    if role == "admin" and t_admin:
        with t_admin[0]:
            with st.form("nuevo_p"):
                c1, c2 = st.columns(2)
                n_nom, n_cat = c1.text_input("Nombre*"), c2.selectbox("Categoría*", lista_cats)
                n_sub, n_col = c1.selectbox("Subcategoría*", lista_subs), c2.text_input("Colores")
                n_inv, n_pub = c1.number_input("Inversión ($)"), c2.number_input("Precio Público ($)")
                n_stk = c1.number_input("Stock Inicial", step=1)
                if st.form_submit_button("🚀 Registrar Producto"):
                    res_c = supabase.table("productos").select("id", count="exact").eq("categoria", n_cat).eq("subcategoria", n_sub).execute()
                    n_seq = str((res_c.count or 0) + 1).zfill(3)
                    n_cod = f"{n_cat[:3].upper()}-{n_sub[:2].upper()}-{n_nom[:3].upper()}-{n_seq}"
                    supabase.table("productos").insert({
                        "codigo": n_cod, "nombre": n_nom, "categoria": n_cat, 
                        "subcategoria": n_sub, "colores": n_col, 
                        "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk
                    }).execute()
                    st.rerun()

# --- 6. CONFIGURACIÓN (Gestión de Listas) ---
elif menu == "Configuración":
    st.header("⚙️ Configuración de Listas")
    c_cat, c_sub = st.columns(2)
    
    with c_cat:
        st.subheader("📁 Categorías")
        n_c = st.text_input("Nueva Categoría").upper()
        if st.button("➕ Añadir Cat"):
            if n_c: supabase.table("configuracion").insert({"tipo": "categoria", "valor": n_c}).execute(); st.rerun()
        res_c = supabase.table("configuracion").select("*").eq("tipo", "categoria").order("valor").execute()
        for c in res_c.data:
            ca, cb = st.columns([4, 1])
            ca.write(c['valor'])
            if cb.button("🗑️", key=f"c_{c['id']}"): supabase.table("configuracion").delete().eq("id", c['id']).execute(); st.rerun()

    with c_sub:
        st.subheader("📂 Subcategorías")
        n_s = st.text_input("Nueva Subcategoría").upper()
        if st.button("➕ Añadir Sub"):
            if n_s: supabase.table("configuracion").insert({"tipo": "subcategoria", "valor": n_s}).execute(); st.rerun()
        res_s = supabase.table("configuracion").select("*").eq("tipo", "subcategoria").order("valor").execute()
        for s in res_s.data:
            sa, sb = st.columns([4, 1])
            sa.write(s['valor'])
            if sb.button("🗑️", key=f"s_{s['id']}"): supabase.table("configuracion").delete().eq("id", s['id']).execute(); st.rerun()

# --- 7. REPORTES (Semanal y Ganancias) ---
elif menu == "Reportes":
    st.header("📊 Reportes de Ganancias Semanales")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_r = pd.DataFrame(res_v.data)
        df_r['fecha_venta'] = pd.to_datetime(df_r['fecha_venta'])
        
        col1, col2 = st.columns(2)
        col1.metric("Ingresos Totales", f"${df_r['precio_total'].sum():,.2f}")
        col2.metric("Utilidad Neta Total", f"${df_r['ganancia'].sum():,.2f}")

        st.divider()
        df_r['Semana'] = df_r['fecha_venta'].dt.to_period('W-MON').apply(lambda r: r.start_time)
        rep_sem = df_r.groupby('Semana').agg({'precio_total': 'sum', 'ganancia': 'sum', 'producto': 'count'}).sort_index(ascending=False)
        rep_sem.columns = ['Ventas ($)', 'Ganancia ($)', 'Cantidad']
        
        st.subheader("📈 Resumen por Semana")
        st.dataframe(rep_sem.style.format("${:,.2f}", subset=['Ventas ($)', 'Ganancia ($)']), use_container_width=True)
        st.bar_chart(rep_sem[['Ventas ($)', 'Ganancia ($)']])
    else:
        st.info("Sin datos de ventas.")
