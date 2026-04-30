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

# --- 4. VENTAS (MULTI-COLOR) ---
if menu == "Ventas":
    st.header("💰 Nueva Venta")
    
    # Inicializar carrito temporal si no existe
    if "carrito" not in st.session_state:
        st.session_state.carrito = []

    res = supabase.table("productos").select("*").gt("stock", 0).order("codigo").execute()
    
    if res.data:
        df_v = pd.DataFrame(res.data)
        opciones_busqueda = [f"{r['codigo']} - {r['nombre']}" for r in res.data]
        sel_raw = st.selectbox("📦 Seleccionar Producto", opciones_busqueda)
        
        cod_v = sel_raw.split(" - ")[0]
        item = df_v[df_v['codigo'] == cod_v].iloc[0]
        
        col_img, col_form = st.columns([1, 2])
        
        with col_img:
            if item.get('foto_path'): 
                st.image(item['foto_path'], width=280)
            st.metric("Stock Disponible", f"{item['stock']} pzs")

        with col_form:
            st.subheader("Configurar Colores")
            c1, c2, c3 = st.columns([2, 1, 1])
            
            # Obtener lista de colores
            lista_colores = [c.strip().upper() for c in item['colores'].split(',') if c.strip()] if item.get('colores') else ["ÚNICO/NA"]
            
            v_color = c1.selectbox("🎨 Color", lista_colores)
            v_cant = c2.number_input("Cant", 1, int(item['stock']), key="cant_selector")
            v_precio = c3.number_input("Precio ($)", value=float(item['precio_pub']))

            if st.button("➕ Añadir a esta venta"):
                # Validar que no exceda el stock sumando lo ya añadido al carrito
                ya_en_carrito = sum(c['cantidad'] for c in st.session_state.carrito)
                if (ya_en_carrito + v_cant) <= item['stock']:
                    st.session_state.carrito.append({
                        "id": item['id'],
                        "codigo": item['codigo'],
                        "nombre": item['nombre'],
                        "color": v_color,
                        "cantidad": v_cant,
                        "precio_unit": v_precio,
                        "precio_inv": item['precio_inv']
                    })
                    st.toast(f"Añadido: {v_color}")
                else:
                    st.error("No hay suficiente stock para añadir esa cantidad.")

        # Mostrar Carrito / Resumen de la venta actual
        if st.session_state.carrito:
            st.divider()
            st.subheader("📋 Resumen de la Venta")
            df_carrito = pd.DataFrame(st.session_state.carrito)
            st.table(df_carrito[["nombre", "color", "cantidad", "precio_unit"]])
            
            total_venta = (df_carrito['cantidad'] * df_carrito['precio_unit']).sum()
            st.markdown(f"### **Total a Pagar: ${total_venta:,.2f}**")
            
            v_vendedor = st.text_input("👤 Vendedor", key="vendedor_v")
            v_fecha = st.date_input("📅 Fecha", datetime.now(ZONA_LOCAL))

            cc1, cc2 = st.columns(2)
            if cc1.button("🗑️ Cancelar Venta", use_container_width=True):
                st.session_state.carrito = []
                st.rerun()

            if cc2.button("🚀 CONFIRMAR TODA LA VENTA", type="primary", use_container_width=True):
                if v_vendedor:
                    for prod in st.session_state.carrito:
                        # 1. Restar Stock (se hace por cada línea)
                        res_prod = supabase.table("productos").select("stock").eq("id", prod['id']).execute()
                        stock_actual = res_prod.data[0]['stock']
                        supabase.table("productos").update({"stock": stock_actual - prod['cantidad']}).eq("id", prod['id']).execute()
                        
                        # 2. Insertar en Ventas
                        supabase.table("ventas").insert({
                            "producto": prod['nombre'], 
                            "codigo_prod": prod['codigo'],
                            "color": prod['color'],
                            "cantidad": prod['cantidad'], 
                            "precio_total": prod['precio_unit'] * prod['cantidad'],
                            "fecha_venta": v_fecha.isoformat(), 
                            "vendedor": v_vendedor,
                            "ganancia": (prod['precio_unit'] - prod['precio_inv']) * prod['cantidad']
                        }).execute()
                    
                    st.success("¡Venta procesada con éxito!")
                    st.session_state.carrito = []
                    st.rerun()
                else:
                    st.warning("Por favor ingresa el nombre del vendedor.")

# --- 5. INVENTARIO ---
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
            p_sel_raw = st.selectbox("Selecciona un producto:", ["-- Seleccionar --"] + opciones_p)
            
            if p_sel_raw != "-- Seleccionar --":
                cod_sel = p_sel_raw.split(" - ")[0]
                it = df_i[df_i['codigo'] == cod_sel].iloc[0]
                with st.expander("📝 Editar Información", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        e_cod = st.text_input("Código", value=it['codigo'])
                        e_nom = st.text_input("Nombre", value=it['nombre'])
                        e_cat = st.selectbox("Categoría", lista_cats, index=lista_cats.index(it['categoria']) if it['categoria'] in lista_cats else 0)
                        e_sub = st.selectbox("Subcategoría", lista_subs, index=lista_subs.index(it['subcategoria']) if it['subcategoria'] in lista_subs else 0)
                        e_col = st.text_input("Colores (Rojo, Azul...)", value=it.get('colores', ''))
                        if st.button("💾 Guardar"):
                            supabase.table("productos").update({
                                "codigo": e_cod.upper(), "nombre": e_nom, "categoria": e_cat, 
                                "subcategoria": e_sub, "colores": e_col
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

        st.data_editor(df_i, use_container_width=True, hide_index=True)

    if role == "admin" and t_admin:
        with t_admin[0]:
            with st.form("nuevo_p"):
                c1, c2 = st.columns(2)
                n_nom, n_cat = c1.text_input("Nombre*"), c2.selectbox("Categoría*", lista_cats)
                n_sub, n_col = c1.selectbox("Subcategoría*", lista_subs), c2.text_input("Colores")
                n_inv, n_pub = c1.number_input("Inversión ($)"), c2.number_input("Público ($)")
                n_stk = c1.number_input("Stock Inicial", step=1)
                if st.form_submit_button("🚀 Registrar"):
                    res_cods = supabase.table("productos").select("codigo").eq("categoria", n_cat).execute()
                    max_n = max([int(r['codigo'].split('-')[-1]) for r in res_cods.data if r['codigo'].split('-')[-1].isdigit()] + [0])
                    n_cod = f"{n_cat[:3].upper()}-{n_sub[:3].upper()}-{(max_n+1):04d}"
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
    st.header("📊 Reportes")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_r = pd.DataFrame(res_v.data)
        df_r['fecha_venta'] = pd.to_datetime(df_r['fecha_venta'])
        col1, col2 = st.columns(2)
        col1.metric("Ventas Totales", f"${df_r['precio_total'].sum():,.2f}")
        col2.metric("Ganancia Total", f"${df_r['ganancia'].sum():,.2f}")
        st.divider()
        df_r['Semana'] = df_r['fecha_venta'].dt.to_period('W-MON').apply(lambda r: r.start_time)
        rep_sem = df_r.groupby('Semana').agg({'precio_total': 'sum', 'ganancia': 'sum', 'producto': 'count'}).sort_index(ascending=False)
        rep_sem.columns = ['Ventas ($)', 'Ganancia ($)', 'Operaciones']
        st.dataframe(rep_sem.style.format("${:,.2f}", subset=['Ventas ($)', 'Ganancia ($)']), use_container_width=True)
        st.bar_chart(rep_sem[['Ventas ($)', 'Ganancia ($)']])
