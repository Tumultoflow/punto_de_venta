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
        st.session_state.carrito = []
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
            if st.button("➕ Añadir al Carrito"):
                id_temp = datetime.now().timestamp()
                st.session_state.carrito.append({
                    "temp_id": str(id_temp),
                    "id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'],
                    "color": v_col, "cantidad": v_cant, "precio": v_pre, 
                    "precio_inv": item['precio_inv'], "foto": item.get('foto_path')
                })
                st.toast("Producto añadido")

        if st.session_state.carrito:
            st.divider()
            st.subheader("🛒 Carrito de Compra")
            total_venta = 0
            for i, p in enumerate(st.session_state.carrito):
                col_item, col_del = st.columns([6, 1])
                subtotal = p['cantidad'] * p['precio']
                total_venta += subtotal
                t_id = p.get('temp_id', f"old_{i}")
                with col_item:
                    st.write(f"**{p['codigo']}** - {p['nombre']} ({p['color']}) | {p['cantidad']} pzs x ${p['precio']:,.2f} = **${subtotal:,.2f}**")
                with col_del:
                    if st.button("🗑️", key=f"del_{t_id}"):
                        st.session_state.carrito.pop(i)
                        st.rerun()
            
            st.markdown(f"### **Total a Pagar: ${total_venta:,.2f}**")
            st.divider()
            f1, f2 = st.columns(2)
            with f1: v_vendedor = st.text_input("Nombre del Vendedor")
            with f2: v_fecha_manual = st.date_input("📅 Fecha", value=datetime.now(ZONA_LOCAL).date())
            
            if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
                if v_vendedor:
                    fecha_final = datetime.combine(v_fecha_manual, datetime.now(ZONA_LOCAL).time()).isoformat()
                    for p in st.session_state.carrito:
                        stk_q = supabase.table("productos").select("stock").eq("id", p['id']).execute()
                        stk_actual = stk_q.data[0]['stock']
                        supabase.table("productos").update({"stock": stk_actual - p['cantidad']}).eq("id", p['id']).execute()
                        supabase.table("ventas").insert({
                            "producto": p['nombre'], "codigo_prod": p['codigo'], "color": p['color'],
                            "cantidad": p['cantidad'], "precio_total": p['precio'] * p['cantidad'],
                            "vendedor": v_vendedor, "ganancia": (p['precio'] - p['precio_inv']) * p['cantidad'],
                            "foto_path": p['foto'], "fecha_venta": fecha_final
                        }).execute()
                    st.session_state.carrito = []
                    st.success("Venta realizada")
                    st.rerun()

