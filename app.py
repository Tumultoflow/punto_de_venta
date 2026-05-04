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
    prefijo = f"{cat[:3]}-{sub[:3]}".upper()
    try:
        res = supabase.table("productos").select("codigo").like("codigo", f"{prefijo}%").execute()
        secuencias = []
        for r in res.data:
            try:
                num = int(r['codigo'].split('-')[-1])
                secuencias.append(num)
            except:
                continue
        proximo = max(secuencias) + 1 if secuencias else 1
        return f"{prefijo}-{proximo:04d}"
    except:
        return f"{prefijo}-0001"

# --- 3. SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []

# --- 4. LOGIN ---
if not st.session_state.auth:
    st.title("🔐 Acceso")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if u == "admin" and p == "admin1": 
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
    st.stop()

# --- 5. INTERFAZ ---
with st.sidebar:
    st.title("⚖️ TUMULTOFLOW")
    menu = st.radio("Menú", ["Ventas", "Inventario", "Configuración", "Reportes"])
    if st.button("Cerrar Sesión"):
        st.session_state.auth = False
        st.rerun()

# --- VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
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
            st.subheader(item['nombre'])
            st.caption(item.get('descripcion', 'Sin descripción'))
            v_col = st.selectbox("🎨 Color", [c.strip().upper() for c in item['colores'].split(',') if c.strip()] if item.get('colores') else ["ÚNICO"])
            v_cant = st.number_input("Cantidad", 1, int(item['stock']))
            v_pre = st.number_input("Precio", value=float(item['precio_pub']))
            if st.button("➕ Añadir"):
                st.session_state.carrito.append({
                    "id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'],
                    "color": v_col, "cantidad": v_cant, "precio": v_pre, 
                    "precio_inv": item['precio_inv'], "foto": item.get('foto_path')
                })
                st.rerun()

        if st.session_state.carrito:
            st.divider()
            total_v = sum(p['precio'] * p['cantidad'] for p in st.session_state.carrito)
            st.markdown(f"### Total: ${total_v:,.2f}")
            v_vend = st.text_input("Vendedor")
            if st.button("🚀 FINALIZAR VENTA", type="primary") and v_vend:
                for p in st.session_state.carrito:
                    stk = supabase.table("productos").select("stock").eq("id", p['id']).execute().data[0]['stock']
                    supabase.table("productos").update({"stock": stk - p['cantidad']}).eq("id", p['id']).execute()
                    supabase.table("ventas").insert({
                        "producto": p['nombre'], "codigo_prod": p['codigo'], "color": p['color'],
                        "cantidad": p['cantidad'], "precio_total": p['precio']*p['cantidad'],
                        "vendedor": v_vend, "ganancia": (p['precio'] - p['precio_inv']) * p['cantidad'],
                        "foto_path": p['foto']
                    }).execute()
                st.session_state.carrito = []
                st.rerun()

