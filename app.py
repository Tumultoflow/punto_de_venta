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
    """Genera el siguiente SKU disponible: CAT-SUB-0001"""
    prefijo = f"{cat[:3]}-{sub[:3]}".upper()
    try:
        res = supabase.table("productos").select("codigo").like("codigo", f"{prefijo}%").execute()
        secuencias = []
        for r in res.data:
            try: secuencias.append(int(r['codigo'].split('-')[-1]))
            except: continue
        proximo = max(secuencias) + 1 if secuencias else 1
        return f"{prefijo}-{proximo:04d}"
    except:
        return f"{prefijo}-0001"

def reestructurar_todos_los_codigos():
    """⚠️ Migración masiva: Reasigna todos los códigos desde 0001 por categoría"""
    productos = supabase.table("productos").select("*").order("created_at").execute()
    if not productos.data: return
    contadores = {}
    for p in productos.data:
        pref = f"{p['categoria'][:3]}-{p['subcategoria'][:3]}".upper()
        contadores[pref] = contadores.get(pref, 0) + 1
        nuevo_sku = f"{pref}-{contadores[pref]:04d}"
        supabase.table("productos").update({"codigo": nuevo_sku}).eq("id", p['id']).execute()

# --- 3. ESTADO DE SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []

if not st.session_state.auth:
    st.title("🔐 Acceso")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "admin1": 
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
    st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("⚖️ TUMULTOFLOW")
    st.markdown(f"**Rol:** `{st.session_state.role.upper()}`")
    menu = st.radio("Menú", ["Ventas", "Inventario", "Configuración", "Reportes"])
    if st.button("Cerrar Sesión"):
        st.session_state.auth = False
        st.rerun()

# --- 4. VENTAS ---
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
            st.info(f"**Stock:** {item['stock']} unidades")
        with c2:
            colores = [c.strip().upper() for c in item['colores'].split(',') if c.strip()] if item.get('colores') else ["ÚNICO"]
            v_col = st.selectbox("🎨 Color", colores)
            v_cant = st.number_input("Cantidad", 1, int(item['stock']))
            v_pre = st.number_input("Precio de Venta", value=float(item['precio_pub']))
            if st.button("➕ Añadir"):
                st.session_state.carrito.append({
                    "id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'],
                    "color": v_col, "cantidad": v_cant, "precio": v_pre, 
                    "precio_inv": item['precio_inv'], "foto": item.get('foto_path')
                })
                st.toast("Añadido al carrito")

        if st.session_state.carrito:
            st.divider()
            st.subheader("🛒 Carrito Actual")
            total_v = 0
            for i, p in enumerate(st.session_state.carrito):
                sub = p['precio'] * p['cantidad']
                total_v += sub
                col_i, col_d = st.columns([5, 1])
                col_i.write(f"**{p['nombre']}** ({p['color']}) - {p['cantidad']} pzs x ${p['precio']} = **${sub}**")
                if col_d.button("🗑️", key=f"del_{i}"):
                    st.session_state.carrito.pop(i)
                    st.rerun()
            
            st.markdown(f"### Total: ${total_v:,.2f}")
            v_vend = st.text_input("Nombre del Vendedor")
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
                st.success("Venta Guardada")
                st.rerun()

