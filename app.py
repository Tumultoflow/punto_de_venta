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

st.set_page_config(page_title="TUMULTOFLOW PRO", layout="wide", page_icon="⚖️")

# --- 2. FUNCIONES DE APOYO ---
def obtener_config(tipo):
    try:
        res = supabase.table("configuracion").select("valor").eq("tipo", tipo).execute()
        return sorted([r['valor'] for r in res.data]) if res.data else ["GENERAL"]
    except:
        return ["GENERAL"]

# --- 3. ESTADO DE LA SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []

# --- 4. AUTENTICACIÓN ---
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

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown(f"**Usuario:** `{st.session_state.role.upper()}`")
    menu = st.radio("Menú Principal", ["Ventas", "Inventario", "Configuración", "Reportes"] if st.session_state.role == "admin" else ["Ventas", "Inventario"])
    if st.button("🚪 CERRAR SESIÓN", use_container_width=True, type="primary"):
        st.session_state.auth = False
        st.rerun()

# --- 5. SECCIÓN: VENTAS (CARRITO MULTI-COLOR CON FOTOS) ---
if menu == "Ventas":
    st.header("💰 Venta Multi-Color")
    
    res = supabase.table("productos").select("*").gt("stock", 0).order("codigo").execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        opciones = [f"{r['codigo']} - {r['nombre']}" for r in res.data]
        sel_prod = st.selectbox("📦 Buscar Producto", opciones)
        
        item = df_p[df_p['codigo'] == sel_prod.split(" - ")[0]].iloc[0]
        
        c1, c2 = st.columns([1, 2])
        with c1:
            if item.get('foto_path'): st.image(item['foto_path'], width=280)
            st.metric("Stock Actual", f"{item['stock']} pzs")
        
        with c2:
            st.subheader("Configurar Línea de Venta")
            colores = [c.strip().upper() for c in item['colores'].split(',') if c.strip()] if item.get('colores') else ["ÚNICO"]
            
            v_col = st.selectbox("🎨 Color", colores)
            v_cant = st.number_input("Cantidad", 1, int(item['stock']))
            v_pre = st.number_input("Precio Unitario", value=float(item['precio_pub']))
            
            if st.button("➕ Añadir a esta Venta"):
                st.session_state.carrito.append({
                    "id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'],
                    "color": v_col, "cantidad": v_cant, "precio": v_pre, 
                    "precio_inv": item['precio_inv'], "foto": item.get('foto_path')
                })
                st.toast(f"Añadido: {item['nombre']} ({v_col})")

        if st.session_state.carrito:
            st.divider()
            st.subheader("🛒 Resumen del Carrito")
            df_car = pd.DataFrame(st.session_state.carrito)
            st.dataframe(df_car[["codigo", "nombre", "color", "cantidad", "precio"]], use_container_width=True)
            
            total_v = (df_car['cantidad'] * df_car['precio']).sum()
            st.markdown(f"## **Total a Cobrar: ${total_v:,.2f}**")
            
            v_vend = st.text_input("👤 Nombre del Vendedor")
            
            cv1, cv2 = st.columns(2)
            if cv1.button("🗑️ Vaciar Carrito", use_container_width=True):
                st.session_state.carrito = []; st.rerun()
                
            if cv2.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
                if v_vend:
                    for p in st.session_state.carrito:
                        # 1. Descontar Stock
                        res_s = supabase.table("productos").select("stock").eq("id", p['id']).execute()
                        nuevo_stk = res_s.data[0]['stock'] - p['cantidad']
                        supabase.table("productos").update({"stock": nuevo_stk}).eq("id", p['id']).execute()
                        
                        # 2. Registrar Venta (Copiando el foto_path para el reporte)
                        supabase.table("ventas").insert({
                            "producto": p['nombre'], "codigo_prod": p['codigo'], "color": p['color'],
                            "cantidad": p['cantidad'], "precio_total": p['precio'] * p['cantidad'],
                            "vendedor": v_vend, "ganancia": (p['precio'] - p['precio_inv']) * p['cantidad'],
                            "foto_path": p['foto'], "fecha_venta": datetime.now(ZONA_LOCAL).isoformat()
                        }).execute()
                    
                    st.session_state.carrito = []
                    st.success("¡Venta registrada exitosamente!")
                    st.rerun()
                else:
                    st.warning("Por favor, ingresa el nombre del vendedor.")

