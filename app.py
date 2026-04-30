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
    st.title("🔐 Acceso")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "admin1": 
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "equipo1": 
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
    st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown(f"**Usuario:** `{st.session_state.role.upper()}`")
    if st.button("🚪 CERRAR SESIÓN", use_container_width=True, type="primary"):
        st.session_state.auth = False
        st.session_state.role = None
        st.rerun()
    st.divider()

role = st.session_state.role
menu = st.sidebar.radio("Menú Principal", ["Ventas", "Inventario", "Configuración", "Reportes"] if role == "admin" else ["Ventas", "Inventario"])

# --- 4. VENTAS (AHORA CON SELECCIÓN DE COLOR) ---
if menu == "Ventas":
    st.header("💰 Nueva Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).order("codigo").execute()
    
    if res.data:
        df_v = pd.DataFrame(res.data)
        # Formato de búsqueda: CODIGO - NOMBRE
        opciones_busqueda = [f"{r['codigo']} - {r['nombre']}" for r in res.data]
        sel_raw = st.selectbox("📦 Seleccionar Producto", opciones_busqueda)
        
        cod_v = sel_raw.split(" - ")[0]
        item = df_v[df_v['codigo'] == cod_v].iloc[0]
        
        c1, c2 = st.columns(2)
        with c1:
            if item.get('foto_path'): 
                st.image(item['foto_path'], width=300)
            st.info(f"**Código:** {item['codigo']}  \n**Existencia:** {item['stock']} unidades")
        
        with c2:
            # --- Lógica de Colores ---
            lista_colores = []
            if item.get('colores'):
                # Separamos por comas y limpiamos espacios
                lista_colores = [c.strip().upper() for c in item['colores'].split(',') if c.strip()]
            
            if lista_colores:
                v_color = st.selectbox("🎨 Seleccionar Color", lista_colores)
            else:
                v_color = "ÚNICO / NA"
                st.write("🎨 **Color:** No especificado")

            v_precio = st.number_input("💵 Precio de Venta", value=float(item['precio_pub']))
            v_cant = st.number_input("Cantidad", 1, int(item['stock']))
            v_vendedor = st.text_input("👤 Vendedor")
            v_fecha = st.date_input("📅 Fecha", datetime.now(ZONA_LOCAL))

            if st.button("🚀 Confirmar Venta", use_container_width=True, type="primary"):
                # 1. Actualizar Stock
                supabase.table("productos").update({"stock": int(item['stock'] - v_cant)}).eq("id", item['id']).execute()
                
                # 2. Registrar Venta (Incluyendo el color seleccionado)
                supabase.table("ventas").insert({
                    "producto": item['nombre'], 
                    "codigo_prod": item['codigo'],
                    "color": v_color, # Guardamos el color elegido
                    "cantidad": v_cant, 
                    "precio_total": v_precio * v_cant,
                    "fecha_venta": v_fecha.isoformat(), 
                    "vendedor": v_vendedor,
                    "ganancia": (v_precio - item['precio_inv']) * v_cant
                }).execute()
                
                st.success(f"¡Venta realizada! {item['nombre']} ({v_color})")
                st.rerun()

# --- 5. INVENTARIO (CON EDICIÓN DE CÓDIGOS Y COLORES) ---
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
            p_sel_raw = st.selectbox("Selecciona un producto para editar:", ["-- Seleccionar --"] + opciones_p)
            
            if p_sel_raw != "-- Seleccionar --":
                cod_sel = p_sel_raw.split(" - ")[0]
                it = df_i[df_i['codigo'] == cod_sel].iloc[0]
                with st.expander("📝 Editar Información y Código", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        e_cod_manual = st.text_input("Código (CAT-SUB-0000)", value=it['codigo'])
                        e_nom = st.text_input("Nombre", value=it['nombre'])
                        e_cat = st.selectbox("Categoría", lista_cats, index=lista_cats.index(it['categoria']) if it['categoria'] in lista_cats else 0)
                        e_sub = st.selectbox("Subcategoría", lista_subs, index=lista_subs.index(it['subcategoria']) if it['subcategoria'] in lista_subs else 0)
                        e_col = st.text_input("Colores (Separados por coma: Rojo, Azul...)", value=it.get('colores', ''))
                        
                        if st.button("💾 Actualizar Todo"):
                            supabase.table("productos").update({
                                "codigo": e_cod_manual.upper(),
                                "nombre": e_nom, "categoria": e_cat, 
                                "subcategoria": e_sub, "colores": e_col
                            }).eq("id", it['id']).execute()
                            st.success("Producto actualizado")
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

        columnas_visibles = ["foto_path", "codigo", "nombre", "stock", "categoria", "subcategoria", "colores", "precio_pub"]
        if role == "admin": columnas_visibles.insert(7, "precio_inv")

        st.data_editor(
            df_i,
            column_order=tuple(columnas_visibles),
            column_config={
                "foto_path": st.column_config.ImageColumn("Imagen"),
                "precio_inv": st.column_config.NumberColumn("Inversión", format="$%.2f"),
                "precio_pub": st.column_config.NumberColumn("Venta", format="$%.2f"),
                "codigo": "Código", "nombre": "Producto"
            },
            use_container_width=True, hide_index=True
        )

    if role == "admin" and t_admin:
        with t_admin[0]:
            with st.form("nuevo_p"):
                c1, c2 = st.columns(2)
                n_nom, n_cat = c1.text_input("Nombre*"), c2.selectbox("Categoría*", lista_cats)
                n_sub, n_col = c1.selectbox("Subcategoría*", lista_subs), c2.text_input("Colores (Rojo, Azul, Negro...)")
                n_inv, n_pub = c1.number_input("Inversión ($)"), c2.number_input("Público ($)")
                n_stk = c1.number_input("Stock Inicial", step=1)
                
                if st.form_submit_button("🚀 Registrar"):
                    res_cods = supabase.table("productos").select("codigo").eq("categoria", n_cat).execute()
                    max_n = 0
                    if res_cods.data:
                        for r in res_cods.data:
                            try:
                                n = int(r['codigo'].split('-')[-1])
                                if n > max_n: max_n = n
                            except: continue
                    
                    n_seq = str(max_n + 1).zfill(4)
                    n_cod = f"{n_cat[:3].upper()}-{n_sub[:3].upper()}-{n_seq}"
                    
                    supabase.table("productos").insert({
                        "codigo": n_cod, "nombre": n_nom, "categoria": n_cat, 
                        "subcategoria": n_sub, "colores": n_col, 
                        "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk
                    }).execute()
                    st.rerun()

# --- 6. CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
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

# --- 7. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes Semanales")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_r = pd.DataFrame(res_v.data)
        df_r['fecha_venta'] = pd.to_datetime(df_r['fecha_venta'])
        col1, col2 = st.columns(2)
        col1.metric("Ventas Totales", f"${df_r['precio_total'].sum():,.2f}")
        col2.metric("Utilidad Neta", f"${df_r['ganancia'].sum():,.2f}")
        
        st.divider()
        st.subheader("📝 Detalle de Ventas")
        # Mostrar el color en la tabla de reportes
        st.dataframe(df_r[["fecha_venta", "vendedor", "codigo_prod", "producto", "color", "cantidad", "precio_total"]], use_container_width=True)
        
        st.divider()
        df_r['Semana'] = df_r['fecha_venta'].dt.to_period('W-MON').apply(lambda r: r.start_time)
        rep_sem = df_r.groupby('Semana').agg({'precio_total': 'sum', 'ganancia': 'sum', 'producto': 'count'}).sort_index(ascending=False)
        rep_sem.columns = ['Ventas ($)', 'Ganancia ($)', 'Operaciones']
        st.dataframe(rep_sem.style.format("${:,.2f}", subset=['Ventas ($)', 'Ganancia ($)']), use_container_width=True)
        st.bar_chart(rep_sem[['Ventas ($)', 'Ganancia ($)']])
