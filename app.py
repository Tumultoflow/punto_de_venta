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
        # Buscamos productos que empiecen con ese prefijo para contar la secuencia
        res = supabase.table("productos").select("codigo").like("codigo", f"{prefijo}%").execute()
        conteo = len(res.data) + 1
        return f"{prefijo}-{conteo:04d}"
    except:
        return f"{prefijo}-0001"

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
            st.info(f"**Stock disponible:** {item['stock']}")
        
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
                st.toast("Añadido correctamente")

        if st.session_state.carrito:
            st.divider()
            st.subheader("🛒 Carrito Actual")
            total_venta = 0
            for i, p in enumerate(st.session_state.carrito):
                col_item, col_del = st.columns([6, 1])
                subtotal = p['cantidad'] * p['precio']
                total_venta += subtotal
                t_id = p.get('temp_id', f"old_{i}")
                with col_item:
                    st.write(f"**{p['nombre']}** ({p['color']}) | {p['cantidad']} pzs x ${p['precio']:,.2f} = **${subtotal:,.2f}**")
                with col_del:
                    if st.button("🗑️", key=f"del_{t_id}"):
                        st.session_state.carrito.pop(i)
                        st.rerun()
            
            st.markdown(f"### **Total: ${total_venta:,.2f}**")
            st.divider()
            f1, f2 = st.columns(2)
            with f1: v_vendedor = st.text_input("Vendedor")
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
                    st.success("¡Venta Guardada!")
                    st.rerun()

# --- 6. SECCIÓN: INVENTARIO ---
elif menu == "Inventario":
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
                    ID_K = it_edit['codigo'] 
                    
                    with st.expander("📝 Formulario de Edición", expanded=True):
                        e_c1, e_c2 = st.columns(2)
                        with e_c1:
                            idx_cat = cats.index(it_edit['categoria']) if it_edit['categoria'] in cats else 0
                            idx_sub = subs.index(it_edit['subcategoria']) if it_edit['subcategoria'] in subs else 0
                            e_nom = st.text_input("Nombre", value=it_edit['nombre'], key=f"nom_{ID_K}")
                            e_cat = st.selectbox("Categoría", cats, index=idx_cat, key=f"cat_{ID_K}")
                            e_sub = st.selectbox("Subcategoría", subs, index=idx_sub, key=f"sub_{ID_K}")
                            e_col = st.text_input("Colores", value=it_edit.get('colores', ''), key=f"col_{ID_K}")
                        with e_c2:
                            e_inv = st.number_input("Costo (Inversión)", value=float(it_edit['precio_inv']), key=f"inv_{ID_K}")
                            e_pub = st.number_input("Precio Público", value=float(it_edit['precio_pub']), key=f"pub_{ID_K}")
                            e_stk = st.number_input("Stock Actual", value=int(it_edit['stock']), key=f"stk_{ID_K}")
                            e_cod = st.text_input("Código SKU", value=it_edit['codigo'], key=f"sku_{ID_K}")
                        
                        eb1, eb2 = st.columns(2)
                        if eb1.button("💾 Guardar Cambios", use_container_width=True):
                            supabase.table("productos").update({
                                "codigo": e_cod.upper(), "nombre": e_nom, "categoria": e_cat,
                                "subcategoria": e_sub, "colores": e_col, "precio_inv": e_inv, 
                                "precio_pub": e_pub, "stock": e_stk
                            }).eq("id", it_edit['id']).execute()
                            st.success("Cambios aplicados")
                            st.rerun()
                        if eb2.button("🗑️ ELIMINAR TOTALMENTE", type="primary", use_container_width=True):
                            supabase.table("productos").delete().eq("id", it_edit['id']).execute()
                            st.warning("Producto eliminado")
                            st.rerun()
                st.divider()

            st.data_editor(df_i, column_config={"foto_path": st.column_config.ImageColumn("Foto")}, hide_index=True, use_container_width=True)

    with tab2:
        if st.session_state.role == "admin":
            st.subheader("🆕 Registrar Nuevo")
            c1, c2 = st.columns(2)
            with c1:
                n_cat = st.selectbox("1. Seleccionar Categoría", cats, key="nw_cat")
                n_sub = st.selectbox("2. Seleccionar Subcategoría", subs, key="nw_sub")
                
                # GENERACIÓN DE SKU EN TIEMPO REAL
                sku_generado = generar_sku(n_cat, n_sub)
                st.info(f"✨ Código sugerido: **{sku_generado}**")
                
                n_cod = st.text_input("3. Confirmar Código SKU", value=sku_generado)
                n_nom = st.text_input("4. Nombre del Producto*")
                n_col = st.text_input("5. Colores (Rojo, Azul, etc)")
                n_inv = st.number_input("6. Precio Inversión", 0.0)
                n_pub = st.number_input("7. Precio Público", 0.0)
                n_stk = st.number_input("8. Stock Inicial", 1)
            with c2:
                st.write("🖼️ Imagen del Producto")
                foto = st.file_uploader("Subir foto o capturar", type=['jpg', 'png', 'jpeg'])
                if foto: st.image(foto, width=200)
            
            if st.button("🚀 REGISTRAR PRODUCTO", type="primary", use_container_width=True):
                if n_nom and foto and n_cod:
                    try:
                        fname = f"{n_cod}_{datetime.now().strftime('%H%M%S')}.jpg"
                        supabase.storage.from_("fotos").upload(fname, foto.getvalue())
                        url = supabase.storage.from_("fotos").get_public_url(fname)
                        supabase.table("productos").insert({
                            "codigo": n_cod.upper(), "nombre": n_nom, "categoria": n_cat, "subcategoria": n_sub,
                            "colores": n_col, "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk, "foto_path": url
                        }).execute()
                        st.success(f"¡Producto {n_cod} guardado exitosamente!")
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

