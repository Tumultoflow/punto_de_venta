import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import pytz
import json

# --- 1. CONFIGURACIÓN ---
ZONA_LOCAL = pytz.timezone('America/Mexico_City')
SUPABASE_URL = "https://gfileauwnaarqvsndlby.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdmaWxlYXV3bmFhcnF2c25kbGJ5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MDk2MTAsImV4cCI6MjA5MjQ4NTYxMH0.vVeNljQC_yyfmP1MEnSyRdtqq59yZg1sm8SgrroQBcs"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="TUMULTOFLOW", layout="wide", page_icon="⚖️")

# --- 2. FUNCIONES ---
def obtener_config(tipo):
    try:
        res = supabase.table("configuracion").select("id, valor").eq("tipo", tipo).execute()
        return res.data if res.data else []
    except: return []

def generar_sku(cat, sub):
    prefijo = f"{cat[:3]}-{sub[:3]}".upper()
    try:
        res = supabase.table("productos").select("codigo").like("codigo", f"{prefijo}%").execute()
        secuencias = [int(r['codigo'].split('-')[-1]) for r in res.data if '-' in r['codigo']]
        proximo = max(secuencias) + 1 if secuencias else 1
        return f"{prefijo}-{proximo:04d}"
    except: return f"{prefijo}-0001"

# --- 3. SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []
if "edit_id" not in st.session_state: st.session_state.edit_id = None
if "temp_matriz" not in st.session_state: st.session_state.temp_matriz = {}

# --- 4. LOGIN ---
if not st.session_state.auth:
    st.title("⚖️ Acceso TumultoFlow")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if (u == "admin" and p == "admin1") or (u == "equipo" and p == "equipo1"):
            st.session_state.auth, st.session_state.role = True, u
            st.rerun()
    st.stop()

# --- 5. NAVEGACIÓN ---
with st.sidebar:
    st.title("⚖️ MENU")
    opc = ["Ventas", "Inventario"]
    if st.session_state.role == "admin": opc += ["Configuración", "Reportes"]
    menu = st.radio("Sección", opc)
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.auth = False
        st.rerun()

# --- SECCIÓN: VENTAS (INTACTA) ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        busq = st.text_input("🔍 Buscar...")
        if busq: df_p = df_p[df_p['nombre'].str.contains(busq, case=False) | df_p['codigo'].str.contains(busq, case=False)]
        
        if not df_p.empty:
            sel_list = [f"{r['codigo']} - {r['nombre']}" for _, r in df_p.iterrows()]
            sel = st.selectbox("Seleccionar Producto", sel_list)
            item = df_p[df_p['codigo'] == sel.split(" - ")[0]].iloc[0]
            
            c1, c2 = st.columns([1, 2])
            with c1:
                if item.get('foto_path'): st.image(item['foto_path'], width=200)
            with c2:
                try: 
                    data_desc = json.loads(item['descripcion'])
                    texto_desc = data_desc.get("_info_extra", "Sin descripción")
                    matriz = {k: v for k, v in data_desc.items() if k != "_info_extra"}
                except: 
                    texto_desc = "Sin descripción"
                    matriz = None

                st.info(f"**Descripción:** {texto_desc}")

                if matriz:
                    v_col = st.selectbox("Color", list(matriz.keys()))
                    v_tal = st.selectbox("Talla", list(matriz[v_col].keys()))
                    stock_v = matriz[v_col][v_tal]
                    st.metric("Disponible", stock_v)
                    v_cant = st.number_input("Cantidad", 1, max(1, int(stock_v)))
                else:
                    v_col, v_tal = "N/A", "N/A"
                    v_cant = st.number_input("Cantidad", 1, int(item['stock']))

                v_pre = st.number_input("Precio", value=float(item['precio_pub']))
                
                # --- NUEVO: MÉTODO DE PAGO ---
                metodos = [m['valor'] for m in obtener_config("metodo_pago")]
                v_pago = st.selectbox("Método de Pago", metodos if metodos else ["EFECTIVO"])

                if st.button("➕ Agregar al Carrito"):
                    st.session_state.carrito.append({
                        "temp_id": datetime.now().timestamp(), "id": item['id'], "Producto": item['nombre'], 
                        "Cantidad": v_cant, "Precio": v_pre, "Color": v_col, "Talla": v_tal,
                        "Fecha": datetime.now(ZONA_LOCAL).strftime("%d/%m/%Y %H:%M"),
                        "Vendedor": st.session_state.role.upper(), "es_matriz": bool(matriz),
                        "precio_inv": float(item['precio_inv']), "codigo": item['codigo'],
                        "metodo_pago": v_pago
                    })
                    st.rerun()

    if st.session_state.carrito:
        st.divider()
        for i, p in enumerate(st.session_state.carrito):
            col_txt, col_btn = st.columns([5, 1])
            col_txt.write(f"**{p['Cantidad']}x {p['Producto']}** ({p['Color']}-{p['Talla']}) | ${p['Precio']*p['Cantidad']:,.2f} [{p['metodo_pago']}]")
            if col_btn.button("❌", key=f"del_{p.get('temp_id', i)}"):
                st.session_state.carrito.pop(i); st.rerun()
        
        c_v1, c_v2 = st.columns(2)
        if c_v1.button("🗑️ CANCELAR TODO"): st.session_state.carrito = []; st.rerun()
        if c_v2.button("🚀 FINALIZAR VENTA", type="primary"):
            for p in st.session_state.carrito:
                prod_db = supabase.table("productos").select("*").eq("id", p['id']).execute().data[0]
                full_desc = json.loads(prod_db['descripcion'])
                if p['es_matriz']:
                    full_desc[p['Color']][p['Talla']] -= p['Cantidad']
                    supabase.table("productos").update({"stock": prod_db['stock']-p['Cantidad'], "descripcion": json.dumps(full_desc)}).eq("id", p['id']).execute()
                else:
                    supabase.table("productos").update({"stock": prod_db['stock']-p['Cantidad']}).eq("id", p['id']).execute()
                
                meta = json.dumps({"v_col": p['Color'], "v_tal": p['Talla'], "es_matriz": p['es_matriz'], "pago": p['metodo_pago']})
                supabase.table("ventas").insert({
                    "producto": p['Producto'], "codigo_prod": p['codigo'], "cantidad": p['Cantidad'],
                    "precio_total": p['Precio']*p['Cantidad'], "ganancia": (p['Precio']-p['precio_inv'])*p['Cantidad'],
                    "vendedor": p['Vendedor'], "fecha_venta": datetime.now(ZONA_LOCAL).isoformat(), "color": meta
                }).execute()
            st.session_state.carrito = []; st.success("Venta realizada"); st.rerun()