# --- 6. SECCIÓN: INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario y Almacén")
    cats = obtener_config("categoria")
    subs = obtener_config("subcategoria")
    
    tab1, tab2 = st.tabs(["📋 Lista de Existencias", "🆕 Registrar Nuevo"])
    
    with tab1:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            df_i = pd.DataFrame(res.data)
            st.data_editor(
                df_i,
                column_order=("foto_path", "codigo", "nombre", "stock", "categoria", "subcategoria", "colores", "precio_pub"),
                column_config={
                    "foto_path": st.column_config.ImageColumn("Miniatura"),
                    "precio_pub": st.column_config.NumberColumn("P. Público", format="$%.2f"),
                    "stock": "Existencia"
                },
                hide_index=True, use_container_width=True
            )

    with tab2:
        if st.session_state.role == "admin":
            with st.form("form_alta"):
                f1, f2 = st.columns(2)
                n_nom = f1.text_input("Nombre del Producto*")
                n_cat = f1.selectbox("Categoría Principal", cats)
                n_sub = f2.selectbox("Subcategoría", subs)
                n_col = f2.text_input("Colores (Ej: Rojo, Azul, Verde)")
                n_inv = f1.number_input("Costo de Inversión", min_value=0.0)
                n_pub = f2.number_input("Precio de Venta", min_value=0.0)
                n_stk = f1.number_input("Stock Inicial", min_value=0, step=1)
                
                if st.form_submit_button("🚀 Guardar Producto"):
                    # Lógica de secuencia según categoría
                    exist = supabase.table("productos").select("codigo").eq("categoria", n_cat).execute()
                    num_sec = len(exist.data) + 1
                    nuevo_sku = f"{n_cat[:3]}-{n_sub[:3]}-{num_sec:04d}".upper()
                    
                    supabase.table("productos").insert({
                        "codigo": nuevo_sku, "nombre": n_nom, "categoria": n_cat,
                        "subcategoria": n_sub, "colores": n_col, "precio_inv": n_inv,
                        "precio_pub": n_pub, "stock": n_stk
                    }).execute()
                    st.success(f"Producto registrado: {nuevo_sku}")
                    st.rerun()
        else:
            st.warning("No tienes permisos para registrar nuevos productos.")

# --- 7. SECCIÓN: CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Ajustes de Sistema")
    opc = st.segmented_control("Gestionar:", ["Categorías", "Subcategorías"])
    
    if opc:
        tipo_db = "categoria" if opc == "Categorías" else "subcategoria"
        
        c_add, _ = st.columns([2,1])
        n_val = c_add.text_input(f"Agregar nueva {opc}").upper()
        if c_add.button("➕ Añadir"):
            if n_val:
                supabase.table("configuracion").insert({"tipo": tipo_db, "valor": n_val}).execute()
                st.rerun()
        
        st.divider()
        res_c = supabase.table("configuracion").select("*").eq("tipo", tipo_db).execute()
        for r in res_c.data:
            col_t, col_b = st.columns([4, 1])
            col_t.write(f"🔹 {r['valor']}")
            if col_b.button("🗑️", key=f"del_{r['id']}"):
                supabase.table("configuracion").delete().eq("id", r['id']).execute()
                st.rerun()

# --- 8. SECCIÓN: REPORTES (IMAGEN Y CÓDIGO SKU) ---
elif menu == "Reportes":
    st.header("📊 Historial de Ventas")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    
    if res_v.data:
        df_r = pd.DataFrame(res_v.data)
        
        # Métricas principales
        m1, m2, m3 = st.columns(3)
        m1.metric("Ventas Totales", f"${df_r['precio_total'].sum():,.2f}")
        m2.metric("Utilidad Neta", f"${df_r['ganancia'].sum():,.2f}")
        m3.metric("Productos Vendidos", f"{df_r['cantidad'].sum()} pzs")
        
        st.divider()
        
        # Tabla Detallada con Imágenes
        st.dataframe(
            df_r,
            column_order=("foto_path", "codigo_prod", "producto", "color", "cantidad", "precio_total", "fecha_venta", "vendedor"),
            column_config={
                "foto_path": st.column_config.ImageColumn("Imagen"),
                "codigo_prod": "Código SKU",
                "precio_total": st.column_config.NumberColumn("Total Cobrado", format="$%.2f"),
                "fecha_venta": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YY HH:mm")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No hay datos de ventas registrados.")
