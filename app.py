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

st.set_page_config(page_title="TUMULTOFLOW ULTIMATE", layout="wide", page_icon="⚖️")

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

# --- 5. SECCIÓN: VENTAS ---
if menu == "Ventas":
    st.header("💰 Venta Multi-Color")
    res = supabase.table("productos").select("*").gt("stock", 0).order("codigo").execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        opciones = [f"{r['codigo']} - {r['nombre']}" for r in res.data]
        sel_prod = st.selectbox("📦 Seleccionar Producto", opciones)
        item = df_p[df_p['codigo'] == sel_prod.split(" - ")[0]].iloc[0]
        
        c1, c2 = st.columns([1, 2])
        with c1:
            if item.get('foto_path'): st.image(item['foto_path'], width=250)
            st.info(f"**Stock:** {item['stock']}")
        
        with c2:
            colores = [c.strip().upper() for c in item['colores'].split(',') if c.strip()] if item.get('colores') else ["ÚNICO"]
            v_col = st.selectbox("🎨 Color", colores)
            v_cant = st.number_input("Cantidad", 1, int(item['stock']))
            v_pre = st.number_input("Precio Venta", value=float(item['precio_pub']))
            if st.button("➕ Añadir"):
                st.session_state.carrito.append({
                    "id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'],
                    "color": v_col, "cantidad": v_cant, "precio": v_pre, 
                    "precio_inv": item['precio_inv'], "foto": item.get('foto_path')
                })
                st.toast("Producto añadido")

        if st.session_state.carrito:
            st.divider()
            df_car = pd.DataFrame(st.session_state.carrito)
            st.table(df_car[["codigo", "nombre", "color", "cantidad", "precio"]])
            v_vend = st.text_input("Vendedor")
            if st.button("🚀 FINALIZAR VENTA", type="primary"):
                if v_vend:
                    for p in st.session_state.carrito:
                        stk = supabase.table("productos").select("stock").eq("id", p['id']).execute().data[0]['stock']
                        supabase.table("productos").update({"stock": stk - p['cantidad']}).eq("id", p['id']).execute()
                        supabase.table("ventas").insert({
                            "producto": p['nombre'], "codigo_prod": p['codigo'], "color": p['color'],
                            "cantidad": p['cantidad'], "precio_total": p['precio'] * p['cantidad'],
                            "vendedor": v_vend, "ganancia": (p['precio'] - p['precio_inv']) * p['cantidad'],
                            "foto_path": p['foto'], "fecha_venta": datetime.now(ZONA_LOCAL).isoformat()
                        }).execute()
                    st.session_state.carrito = []
                    st.success("Venta exitosa")
                    st.rerun()

# --- 6. SECCIÓN: INVENTARIO (CON EDICIÓN, ELIMINACIÓN Y CÁMARA) ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    cats = obtener_config("categoria")
    subs = obtener_config("subcategoria")
    
    tab1, tab2 = st.tabs(["📋 Existencias y Edición", "🆕 Nuevo Producto (Cámara)"])
    
    with tab1:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            df_i = pd.DataFrame(res.data)
            
            # --- APARTADO DE EDICIÓN Y ELIMINACIÓN ---
            if st.session_state.role == "admin":
                st.subheader("🛠️ Editar o Eliminar Producto")
                lista_editar = [f"{r['codigo']} - {r['nombre']}" for r in res.data]
                p_edit_raw = st.selectbox("Selecciona para modificar:", ["-- Seleccionar --"] + lista_editar)
                
                if p_edit_raw != "-- Seleccionar --":
                    it_edit = df_i[df_i['codigo'] == p_edit_raw.split(" - ")[0]].iloc[0]
                    with st.expander("📝 Panel de Edición Directa", expanded=True):
                        e_c1, e_c2 = st.columns(2)
                        with e_c1:
                            e_cod = st.text_input("Código (Manual)", value=it_edit['codigo'])
                            e_nom = st.text_input("Nombre", value=it_edit['nombre'])
                            e_col = st.text_input("Colores", value=it_edit.get('colores', ''))
                        with e_c2:
                            e_inv = st.number_input("Costo", value=float(it_edit['precio_inv']))
                            e_pub = st.number_input("Público", value=float(it_edit['precio_pub']))
                            e_stk = st.number_input("Stock", value=int(it_edit['stock']))
                        
                        eb1, eb2 = st.columns(2)
                        if eb1.button("💾 Guardar Cambios", use_container_width=True):
                            supabase.table("productos").update({
                                "codigo": e_cod.upper(), "nombre": e_nom, "colores": e_col,
                                "precio_inv": e_inv, "precio_pub": e_pub, "stock": e_stk
                            }).eq("id", it_edit['id']).execute()
                            st.success("¡Actualizado!")
                            st.rerun()
                        if eb2.button("🗑️ ELIMINAR PRODUCTO", type="primary", use_container_width=True):
                            supabase.table("productos").delete().eq("id", it_edit['id']).execute()
                            st.rerun()
                st.divider()

            st.data_editor(df_i, column_config={"foto_path": st.column_config.ImageColumn("Foto")}, hide_index=True, use_container_width=True)

    with tab2:
        if st.session_state.role == "admin":
            c_f, c_c = st.columns(2)
            with c_f:
                n_nom = st.text_input("Nombre*")
                n_cat = st.selectbox("Categoría", cats)
                n_sub = st.selectbox("Subcategoría", subs)
                n_col = st.text_input("Colores")
                n_inv = st.number_input("Inversión", 0.0)
                n_pub = st.number_input("Público", 0.0)
                n_stk = st.number_input("Stock", 1)
            with c_c:
                st.write("📸 Captura de Imagen")
                foto = st.camera_input("Tomar foto")
            
            if st.button("🚀 REGISTRAR PRODUCTO", type="primary", use_container_width=True):
                if n_nom and foto:
                    exist = supabase.table("productos").select("codigo").eq("categoria", n_cat).execute()
                    n_sku = f"{n_cat[:3]}-{n_sub[:3]}-{len(exist.data)+1:04d}".upper()
                    # Subir Foto
                    fname = f"{n_sku}_{datetime.now().strftime('%M%S')}.jpg"
                    supabase.storage.from_("fotos").upload(fname, foto.getvalue())
                    url_f = supabase.storage.from_("fotos").get_public_url(fname)
                    # Insertar
                    supabase.table("productos").insert({
                        "codigo": n_sku, "nombre": n_nom, "categoria": n_cat, "subcategoria": n_sub,
                        "colores": n_col, "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk, "foto_path": url_f
                    }).execute()
                    st.success("Guardado")
                    st.rerun()

# --- 7. SECCIÓN: CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
    opc = st.radio("Editar:", ["Categorías", "Subcategorías"], horizontal=True)
    t_db = "categoria" if opc == "Categorías" else "subcategoria"
    
    n_val = st.text_input(f"Nueva {opc}").upper()
    if st.button("➕ Añadir"):
        if n_val: supabase.table("configuracion").insert({"tipo": t_db, "valor": n_val}).execute(); st.rerun()
    
    res = supabase.table("configuracion").select("*").eq("tipo", t_db).execute()
    for r in res.data:
        c1, c2 = st.columns([5, 1])
        c1.write(f"▪️ {r['valor']}")
        if c2.button("🗑️", key=r['id']):
            supabase.table("configuracion").delete().eq("id", r['id']).execute()
            st.rerun()

# --- 8. SECCIÓN: REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes")
    res = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res.data:
        df_r = pd.DataFrame(res.data)
        st.dataframe(df_r, column_config={"foto_path": st.column_config.ImageColumn("Foto")}, hide_index=True, use_container_width=True)