# --- SECCIÓN: INVENTARIO (INTACTA) ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    cats_data = obtener_config("categoria")
    subs_data = obtener_config("subcategoria")
    cats = [c['valor'] for c in cats_data] if cats_data else ["GENERAL"]
    subs = [s['valor'] for s in subs_data] if subs_data else ["GENERAL"]
    
    t1, t2, t3 = st.tabs(["📋 Lista", "🆕 Registrar Nuevo", "✏️ Editor Maestro"])

    with t1:
        res_i = supabase.table("productos").select("*").order("codigo").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            for _, r in df_i.iterrows():
                c_im, c_tx, c_ac1, c_ac2 = st.columns([1, 4, 0.5, 0.5])
                if r['foto_path']: c_im.image(r['foto_path'], width=80)
                try: d_json = json.loads(r['descripcion'])
                except: d_json = {}
                desc_lista = d_json.get("_info_extra", "Sin descripción")
                c_tx.write(f"**{r['codigo']}** - {r['nombre']}")
                c_tx.write(f"_{desc_lista}_")
                if c_ac1.button("✏️", key=f"ed_btn_{r['id']}"):
                    st.session_state.edit_id = r['id']
                    st.session_state.temp_matriz = d_json
                    st.rerun()
                if c_ac2.button("🗑️", key=f"del_btn_{r['id']}"):
                    supabase.table("productos").delete().eq("id", r['id']).execute(); st.rerun()
                st.divider()

    with t2:
        c_n1, c_n2 = st.columns(2)
        with c_n1:
            n_cat = st.selectbox("Categoría", cats, key="reg_cat")
            n_sub = st.selectbox("Subcategoría", subs, key="reg_sub")
            n_sku = st.text_input("SKU", value=generar_sku(n_cat, n_sub), key="reg_sku")
            n_nom = st.text_input("Nombre Producto", key="reg_nom")
            n_desc = st.text_area("Descripción", key="reg_desc")
            n_pub = st.number_input("Precio Público", 0.0, key="reg_pub")
            n_inv = st.number_input("Precio Proveedor", 0.0, key="reg_inv")
            n_foto = st.file_uploader("Imagen", key="reg_foto")
        with c_n2:
            st.write("**Variantes**")
            m_col = st.text_input("Color", key="mc_reg")
            m_tal = st.text_input("Talla", key="mt_reg")
            m_can = st.number_input("Stock", 0, key="mq_reg")
            if st.button("Añadir Variante"):
                if m_col and m_tal:
                    if m_col not in st.session_state.temp_matriz: st.session_state.temp_matriz[m_col] = {}
                    st.session_state.temp_matriz[m_col][m_tal] = m_can
            st.write(st.session_state.temp_matriz)
        if st.button("🚀 GUARDAR"):
            st.session_state.temp_matriz["_info_extra"] = n_desc
            total_stk = sum(sum(v.values()) for k, v in st.session_state.temp_matriz.items() if k != "_info_extra")
            url = ""
            if n_foto:
                fn = f"{n_sku}_{datetime.now().strftime('%H%M%S')}.jpg"
                supabase.storage.from_("fotos").upload(fn, n_foto.getvalue())
                url = supabase.storage.from_("fotos").get_public_url(fn)
            supabase.table("productos").insert({"codigo": n_sku, "nombre": n_nom, "precio_pub": n_pub, "precio_inv": n_inv, "stock": total_stk, "descripcion": json.dumps(st.session_state.temp_matriz), "foto_path": url, "categoria": n_cat, "subcategoria": n_sub}).execute()
            st.session_state.temp_matriz = {}; st.success("Registrado"); st.rerun()

    with t3:
        if st.session_state.edit_id:
            p = supabase.table("productos").select("*").eq("id", st.session_state.edit_id).execute().data[0]
            e_nom = st.text_input("Nombre", value=p['nombre'], key="edit_nom")
            e_desc = st.text_area("Descripción", value=json.loads(p['descripcion']).get("_info_extra", ""), key="edit_desc")
            if st.button("💾 ACTUALIZAR"):
                new_m = st.session_state.temp_matriz
                new_m["_info_extra"] = e_desc
                supabase.table("productos").update({"nombre": e_nom, "descripcion": json.dumps(new_m)}).eq("id", st.session_state.edit_id).execute()
                st.session_state.edit_id = None; st.rerun()
            if st.button("Cancelar"): st.session_state.edit_id = None; st.rerun()