# --- 5. INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    cats = obtener_config("categoria")
    subs = obtener_config("subcategoria")

    if st.session_state.role == "admin":
        with st.expander("🛠️ Zona de Reorganización (Cuidado)"):
            st.write("Esto reiniciará todos los códigos desde 0001 según su categoría actual.")
            if st.button("♻️ RECOMENZAR SECUENCIAS DESDE 0001"):
                reestructurar_todos_los_codigos()
                st.rerun()

    t1, t2 = st.tabs(["📋 Existencias", "🆕 Nuevo Producto"])
    
    with t1:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            df_i = pd.DataFrame(res.data)
            # Sección de Edición
            st.subheader("🛠️ Editar Producto")
            sel_edit = st.selectbox("Elegir producto para modificar:", ["-- Seleccionar --"] + [f"{r['codigo']} - {r['nombre']}" for r in res.data])
            if sel_edit != "-- Seleccionar --":
                item_e = df_i[df_i['codigo'] == sel_edit.split(" - ")[0]].iloc[0]
                with st.expander("✏️ Panel de Edición", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        e_nom = st.text_input("Nombre", value=item_e['nombre'])
                        e_cat = st.selectbox("Categoría", cats, index=cats.index(item_e['categoria']) if item_e['categoria'] in cats else 0)
                        e_sub = st.selectbox("Subcategoría", subs, index=subs.index(item_e['subcategoria']) if item_e['subcategoria'] in subs else 0)
                        e_col = st.text_input("Colores (separados por coma)", value=item_e['colores'])
                    with c2:
                        # SKU reactivo al editar
                        if e_cat != item_e['categoria'] or e_sub != item_e['subcategoria']:
                            nuevo_sku_e = generar_sku(e_cat, e_sub)
                            st.warning(f"Se asignará nuevo código: {nuevo_sku_e}")
                        else:
                            nuevo_sku_e = item_e['codigo']
                        
                        e_cod = st.text_input("Código SKU", value=nuevo_sku_e)
                        e_inv = st.number_input("Costo Inversión", value=float(item_e['precio_inv']))
                        e_pub = st.number_input("Precio Venta", value=float(item_e['precio_pub']))
                        e_stk = st.number_input("Stock", value=int(item_e['stock']))
                    
                    if st.button("💾 Guardar Cambios"):
                        supabase.table("productos").update({
                            "nombre": e_nom, "codigo": e_cod.upper(), "categoria": e_cat,
                            "subcategoria": e_sub, "colores": e_col, "precio_inv": e_inv,
                            "precio_pub": e_pub, "stock": e_stk
                        }).eq("id", item_e['id']).execute()
                        st.rerun()

            st.divider()
            st.dataframe(df_i, column_config={"foto_path": st.column_config.ImageColumn("Foto")}, use_container_width=True)

    with t2:
        st.subheader("🆕 Registrar Producto")
        with st.form("crear_p"):
            c1, c2 = st.columns(2)
            with c1:
                n_cat = st.selectbox("Categoría", cats)
                n_sub = st.selectbox("Subcategoría", subs)
                # Generación automática
                n_cod = st.text_input("Código SKU Sugerido", value=generar_sku(n_cat, n_sub))
                n_nom = st.text_input("Nombre del Producto")
                n_col = st.text_input("Colores (ej: Rojo, Azul, Negro)")
            with c2:
                n_inv = st.number_input("Costo Inversión", 0.0)
                n_pub = st.number_input("Precio Venta", 0.0)
                n_stk = st.number_input("Stock Inicial", 1)
                n_foto = st.file_uploader("Imagen", type=['jpg','png','jpeg'])
            
            if st.form_submit_button("🚀 REGISTRAR"):
                if n_nom and n_foto:
                    fname = f"{n_cod}_{datetime.now().strftime('%H%M%S')}.jpg"
                    supabase.storage.from_("fotos").upload(fname, n_foto.getvalue())
                    url = supabase.storage.from_("fotos").get_public_url(fname)
                    supabase.table("productos").insert({
                        "codigo": n_cod.upper(), "nombre": n_nom, "categoria": n_cat, "subcategoria": n_sub,
                        "colores": n_col, "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk, "foto_path": url
                    }).execute()
                    st.rerun()

# --- 6. CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
    op = st.radio("Editar:", ["Categorías", "Subcategorías"], horizontal=True)
    db_t = "categoria" if op == "Categorías" else "subcategoria"
    
    n_v = st.text_input(f"Añadir {op}").upper()
    if st.button("➕ Agregar") and n_v:
        supabase.table("configuracion").insert({"tipo": db_t, "valor": n_v}).execute(); st.rerun()
    
    res = supabase.table("configuracion").select("*").eq("tipo", db_t).execute()
    for r in res.data:
        c1, c2 = st.columns([5, 1])
        c1.write(f"• {r['valor']}")
        if c2.button("🗑️", key=r['id']):
            supabase.table("configuracion").delete().eq("id", r['id']).execute(); st.rerun()

# --- 7. REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes de Ventas")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_r = pd.DataFrame(res_v.data)
        c1, c2, c3 = st.columns(3)
        c1.metric("Ingreso Total", f"${df_r['precio_total'].sum():,.2f}")
        c2.metric("Ganancia Total", f"${df_r['ganancia'].sum():,.2f}")
        c3.metric("Ventas Realizadas", len(df_r))
        st.dataframe(df_r, column_config={"foto_path": st.column_config.ImageColumn("Foto")}, use_container_width=True)
    else:
        st.info("Sin ventas registradas.")
