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

def generar_sku(cat, sub):
    """Genera un SKU basado en el conteo actual de esa categoría/subcategoría"""
    prefijo = f"{cat[:3]}-{sub[:3]}".upper()
    try:
        res = supabase.table("productos").select("codigo").like("codigo", f"{prefijo}%").execute()
        conteo = len(res.data) + 1
        return f"{prefijo}-{conteo:04d}"
    except:
        return f"{prefijo}-0001"

def validar_existencia_sku(sku, id_actual=None):
    """Verifica si el SKU ya existe en la base de datos (excluyendo el producto actual)"""
    query = supabase.table("productos").select("id").eq("codigo", sku.upper())
    if id_actual:
        query = query.neq("id", id_actual)
    res = query.execute()
    return len(res.data) > 0

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

# --- 6. SECCIÓN: INVENTARIO ---
if menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    cats = obtener_config("categoria")
    subs = obtener_config("subcategoria")
    
    tab1, tab2 = st.tabs(["📋 Existencias y Edición", "🆕 Agregar Nuevo Producto"])
    
    with tab1:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            df_i = pd.DataFrame(res.data)
            
            if st.session_state.role == "admin":
                st.subheader("🛠️ Editar o Eliminar Producto")
                lista_editar = [f"{r['codigo']} - {r['nombre']}" for r in res.data]
                p_edit_raw = st.selectbox("Selecciona un producto para modificar:", ["-- Seleccionar --"] + lista_editar)
                
                if p_edit_raw != "-- Seleccionar --":
                    cod_sel = p_edit_raw.split(" - ")[0]
                    it_edit = df_i[df_i['codigo'] == cod_sel].iloc[0]
                    
                    # Key dinámica para resetear widgets al cambiar de producto
                    ID_K = it_edit['codigo'] 
                    
                    with st.expander("📝 Formulario de Edición Reactivo", expanded=True):
                        e_c1, e_c2 = st.columns(2)
                        with e_c1:
                            idx_cat = cats.index(it_edit['categoria']) if it_edit['categoria'] in cats else 0
                            idx_sub = subs.index(it_edit['subcategoria']) if it_edit['subcategoria'] in subs else 0
                            
                            e_nom = st.text_input("Nombre", value=it_edit['nombre'], key=f"nom_{ID_K}")
                            e_cat = st.selectbox("Nueva Categoría", cats, index=idx_cat, key=f"cat_{ID_K}")
                            e_sub = st.selectbox("Nueva Subcategoría", subs, index=idx_sub, key=f"sub_{ID_K}")
                            e_col = st.text_input("Colores", value=it_edit.get('colores', ''), key=f"col_{ID_K}")
                        
                        with e_c2:
                            # Lógica reactiva de SKU
                            if e_cat != it_edit['categoria'] or e_sub != it_edit['subcategoria']:
                                sku_propuesto = generar_sku(e_cat, e_sub)
                                st.info(f"🔄 Cambio de categoría. Nueva secuencia: **{sku_propuesto}**")
                            else:
                                sku_propuesto = it_edit['codigo']

                            e_cod = st.text_input("Código SKU (Editable)", value=sku_propuesto, key=f"sku_{ID_K}")
                            
                            # Validar si el código escrito ya existe (avisar al usuario)
                            if validar_existencia_sku(e_cod, it_edit['id']):
                                st.error(f"❌ El código **{e_cod}** ya está asignado a otro producto.")
                                bloqueado = True
                            else:
                                if e_cod != it_edit['codigo']:
                                    st.success(f"✅ Código **{e_cod}** disponible.")
                                bloqueado = False

                            e_inv = st.number_input("Costo (Inversión)", value=float(it_edit['precio_inv']), key=f"inv_{ID_K}")
                            e_pub = st.number_input("Precio Público", value=float(it_edit['precio_pub']), key=f"pub_{ID_K}")
                            e_stk = st.number_input("Stock Actual", value=int(it_edit['stock']), key=f"stk_{ID_K}")
                        
                        eb1, eb2 = st.columns(2)
                        if eb1.button("💾 Guardar Cambios", use_container_width=True, disabled=bloqueado):
                            supabase.table("productos").update({
                                "codigo": e_cod.upper(), "nombre": e_nom, "categoria": e_cat,
                                "subcategoria": e_sub, "colores": e_col, "precio_inv": e_inv, 
                                "precio_pub": e_pub, "stock": e_stk
                            }).eq("id", it_edit['id']).execute()
                            st.success("Cambios aplicados")
                            st.rerun()
                        if eb2.button("🗑️ ELIMINAR", type="primary", use_container_width=True):
                            supabase.table("productos").delete().eq("id", it_edit['id']).execute()
                            st.rerun()
                st.divider()

            st.data_editor(df_i, column_config={"foto_path": st.column_config.ImageColumn("Foto")}, hide_index=True, use_container_width=True)

    with tab2:
        if st.session_state.role == "admin":
            st.subheader("🆕 Registrar Nuevo")
            c1, c2 = st.columns(2)
            with c1:
                n_cat = st.selectbox("Categoría", cats, key="nw_cat")
                n_sub = st.selectbox("Subcategoría", subs, key="nw_sub")
                
                sku_nuevo = generar_sku(n_cat, n_sub)
                n_cod = st.text_input("Código SKU (Autogenerado)", value=sku_nuevo)
                
                # Validación de duplicados para nuevos
                if validar_existencia_sku(n_cod):
                    st.error("⚠️ Este código ya existe. Intenta con otra secuencia.")
                    bloqueo_nuevo = True
                else:
                    bloqueo_nuevo = False
                
                n_nom = st.text_input("Nombre del Producto*")
                n_col = st.text_input("Colores")
                n_inv = st.number_input("Precio Inversión", 0.0)
                n_pub = st.number_input("Precio Público", 0.0)
                n_stk = st.number_input("Stock Inicial", 1)
            with c2:
                st.write("🖼️ Imagen")
                foto = st.file_uploader("Subir foto", type=['jpg', 'png', 'jpeg'])
                if foto: st.image(foto, width=200)
            
            if st.button("🚀 REGISTRAR", type="primary", use_container_width=True, disabled=bloqueo_nuevo):
                if n_nom and foto:
                    try:
                        fname = f"{n_cod}_{datetime.now().strftime('%H%M%S')}.jpg"
                        supabase.storage.from_("fotos").upload(fname, foto.getvalue())
                        url = supabase.storage.from_("fotos").get_public_url(fname)
                        supabase.table("productos").insert({
                            "codigo": n_cod.upper(), "nombre": n_nom, "categoria": n_cat, "subcategoria": n_sub,
                            "colores": n_col, "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk, "foto_path": url
                        }).execute()
                        st.success(f"Registrado como {n_cod}")
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

