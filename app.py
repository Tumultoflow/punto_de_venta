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

st.set_page_config(page_title="TUMULTOFLOW v3", layout="wide", page_icon="⚖️")

# --- 2. FUNCIONES DE APOYO ---
def obtener_config(tipo):
    try:
        res = supabase.table("configuracion").select("valor").eq("tipo", tipo).execute()
        return sorted([r['valor'] for r in res.data]) if res.data else ["GENERAL"]
    except:
        return ["GENERAL"]

# --- 3. ESTADO DE LA SESIÓN (PERSISTENCIA) ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []

# --- 4. AUTENTICACIÓN ---
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
    menu = st.radio("Menú Principal", ["Ventas", "Inventario", "Configuración", "Reportes"] if st.session_state.role == "admin" else ["Ventas", "Inventario"])
    if st.button("🚪 CERRAR SESIÓN", use_container_width=True):
        st.session_state.auth = False
        st.rerun()

# --- 5. SECCIÓN: VENTAS (CARRITO ESTABLE) ---
if menu == "Ventas":
    st.header("💰 Nueva Venta Multi-Color")
    
    res = supabase.table("productos").select("*").gt("stock", 0).order("codigo").execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        opciones = [f"{r['codigo']} - {r['nombre']}" for r in res.data]
        sel_prod = st.selectbox("📦 Seleccionar Producto", opciones)
        
        item = df_p[df_p['codigo'] == sel_prod.split(" - ")[0]].iloc[0]
        
        col1, col2 = st.columns([1, 2])
        with col1:
            if item.get('foto_path'): st.image(item['foto_path'], width=250)
            st.info(f"**Stock:** {item['stock']} unidades")
        
        with col2:
            colores = [c.strip().upper() for c in item['colores'].split(',') if c.strip()] if item.get('colores') else ["ÚNICO"]
            c_color = st.selectbox("🎨 Elegir Color", colores)
            c_cant = st.number_input("Cantidad", 1, int(item['stock']))
            c_pre = st.number_input("Precio Unitario", value=float(item['precio_pub']))
            
            if st.button("➕ Añadir al Carrito"):
                st.session_state.carrito.append({
                    "id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'],
                    "color": c_color, "cantidad": c_cant, "precio": c_pre, 
                    "precio_inv": item['precio_inv'], "foto": item.get('foto_path')
                })
                st.toast(f"Añadido {c_color}")

        if st.session_state.carrito:
            st.subheader("📋 Resumen de Venta")
            df_car = pd.DataFrame(st.session_state.carrito)
            st.table(df_car[["codigo", "nombre", "color", "cantidad", "precio"]])
            
            total = (df_car['cantidad'] * df_car['precio']).sum()
            st.write(f"### **Total: ${total:,.2f}**")
            
            v_vend = st.text_input("Vendedor")
            
            c_v1, c_v2 = st.columns(2)
            if c_v1.button("🗑️ Vaciar"): 
                st.session_state.carrito = []; st.rerun()
                
            if c_v2.button("🚀 Confirmar Venta", type="primary"):
                if v_vend:
                    for p in st.session_state.carrito:
                        # Actualizar Stock
                        stk_actual = supabase.table("productos").select("stock").eq("id", p['id']).execute().data[0]['stock']
                        supabase.table("productos").update({"stock": stk_actual - p['cantidad']}).eq("id", p['id']).execute()
                        # Registrar Venta
                        supabase.table("ventas").insert({
                            "producto": p['nombre'], "codigo_prod": p['codigo'], "color": p['color'],
                            "cantidad": p['cantidad'], "precio_total": p['precio'] * p['cantidad'],
                            "vendedor": v_vend, "ganancia": (p['precio'] - p['precio_inv']) * p['cantidad'],
                            "foto_path": p['foto'], "fecha_venta": datetime.now(ZONA_LOCAL).isoformat()
                        }).execute()
                    st.session_state.carrito = []
                    st.success("Venta Guardada")
                    st.rerun()

# --- 6. SECCIÓN: INVENTARIO (NUEVO PRODUCTO CORREGIDO) ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    
    cats = obtener_config("categoria")
    subs = obtener_config("subcategoria")
    
    tab1, tab2 = st.tabs(["📋 Existencias", "🆕 Nuevo Producto"])
    
    with tab1:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            df_i = pd.DataFrame(res.data)
            st.data_editor(df_i, column_config={
                "foto_path": st.column_config.ImageColumn("Foto"),
                "precio_pub": st.column_config.NumberColumn("Venta", format="$%.2f")
            }, hide_index=True, use_container_width=True)

    with tab2:
        with st.form("form_nuevo"):
            f1, f2 = st.columns(2)
            n_nom = f1.text_input("Nombre del Producto*")
            n_cat = f1.selectbox("Categoría", cats)
            n_sub = f2.selectbox("Subcategoría", subs)
            n_col = f2.text_input("Colores (Separados por coma)")
            n_inv = f1.number_input("Costo Inversión", min_value=0.0)
            n_pub = f2.number_input("Precio Venta", min_value=0.0)
            n_stk = f1.number_input("Stock Inicial", min_value=1, step=1)
            
            if st.form_submit_button("🚀 Registrar Producto"):
                # Generar Código
                existentes = supabase.table("productos").select("codigo").eq("categoria", n_cat).execute()
                num = len(existentes.data) + 1
                nuevo_cod = f"{n_cat[:3]}-{n_sub[:3]}-{num:04d}".upper()
                
                supabase.table("productos").insert({
                    "codigo": nuevo_cod, "nombre": n_nom, "categoria": n_cat,
                    "subcategoria": n_sub, "colores": n_col, "precio_inv": n_inv,
                    "precio_pub": n_pub, "stock": n_stk
                }).execute()
                st.success(f"Registrado como {nuevo_cod}")
                st.rerun()

# --- 7. SECCIÓN: CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración de Listas")
    tipo = st.radio("Editar:", ["Categorías", "Subcategorías"], horizontal=True)
    t_db = "categoria" if tipo == "Categorías" else "subcategoria"
    
    n_val = st.text_input(f"Nueva {tipo}").upper()
    if st.button("➕ Agregar"):
        if n_val: 
            supabase.table("configuracion").insert({"tipo": t_db, "valor": n_val}).execute()
            st.rerun()
    
    res = supabase.table("configuracion").select("*").eq("tipo", t_db).execute()
    for r in res.data:
        c1, c2 = st.columns([5, 1])
        c1.write(r['valor'])
        if c2.button("🗑️", key=r['id']):
            supabase.table("configuracion").delete().eq("id", r['id']).execute()
            st.rerun()

# --- 8. SECCIÓN: REPORTES (IMAGEN Y CÓDIGO) ---
elif menu == "Reportes":
    st.header("📊 Reporte de Ventas")
    res = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res.data:
        df_r = pd.DataFrame(res.data)
        st.dataframe(df_r, column_config={
            "foto_path": st.column_config.ImageColumn("Imagen"),
            "codigo_prod": "Código SKU",
            "precio_total": st.column_config.NumberColumn("Total", format="$%.2f")
        }, hide_index=True, use_container_width=True)
