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
    if not cat or not sub:
        return "GEN-GEN-0001"
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

# --- 3. MANEJO DE SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "role" not in st.session_state: st.session_state.role = None
if "carrito" not in st.session_state: st.session_state.carrito = []

# --- 4. LOGIN CON ROLES ---
if not st.session_state.auth:
    st.title("⚖️ Sistema TumultoFlow - Acceso")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if u == "admin" and p == "admin1": 
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "equipo1":
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.stop()

# --- 5. INTERFAZ PRINCIPAL ---
with st.sidebar:
    st.title("⚖️ TUMULTOFLOW")
    st.write(f"👤 Rol: **{st.session_state.role.upper()}**")
    
    opciones_menu = ["Ventas", "Inventario"]
    if st.session_state.role == "admin":
        opciones_menu += ["Configuración", "Reportes"]
    
    menu = st.radio("Navegación", opciones_menu)
    
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.auth = False
        st.session_state.role = None
        st.rerun()

# --- SECCIÓN: VENTAS ---
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
            st.info(f"**Disponibles:** {item['stock']}")
        with c2:
            st.subheader(item['nombre'])
            st.caption(f"📝 {item.get('descripcion', 'Sin descripción')}")
            colores = [c.strip().upper() for c in item['colores'].split(',') if c.strip()] if item.get('colores') else ["ÚNICO"]
            v_col = st.selectbox("🎨 Color", colores)
            v_cant = st.number_input("Cantidad", 1, int(item['stock']))
            v_pre = st.number_input("Precio de Venta", value=float(item['precio_pub']))
            if st.button("➕ Añadir al Carrito", use_container_width=True):
                st.session_state.carrito.append({
                    "id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'],
                    "color": v_col, "cantidad": v_cant, "precio": v_pre, 
                    "precio_inv": item['precio_inv'], "foto": item.get('foto_path')
                })
                st.toast("Producto añadido")

        if st.session_state.carrito:
            st.divider()
            total_v = sum(p['precio'] * p['cantidad'] for p in st.session_state.carrito)
            st.subheader(f"Total a Pagar: ${total_v:,.2f}")
            v_vend = st.text_input("Vendedor", value="Equipo" if st.session_state.role == "equipo" else "")
            
            if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True) and v_vend:
                for p in st.session_state.carrito:
                    stk_db = supabase.table("productos").select("stock").eq("id", p['id']).execute().data[0]['stock']
                    supabase.table("productos").update({"stock": stk_db - p['cantidad']}).eq("id", p['id']).execute()
                    supabase.table("ventas").insert({
                        "producto": p['nombre'], "codigo_prod": p['codigo'], "color": p['color'],
                        "cantidad": p['cantidad'], "precio_total": p['precio']*p['cantidad'],
                        "vendedor": v_vend, "ganancia": (p['precio'] - p['precio_inv']) * p['cantidad'],
                        "foto_path": p['foto']
                    }).execute()
                st.session_state.carrito = []
                st.success("¡Venta completada!")
                st.rerun()

