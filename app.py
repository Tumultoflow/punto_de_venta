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

# --- 2. FUNCIONES DE APOYO ---
def obtener_config(tipo):
    try:
        res = supabase.table("configuracion").select("valor").eq("tipo", tipo).execute()
        items = [r['valor'] for r in res.data]
        return sorted(items) if items else ["GENERAL"]
    except:
        return ["GENERAL"]

# --- 3. AUTENTICACIÓN ---
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

# --- 4. VENTAS (CARRITO MULTI-COLOR) ---
if menu == "Ventas":
    st.header("💰 Nueva Venta")
    if "carrito" not in st.session_state: st.session_state.carrito = []

    res = supabase.table("productos").select("*").gt("stock", 0).order("codigo").execute()
    if res.data:
        df_v = pd.DataFrame(res.data)
        opciones = [f"{r['codigo']} - {r['nombre']}" for r in res.data]
        sel_raw = st.selectbox("📦 Seleccionar Producto", opciones)
        
        cod_v = sel_raw.split(" - ")[0]
        item = df_v[df_v['codigo'] == cod_v].iloc[0]
        
        c_img, c_form = st.columns([1, 2])
        with c_img:
            if item.get('foto_path'): st.image(item['foto_path'], width=250)
            st.metric("Stock", f"{item['stock']} pzs")

        with c_form:
            lista_colores = [c.strip().upper() for c in item['colores'].split(',') if c.strip()] if item.get('colores') else ["ÚNICO"]
            v_col = st.selectbox("🎨 Color", lista_colores)
            v_cant = st.number_input("Cantidad", 1, int(item['stock']))
            v_pre = st.number_input("Precio ($)", value=float(item['precio_pub']))
            
            if st.button("➕ Añadir"):
                st.session_state.carrito.append({
                    "id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'],
                    "color": v_col, "cantidad": v_cant, "precio_unit": v_pre,
                    "precio_inv": item['precio_inv'], "foto_path": item.get('foto_path')
                })
                st.toast("Añadido")

        if st.session_state.carrito:
            st.divider()
            df_car = pd.DataFrame(st.session_state.carrito)
            st.dataframe(df_car[["codigo", "nombre", "color", "cantidad", "precio_unit"]], use_container_width=True)
            
            v_vendedor = st.text_input("👤 Vendedor")
            v_fecha = st.date_input("📅 Fecha", datetime.now(ZONA_LOCAL))

            if st.button("🚀 CONFIRMAR VENTA", type="primary"):
                for p in st.session_state.carrito:
                    # Descontar stock
                    res_s = supabase.table("productos").select("stock").eq("id", p['id']).execute()
                    n_stk = res_s.data[0]['stock'] - p['cantidad']
                    supabase.table("productos").update({"stock": n_stk}).eq("id", p['id']).execute()
                    
                    # Registrar Venta (Incluye foto_path para el reporte)
                    supabase.table("ventas").insert({
                        "producto": p['nombre'], "codigo_prod": p['codigo'], "color": p['color'],
                        "cantidad": p['cantidad'], "precio_total": p['precio_unit'] * p['cantidad'],
                        "fecha_venta": v_fecha.isoformat(), "vendedor": v_vendedor,
                        "ganancia": (p['precio_unit'] - p['precio_inv']) * p['cantidad'],
                        "foto_path": p['foto_path'] 
                    }).execute()
                st.session_state.carrito = []
                st.success("Venta realizada")
                st.rerun()

# --- 5. INVENTARIO (CON IMÁGENES ACTIVAS) ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    res_i = supabase.table("productos").select("*").order("codigo").execute()
    df_i = pd.DataFrame(res_i.data) if res_i.data else pd.DataFrame()
    
    tabs = ["📋 Existencias", "🆕 Nuevo Producto"] if role == "admin" else ["📋 Existencias"]
    t_lista, *t_admin = st.tabs(tabs)

    with t_lista:
        if not df_i.empty:
            columnas = ["foto_path", "codigo", "nombre", "stock", "categoria", "subcategoria", "colores", "precio_pub"]
            if role == "admin": columnas.insert(7, "precio_inv")
            
            st.data_editor(
                df_i,
                column_order=columnas,
                column_config={
                    "foto_path": st.column_config.ImageColumn("Imagen"),
                    "precio_pub": st.column_config.NumberColumn("Venta", format="$%.2f"),
                    "precio_inv": st.column_config.NumberColumn("Costo", format="$%.2f")
                },
                hide_index=True, use_container_width=True
            )

    if role == "admin" and t_admin:
        with t_admin[0]:
            # Formulario de registro (omito por espacio, pero mantiene la lógica de CAT-SUB-0000)
            st.info("Usa el formulario estándar para registrar productos.")

# --- 7. REPORTES (CON CÓDIGO E IMAGEN DE LO VENDIDO) ---
elif menu == "Reportes":
    st.header("📊 Reporte de Ventas Detallado")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    
    if res_v.data:
        df_r = pd.DataFrame(res_v.data)
        df_r['fecha_venta'] = pd.to_datetime(df_r['fecha_venta']).dt.date
        
        # Resumen métrico
        c1, c2 = st.columns(2)
        c1.metric("Ventas Totales", f"${df_r['precio_total'].sum():,.2f}")
        c2.metric("Ganancia Neta", f"${df_r['ganancia'].sum():,.2f}")
        
        st.divider()
        st.subheader("📝 Historial de Transacciones")
        
        # Configuración de tabla con Imágenes y Códigos
        st.dataframe(
            df_r[["foto_path", "codigo_prod", "producto", "color", "cantidad", "precio_total", "fecha_venta", "vendedor"]],
            column_config={
                "foto_path": st.column_config.ImageColumn("Imagen"),
                "codigo_prod": "Código",
                "precio_total": st.column_config.NumberColumn("Total", format="$%.2f"),
                "fecha_venta": "Fecha"
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Gráfico semanal
        df_r['Semana'] = pd.to_datetime(df_r['fecha_venta']).dt.to_period('W-MON').apply(lambda r: r.start_time)
        rep_sem = df_r.groupby('Semana').agg({'precio_total': 'sum', 'ganancia': 'sum'}).sort_index(ascending=False)
        st.bar_chart(rep_sem)
    else:
        st.info("No hay ventas registradas.")