# --- 6. SECCIÓN: INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    cats = obtener_config("categoria")
    subs = obtener_config("subcategoria")
    
    tab1, tab2 = st.tabs(["📋 Existencias", "🆕 Nuevo Producto"])
    
    with tab1:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            df_i = pd.DataFrame(res.data)
            if st.session_state.role == "admin":
                st.subheader("🛠️ Editar o Eliminar")
                lista_editar = [f"{r['codigo']} - {r['nombre']}" for r in res.data]
                p_edit_raw = st.selectbox("Selecciona para modificar:", ["-- Seleccionar --"] + lista_editar)
                if p_edit_raw != "-- Seleccionar --":
                    it_edit = df_i[df_i['codigo'] == p_edit_raw.split(" - ")[0]].iloc[0]
                    with st.expander("📝 Panel de Edición", expanded=True):
                        e_c1, e_c2 = st.columns(2)
                        with e_c1:
                            idx_cat = cats.index(it_edit['categoria']) if it_edit['categoria'] in cats else 0
                            idx_sub = subs.index(it_edit['subcategoria']) if it_edit['subcategoria'] in subs else 0
                            e_nom = st.text_input("Nombre", value=it_edit['nombre'], key="ed_nom")
                            e_cat = st.selectbox("Categoría", cats, index=idx_cat, key="ed_cat")
                            e_sub = st.selectbox("Subcategoría", subs, index=idx_sub, key="ed_sub")
                        with e_c2:
                            e_inv = st.number_input("Costo", value=float(it_edit['precio_inv']), key="ed_inv")
                            e_pub = st.number_input("Público", value=float(it_edit['precio_pub']), key="ed_pub")
                            e_stk = st.number_input("Stock", value=int(it_edit['stock']), key="ed_stk")
                            sugerencia_sku = f"{e_cat[:3]}-{e_sub[:3]}-{it_edit['codigo'].split('-')[-1]}".upper()
                            e_cod = st.text_input("Código SKU", value=sugerencia_sku, key="ed_sku")
                        
                        eb1, eb2 = st.columns(2)
                        if eb1.button("💾 Guardar"):
                            supabase.table("productos").update({
                                "codigo": e_cod.upper(), "nombre": e_nom, "categoria": e_cat,
                                "subcategoria": e_sub, "precio_inv": e_inv, "precio_pub": e_pub, "stock": e_stk
                            }).eq("id", it_edit['id']).execute()
                            st.rerun()
                        if eb2.button("🗑️ Eliminar", type="primary"):
                            supabase.table("productos").delete().eq("id", it_edit['id']).execute()
                            st.rerun()
            st.data_editor(df_i, column_config={"foto_path": st.column_config.ImageColumn("Foto")}, hide_index=True)

    with tab2:
        if st.session_state.role == "admin":
            st.subheader("📝 Registrar Nuevo Producto")
            c_f, c_c = st.columns(2)
            with c_f:
                n_nom = st.text_input("Nombre del producto*", key="nw_nom")
                n_cat = st.selectbox("Categoría", cats, key="nw_cat")
                n_sub = st.selectbox("Subcategoría", subs, key="nw_sub")
                n_col = st.text_input("Colores (separados por coma)", key="nw_col") 
                n_inv = st.number_input("Precio Inversión", 0.0, key="nw_inv")
                n_pub = st.number_input("Precio Público", 0.0, key="nw_pub")
                n_stk = st.number_input("Stock Inicial", 1, key="nw_stk")
            with c_c:
                # CAMBIO AQUÍ: Ahora permite elegir archivo o usar cámara en móviles
                st.write("🖼️ Foto del Producto")
                foto = st.file_uploader("Sube una foto o tómala con el celular", type=['jpg', 'jpeg', 'png'], key="file_nw")
                if foto: st.image(foto, width=200)
            
            if st.button("🚀 REGISTRAR PRODUCTO", type="primary", use_container_width=True):
                if n_nom and foto:
                    try:
                        # Generación de Código
                        exist = supabase.table("productos").select("codigo").execute()
                        n_sku = f"{n_cat[:3]}-{n_sub[:3]}-{len(exist.data)+1:04d}".upper()
                        
                        # Subir imagen
                        fname = f"{n_sku}_{datetime.now().strftime('%H%M%S')}.jpg"
                        res_storage = supabase.storage.from_("fotos").upload(fname, foto.getvalue())
                        url_f = supabase.storage.from_("fotos").get_public_url(fname)
                        
                        # Insertar en DB
                        res_insert = supabase.table("productos").insert({
                            "codigo": n_sku, "nombre": n_nom, "categoria": n_cat, "subcategoria": n_sub,
                            "colores": n_col, "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk, "foto_path": url_f
                        }).execute()
                        
                        if res_insert.data:
                            st.success(f"Producto {n_sku} registrado con éxito.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar: {e}")
                else:
                    st.warning("Falta el nombre o la foto.")

# --- 7. CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
    opc = st.radio("Editar:", ["Categorías", "Subcategorías"], horizontal=True)
    t_db = "categoria" if opc == "Categorías" else "subcategoria"
    n_val = st.text_input(f"Nueva {opc}").upper()
    if st.button("➕ Añadir"):
        if n_val: supabase.table("configuracion").insert({"tipo": t_db, "valor": n_val}).execute(); st.rerun()
    res = supabase.table("configuracion").select("*").eq("tipo", t_db).execute()
    if res.data:
        for r in res.data:
            c1, c2 = st.columns([5, 1])
            c1.write(f"▪️ {r['valor']}")
            if c2.button("🗑️", key=f"cfg_{r['id']}"):
                supabase.table("configuracion").delete().eq("id", r['id']).execute(); st.rerun()

# --- 8. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_r = pd.DataFrame(res_v.data)
        st.metric("Ganancia Total", f"${df_r['ganancia'].sum():,.2f}")
        st.dataframe(df_r, use_container_width=True)