# --- SECCIÓN: INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    cats, subs = obtener_config("categoria"), obtener_config("subcategoria")
    
    tabs_inv = ["📋 Catálogo"]
    if st.session_state.role == "admin":
        tabs_inv.append("🆕 Nuevo Producto")
    
    tabs = st.tabs(tabs_inv)
    
    with tabs[0]:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            df_i = pd.DataFrame(res.data)
            
            columnas_visibles = df_i.columns.tolist()
            if st.session_state.role == "equipo" and "precio_inv" in columnas_visibles:
                columnas_visibles.remove("precio_inv")
            
            sel_edit = st.selectbox("Selecciona para ver/modificar:", ["-- Seleccionar --"] + [f"{r['codigo']} - {r['nombre']}" for r in res.data])
            
            if sel_edit != "-- Seleccionar --":
                it_e = df_i[df_i['codigo'] == sel_edit.split(" - ")[0]].iloc[0]
                with st.expander("✏️ Detalle del Producto", expanded=True):
                    c_img1, c_img2 = st.columns([1, 2])
                    with c_img1:
                        if it_e.get('foto_path'): st.image(it_e['foto_path'], width=150)
                    with c_img2:
                        nueva_foto = st.file_uploader("🖼️ Cambiar Imagen", type=['jpg','png','jpeg']) if st.session_state.role == "admin" else None
                    
                    e_desc = st.text_area("Descripción", value=it_e.get('descripcion', ''), disabled=(st.session_state.role != "admin"))
                    c1, c2 = st.columns(2)
                    with c1:
                        e_nom = st.text_input("Nombre", value=it_e['nombre'], disabled=(st.session_state.role != "admin"))
                        e_cat = st.selectbox("Categoría", cats, index=cats.index(it_e['categoria']) if it_e['categoria'] in cats else 0, disabled=(st.session_state.role != "admin"))
                        # CORRECCIÓN 1: Se agregó el campo subcategoría en la edición
                        sub_actual = it_e.get('subcategoria', '')
                        e_sub = st.selectbox("Subcategoría", subs, index=subs.index(sub_actual) if sub_actual in subs else 0, disabled=(st.session_state.role != "admin"))
                        e_col = st.text_input("Colores", value=it_e['colores'], disabled=(st.session_state.role != "admin"))
                    with c2:
                        # CORRECCIÓN 2: Si cambian la categoría o subcategoría, sugiere el nuevo código, pero permite editarlo (disabled=False para admin)
                        sku_sugerido = generar_sku(e_cat, e_sub) if (e_cat != it_e['categoria'] or e_sub != sub_actual) else it_e['codigo']
                        e_cod = st.text_input("Código SKU", value=sku_sugerido, disabled=(st.session_state.role != "admin"))
                        
                        if st.session_state.role == "admin":
                            e_inv = st.number_input("Costo (Inversión)", value=float(it_e['precio_inv']))
                        else:
                            e_inv = it_e['precio_inv']
                        
                        e_pub = st.number_input("Precio Venta", value=float(it_e['precio_pub']), disabled=(st.session_state.role != "admin"))
                        e_stk = st.number_input("Stock Actual", value=int(it_e['stock']))
                    
                    if st.session_state.role == "admin":
                        b_col1, b_col2 = st.columns(2)
                        if b_col1.button("💾 Guardar Cambios", use_container_width=True):
                            url_f = it_e['foto_path']
                            if nueva_foto:
                                fn = f"{e_cod}_{datetime.now().strftime('%H%M%S')}.jpg"
                                supabase.storage.from_("fotos").upload(fn, nueva_foto.getvalue())
                                url_f = supabase.storage.from_("fotos").get_public_url(fn)
                            
                            supabase.table("productos").update({
                                "nombre": e_nom, "codigo": e_cod.upper(), "categoria": e_cat, "subcategoria": e_sub,
                                "colores": e_col, "precio_inv": e_inv, "precio_pub": e_pub, "stock": e_stk, 
                                "descripcion": e_desc, "foto_path": url_f
                            }).eq("id", it_e['id']).execute()
                            st.rerun()
                        
                        if b_col2.button("🗑️ ELIMINAR", type="primary", use_container_width=True):
                            supabase.table("productos").delete().eq("id", it_e['id']).execute()
                            st.rerun()
                    else:
                        if st.button("💾 Actualizar Stock (Solo)"):
                            supabase.table("productos").update({"stock": e_stk}).eq("id", it_e['id']).execute()
                            st.success("Stock actualizado")

            st.divider()
            st.dataframe(df_i[columnas_visibles], column_config={"foto_path": st.column_config.ImageColumn("Foto")}, use_container_width=True)

    if st.session_state.role == "admin":
        with tabs[1]:
            # CORRECCIÓN 3: Al usar la asignación fuera del st.form, el SKU cambia de forma dinámica e instantánea
            st.write("### Registrar Nuevo Artículo")
            n_nom = st.text_input("Nombre")
            n_desc = st.text_area("Descripción")
            
            c1, c2 = st.columns(2)
            with c1:
                n_cat = st.selectbox("Categoría", cats, key="new_cat")
                n_sub = st.selectbox("Subcategoría", subs, key="new_sub")
                # El valor cambia dinámicamente según lo seleccionado arriba
                sku_dinamico = generar_sku(n_cat, n_sub)
                n_cod = st.text_input("SKU Generado automáticamente", value=sku_dinamico)
                n_col = st.text_input("Colores")
            with c2:
                n_inv = st.number_input("Costo", 0.0)
                n_pub = st.number_input("Venta", 0.0)
                n_stk = st.number_input("Stock Inicial", 1)
                n_foto = st.file_uploader("Subir Imagen", type=['jpg','png','jpeg'])
            
            if st.button("🚀 REGISTRAR", use_container_width=True):
                if n_nom and n_foto:
                    fname = f"{n_cod}_{datetime.now().strftime('%H%M%S')}.jpg"
                    supabase.storage.from_("fotos").upload(fname, n_foto.getvalue())
                    url = supabase.storage.from_("fotos").get_public_url(fname)
                    supabase.table("productos").insert({
                        "codigo": n_cod.upper(), "nombre": n_nom, "descripcion": n_desc, "categoria": n_cat, 
                        "subcategoria": n_sub, "colores": n_col, "precio_inv": n_inv, "precio_pub": n_pub, 
                        "stock": n_stk, "foto_path": url
                    }).execute()
                    st.success("¡Producto creado con éxito!")
                    st.rerun()