# --- SECCIONES RESTANTES (VENTAS, CONFIG, REPORTES) IGUAL QUE ANTES ---
# (Se omite el código repetitivo de Ventas y Reportes por brevedad, pero se mantiene la lógica funcional)
elif menu == "Ventas":
    st.header("💰 Nueva Venta")
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
                st.session_state.carrito.append({"id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'], "color": v_col, "cantidad": v_cant, "precio": v_pre, "precio_inv": item['precio_inv'], "foto": item.get('foto_path')})
                st.rerun()

        if st.session_state.carrito:
            st.divider()
            total_venta = 0
            for i, p in enumerate(st.session_state.carrito):
                st.write(f"**{p['nombre']}** - {p['cantidad']} pzs x ${p['precio']} = ${p['cantidad']*p['precio']}")
                total_venta += p['cantidad']*p['precio']
            st.write(f"### Total: ${total_venta}")
            v_vend = st.text_input("Vendedor")
            if st.button("🚀 FINALIZAR VENTA") and v_vend:
                for p in st.session_state.carrito:
                    # Actualizar stock y registrar venta
                    stk_q = supabase.table("productos").select("stock").eq("id", p['id']).execute()
                    supabase.table("productos").update({"stock": stk_q.data[0]['stock'] - p['cantidad']}).eq("id", p['id']).execute()
                    supabase.table("ventas").insert({"producto": p['nombre'], "codigo_prod": p['codigo'], "color": p['color'], "cantidad": p['cantidad'], "precio_total": p['precio']*p['cantidad'], "vendedor": v_vend, "ganancia": (p['precio']-p['precio_inv'])*p['cantidad'], "foto_path": p['foto']}).execute()
                st.session_state.carrito = []
                st.rerun()

elif menu == "Configuración":
    st.header("⚙️ Configuración")
    tipo = st.radio("Editar:", ["Categorías", "Subcategorías"], horizontal=True)
    t_db = "categoria" if tipo == "Categorías" else "subcategoria"
    n_val = st.text_input(f"Nuevo valor").upper()
    if st.button("➕ Agregar") and n_val:
        supabase.table("configuracion").insert({"tipo": t_db, "valor": n_val}).execute(); st.rerun()
    res = supabase.table("configuracion").select("*").eq("tipo", t_db).execute()
    for r in res.data:
        if st.button(f"🗑️ {r['valor']}", key=r['id']):
            supabase.table("configuracion").delete().eq("id", r['id']).execute(); st.rerun()

elif menu == "Reportes":
    st.header("📊 Reportes")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_r = pd.DataFrame(res_v.data)
        st.metric("Total Ingresos", f"${df_r['precio_total'].sum():,.2f}")
        st.dataframe(df_r, use_container_width=True)