# --- 7. CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
    tipo = st.radio("Editar:", ["Categorías", "Subcategorías"], horizontal=True)
    t_db = "categoria" if tipo == "Categorías" else "subcategoria"
    n_val = st.text_input(f"Nuevo valor para {tipo}").upper()
    if st.button("➕ Agregar"):
        if n_val: supabase.table("configuracion").insert({"tipo": t_db, "valor": n_val}).execute(); st.rerun()
    res = supabase.table("configuracion").select("*").eq("tipo", t_db).execute()
    for r in res.data:
        col_t, col_b = st.columns([5, 1])
        col_t.write(f"• {r['valor']}")
        if col_b.button("🗑️", key=f"cfg_{r['id']}"):
            supabase.table("configuracion").delete().eq("id", r['id']).execute(); st.rerun()

# --- 8. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes Detallados")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    
    if res_v.data:
        df_r = pd.DataFrame(res_v.data)
        df_r['fecha_venta'] = pd.to_datetime(df_r['fecha_venta'])

        m1, m2, m3, m4 = st.columns(4)
        total_v = df_r['precio_total'].sum()
        total_g = df_r['ganancia'].sum()
        m1.metric("Ingresos", f"${total_v:,.2f}")
        m2.metric("Ganancia", f"${total_g:,.2f}")
        m3.metric("Productos", f"{df_r['cantidad'].sum()}")
        m4.metric("Ventas", len(df_r))

        st.divider()
        st.subheader("📝 Historial de Ventas")
        st.dataframe(
            df_r, 
            column_order=("foto_path", "fecha_venta", "codigo_prod", "producto", "color", "cantidad", "precio_total", "ganancia", "vendedor"),
            column_config={
                "foto_path": st.column_config.ImageColumn("Foto"),
                "fecha_venta": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YY HH:mm"),
                "precio_total": st.column_config.NumberColumn("Venta", format="$%.2f"),
                "ganancia": st.column_config.NumberColumn("Ganancia", format="$%.2f"),
            }, 
            hide_index=True, use_container_width=True
        )
        st.divider()
        st.subheader("📈 Tendencia")
        st.line_chart(df_r.groupby(df_r['fecha_venta'].dt.date)['precio_total'].sum())
    else:
        st.info("Sin registros de ventas.")