# --- SECCIÓN: CONFIGURACIÓN (REDISEÑADA) ---
elif menu == "Configuración":
    st.header("⚙️ Centro de Configuración")
    
    # 1. AGREGAR NUEVOS VALORES
    with st.expander("➕ Añadir Nueva Configuración", expanded=True):
        c_a1, c_a2 = st.columns([1, 2])
        tipo_cfg = c_a1.selectbox("¿Qué deseas añadir?", ["categoria", "subcategoria", "vendedor", "metodo_pago"])
        valor_cfg = c_a2.text_input("Nombre del valor (Ej: CALZADO, JUAN PEREZ, TARJETA)").upper()
        if st.button("💾 Guardar Configuración", use_container_width=True):
            if valor_cfg:
                supabase.table("configuracion").insert({"tipo": tipo_cfg, "valor": valor_cfg}).execute()
                st.success(f"'{valor_cfg}' añadido correctamente.")
                st.rerun()

    st.divider()
    
    # 2. LISTADO Y ELIMINACIÓN
    st.subheader("📋 Configuración Actual")
    col_cat, col_sub, col_ven, col_pag = st.columns(4)

    with col_cat:
        st.write("**Categorías**")
        for item in obtener_config("categoria"):
            c1, c2 = st.columns([3, 1])
            c1.caption(item['valor'])
            if c2.button("🗑️", key=f"del_c_{item['id']}"):
                supabase.table("configuracion").delete().eq("id", item['id']).execute(); st.rerun()

    with col_sub:
        st.write("**Subcategorías**")
        for item in obtener_config("subcategoria"):
            c1, c2 = st.columns([3, 1])
            c1.caption(item['valor'])
            if c2.button("🗑️", key=f"del_s_{item['id']}"):
                supabase.table("configuracion").delete().eq("id", item['id']).execute(); st.rerun()

    with col_ven:
        st.write("**Vendedores**")
        for item in obtener_config("vendedor"):
            c1, c2 = st.columns([3, 1])
            c1.caption(item['valor'])
            if c2.button("🗑️", key=f"del_v_{item['id']}"):
                supabase.table("configuracion").delete().eq("id", item['id']).execute(); st.rerun()

    with col_pag:
        st.write("**Métodos de Pago**")
        for item in obtener_config("metodo_pago"):
            c1, c2 = st.columns([3, 1])
            c1.caption(item['valor'])
            if c2.button("🗑️", key=f"del_p_{item['id']}"):
                supabase.table("configuracion").delete().eq("id", item['id']).execute(); st.rerun()

# --- SECCIÓN: REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        st.dataframe(df_v)
