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

# --- 5. SECCIÓN: VENTAS ---
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
                st.toast("Añadido al carrito")

        if st.session_state.carrito:
            st.divider()
            df_car = pd.DataFrame(st.session_state.carrito)
            st.table(df_car[["codigo", "nombre", "color", "cantidad", "precio"]])
            total_v = (df_car['cantidad'] * df_car['precio']).sum()
            st.markdown(f"## **Total: ${total_v:,.2f}**")
            v_vend = st.text_input("👤 Vendedor")
            
            if st.button("🚀 FINALIZAR VENTA", type="primary"):
                if v_vend:
                    for p in st.session_state.carrito:
                        stk_act = supabase.table("productos").select("stock").eq("id", p['id']).execute().data[0]['stock']
                        supabase.table("productos").update({"stock": stk_act - p['cantidad']}).eq("id", p['id']).execute()
                        supabase.table("ventas").insert({
                            "producto": p['nombre'], "codigo_prod": p['codigo'], "color": p['color'],
                            "cantidad": p['cantidad'], "precio_total": p['precio'] * p['cantidad'],
                            "vendedor": v_vend, "ganancia": (p['precio'] - p['precio_inv']) * p['cantidad'],
                            "foto_path": p['foto'], "fecha_venta": datetime.now(ZONA_LOCAL).isoformat()
                        }).execute()
                    st.session_state.carrito = []
                    st.success("Venta guardada")
                    st.rerun()

# --- 6. SECCIÓN: INVENTARIO (CON CÁMARA) ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    cats = obtener_config("categoria")
    subs = obtener_config("subcategoria")
    
    tab1, tab2 = st.tabs(["📋 Existencias", "🆕 Registrar Nuevo"])
    
    with tab1:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            st.data_editor(pd.DataFrame(res.data), column_config={"foto_path": st.column_config.ImageColumn("Foto")}, hide_index=True, use_container_width=True)

    with tab2:
        if st.session_state.role == "admin":
            st.subheader("Capturar Nuevo Producto")
            
            # Formulario y Cámara
            c_form, c_cam = st.columns([1, 1])
            
            with c_form:
                n_nom = st.text_input("Nombre del Producto*")
                n_cat = st.selectbox("Categoría", cats)
                n_sub = st.selectbox("Subcategoría", subs)
                n_col = st.text_input("Colores (Rojo, Azul...)")
                n_inv = st.number_input("Costo Inversión", 0.0)
                n_pub = st.number_input("Precio Venta", 0.0)
                n_stk = st.number_input("Stock Inicial", 1, step=1)
            
            with c_cam:
                st.write("📸 Foto del Producto")
                foto_captura = st.camera_input("Tomar Foto")

            if st.button("🚀 GUARDAR PRODUCTO COMPLETO", type="primary", use_container_width=True):
                if n_nom and foto_captura:
                    # 1. Generar Código
                    exist = supabase.table("productos").select("codigo").eq("categoria", n_cat).execute()
                    n_sku = f"{n_cat[:3]}-{n_sub[:3]}-{len(exist.data)+1:04d}".upper()
                    
                    # 2. Subir imagen a Supabase Storage
                    file_name = f"{n_sku}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    res_storage = supabase.storage.from_("fotos").upload(file_name, foto_captura.getvalue())
                    
                    # 3. Obtener URL pública
                    url_foto = supabase.storage.from_("fotos").get_public_url(file_name)
                    
                    # 4. Insertar en Base de Datos
                    supabase.table("productos").insert({
                        "codigo": n_sku, "nombre": n_nom, "categoria": n_cat,
                        "subcategoria": n_sub, "colores": n_col, "precio_inv": n_inv,
                        "precio_pub": n_pub, "stock": n_stk, "foto_path": url_foto
                    }).execute()
                    
                    st.success(f"Producto {n_sku} guardado con éxito.")
                    st.rerun()
                else:
                    st.error("Por favor ingresa el nombre y toma una foto.")

# --- 7. CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
    # (Lógica de categorías y subcategorías igual a la anterior)
    opc = st.radio("Editar:", ["Categorías", "Subcategorías"], horizontal=True)
    t_db = "categoria" if opc == "Categorías" else "subcategoria"
    n_val = st.text_input(f"Nueva {opc}").upper()
    if st.button("Añadir"):
        if n_val: supabase.table("configuracion").insert({"tipo": t_db, "valor": n_val}).execute(); st.rerun()
    res = supabase.table("configuracion").select("*").eq("tipo", t_db).execute()
    for r in res.data:
        c1, c2 = st.columns([5, 1])
        c1.write(r['valor'])
        if c2.button("🗑️", key=r['id']): supabase.table("configuracion").delete().eq("id", r['id']).execute(); st.rerun()

# --- 8. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes")
    res = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res.data:
        df_r = pd.DataFrame(res.data)
        st.dataframe(df_r, column_config={"foto_path": st.column_config.ImageColumn("Imagen")}, hide_index=True, use_container_width=True)