# --- INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    cats, subs = obtener_config("categoria"), obtener_config("subcategoria")
    t1, t2 = st.tabs(["📋 Catálogo", "🆕 Nuevo Producto"])
    
    with t1:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            df_i = pd.DataFrame(res.data)
            sel_edit = st.selectbox("Editar producto:", ["-- Seleccionar --"] + [f"{r['codigo']} - {r['nombre']}" for r in res.data])
            
            if sel_edit != "-- Seleccionar --":
                it_e = df_i[df_i['codigo'] == sel_edit.split(" - ")[0]].iloc[0]
                with st.expander("✏️ Modificar Producto", expanded=True):
                    # --- SECCIÓN DE IMAGEN EN EDICIÓN ---
                    c_img1, c_img2 = st.columns([1, 2])
                    with c_img1:
                        st.markdown("**Imagen Actual:**")
                        if it_e.get('foto_path'):
                            st.image(it_e['foto_path'], width=150)
                        else:
                            st.write("Sin imagen")
                    with c_img2:
                        nueva_foto = st.file_uploader("🖼️ Cambiar Imagen (Opcional)", type=['jpg','png','jpeg'], key="edit_foto")
                    
                    st.divider()
                    e_desc = st.text_area("Descripción", value=it_e.get('descripcion', ''))
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        e_nom = st.text_input("Nombre", value=it_e['nombre'])
                        e_cat = st.selectbox("Categoría", cats, index=cats.index(it_e['categoria']) if it_e['categoria'] in cats else 0)
                        e_sub = st.selectbox("Subcategoría", subs, index=subs.index(it_e['subcategoria']) if it_e['subcategoria'] in subs else 0)
                        e_col = st.text_input("Colores", value=it_e['colores'])
                    with c2:
                        sku_val = generar_sku(e_cat, e_sub) if (e_cat != it_e['categoria'] or e_sub != it_e['subcategoria']) else it_e['codigo']
                        e_cod = st.text_input("SKU", value=sku_val)
                        e_inv = st.number_input("Costo", value=float(it_e['precio_inv']))
                        e_pub = st.number_input("Venta", value=float(it_e['precio_pub']))
                        e_stk = st.number_input("Stock", value=int(it_e['stock']))
                    
                    b1, b2 = st.columns(2)
                    if b1.button("💾 GUARDAR CAMBIOS", use_container_width=True):
                        # Lógica para subir nueva foto si existe
                        url_foto = it_e['foto_path']
                        if nueva_foto:
                            fname = f"{e_cod}_{datetime.now().strftime('%H%M%S')}.jpg"
                            supabase.storage.from_("fotos").upload(fname, nueva_foto.getvalue())
                            url_foto = supabase.storage.from_("fotos").get_public_url(fname)
                        
                        supabase.table("productos").update({
                            "nombre": e_nom, "codigo": e_cod.upper(), "categoria": e_cat,
                            "subcategoria": e_sub, "colores": e_col, "precio_inv": e_inv,
                            "precio_pub": e_pub, "stock": e_stk, "descripcion": e_desc,
                            "foto_path": url_foto
                        }).eq("id", it_e['id']).execute()
                        st.success("¡Producto actualizado!")
                        st.rerun()
                    
                    if b2.button("🗑️ ELIMINAR", type="primary", use_container_width=True):
                        supabase.table("productos").delete().eq("id", it_e['id']).execute()
                        st.rerun()

            st.divider()
            st.dataframe(df_i, column_config={"foto_path": st.column_config.ImageColumn("Foto")}, use_container_width=True)

    with t2:
        with st.form("nuevo_p"):
            n_nom = st.text_input("Nombre")
            n_desc = st.text_area("Descripción")
            c1, c2 = st.columns(2)
            with c1:
                n_cat = st.selectbox("Categoría", cats)
                n_sub = st.selectbox("Subcategoría", subs)
                n_cod = st.text_input("SKU Sugerido", value=generar_sku(n_cat, n_sub))
                n_col = st.text_input("Colores")
            with c2:
                n_inv = st.number_input("Costo", 0.0)
                n_pub = st.number_input("Venta", 0.0)
                n_stk = st.number_input("Stock Inicial", 1)
                n_foto = st.file_uploader("Imagen", type=['jpg','png','jpeg'])
            
            if st.form_submit_button("🚀 REGISTRAR"):
                if n_nom and n_foto:
                    fname = f"{n_cod}_{datetime.now().strftime('%H%M%S')}.jpg"
                    supabase.storage.from_("fotos").upload(fname, n_foto.getvalue())
                    url = supabase.storage.from_("fotos").get_public_url(fname)
                    supabase.table("productos").insert({
                        "codigo": n_cod.upper(), "nombre": n_nom, "descripcion": n_desc, 
                        "categoria": n_cat, "subcategoria": n_sub, "colores": n_col, 
                        "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk, "foto_path": url
                    }).execute()
                    st.rerun()

# --- RESTO DEL CÓDIGO (Configuración y Reportes) ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
    tipo = st.radio("Gestionar:", ["Categorías", "Subcategorías"], horizontal=True)
    db_col = "categoria" if tipo == "Categorías" else "subcategoria"
    val = st.text_input(f"Añadir {tipo}").upper()
    if st.button("➕ Agregar") and val:
        supabase.table("configuracion").insert({"tipo": db_col, "valor": val}).execute(); st.rerun()
    res = supabase.table("configuracion").select("*").eq("tipo", db_col).execute()
    for r in res.data:
        v, b = st.columns([5, 1])
        v.write(f"• {r['valor']}")
        if b.button("🗑️", key=r['id']):
            supabase.table("configuracion").delete().eq("id", r['id']).execute(); st.rerun()

elif menu == "Reportes":
    st.header("📊 Reportes")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_r = pd.DataFrame(res_v.data)
        st.metric("Total Ventas", f"${df_r['precio_total'].sum():,.2f}")
        st.dataframe(df_r, column_config={"foto_path": st.column_config.ImageColumn("Foto")}, use_container_width=True)