# --- SECCIÓN: CONFIGURACIÓN ---
elif menu == "Configuración" and st.session_state.role == "admin":
    st.header("⚙️ Configuración")
    tipo = st.radio("Gestionar:", ["Categorías", "Subcategorías"], horizontal=True)
    db_col = "categoria" if tipo == "Categorías" else "subcategoria"
    val = st.text_input(f"Nuevo {tipo}").upper()
    if st.button("➕ Agregar") and val:
        supabase.table("configuracion").insert({"tipo": db_col, "valor": val}).execute(); st.rerun()
    res = supabase.table("configuracion").select("*").eq("tipo", db_col).execute()
    for r in res.data:
        v, b = st.columns([5, 1])
        v.write(f"• {r['valor']}")
        if b.button("🗑️", key=r['id']):
            supabase.table("configuracion").delete().eq("id", r['id']).execute(); st.rerun()

# --- SECCIÓN: REPORTES ---
elif menu == "Reportes" and st.session_state.role == "admin":
    st.header("📊 Reportes de Desempeño")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    
    if res_v.data:
        df = pd.DataFrame(res_v.data)
        df['fecha_venta'] = pd.to_datetime(df['fecha_venta'], errors='coerce')
        df = df.dropna(subset=['fecha_venta'])
        df['Semana'] = df['fecha_venta'].dt.strftime('%Y - Semana %W')
        
        semanas_unicas = df['Semana'].dropna().unique().astype(str).tolist()
        lista_semanas = ["Todo el Historial"] + sorted(semanas_unicas, reverse=True)
        semana_sel = st.selectbox("📅 Seleccionar Semana:", lista_semanas)
        
        df_f = df if semana_sel == "Todo el Historial" else df[df['Semana'] == semana_sel]

        col1, col2, col3 = st.columns(3)
        df_f['precio_total'] = pd.to_numeric(df_f['precio_total'], errors='coerce').fillna(0)
        df_f['ganancia'] = pd.to_numeric(df_f['ganancia'], errors='coerce').fillna(0)
        
        col1.metric("Ventas Cobradas", f"${df_f['precio_total'].sum():,.2f}")
        col2.metric("Ganancia Neta", f"${df_f['ganancia'].sum():,.2f}")
        col3.metric("Productos Salientes", f"{int(df_f['cantidad'].sum())} pzs")

        st.divider()
        st.dataframe(df_f, column_config={"foto_path": st.column_config.ImageColumn("Mini")}, use_container_width=True)
    else:
        st.warning("No hay ventas aún.")
