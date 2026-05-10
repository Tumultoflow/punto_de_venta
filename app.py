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
        res = supabase.table("configuracion").select("valor").eq("tipo", tipo).execute()
        return sorted([r['valor'] for r in res.data]) if res.data else ["GENERAL"]
    except: return ["GENERAL"]

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

# --- SECCIÓN: VENTAS (MANTENIDA) ---
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
                try: matriz = json.loads(item['descripcion']) if item['descripcion'] and item['descripcion'].startswith('{') else None
                except: matriz = None

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
                if st.button("➕ Agregar al Carrito"):
                    st.session_state.carrito.append({
                        "temp_id": datetime.now().timestamp(), "id": item['id'], "Producto": item['nombre'], 
                        "Cantidad": v_cant, "Precio": v_pre, "Color": v_col, "Talla": v_tal,
                        "Fecha": datetime.now(ZONA_LOCAL).strftime("%d/%m/%Y %H:%M"),
                        "Vendedor": st.session_state.role.upper(), "es_matriz": bool(matriz),
                        "precio_inv": float(item['precio_inv']), "codigo": item['codigo']
                    })
                    st.rerun()

    if st.session_state.carrito:
        st.divider()
        for i, p in enumerate(st.session_state.carrito):
            col_txt, col_btn = st.columns([5, 1])
            col_txt.write(f"**{p['Cantidad']}x {p['Producto']}** ({p['Color']}-{p['Talla']}) | ${p['Precio']*p['Cantidad']:,.2f}")
            if col_btn.button("❌", key=f"del_{p.get('temp_id', i)}"):
                st.session_state.carrito.pop(i); st.rerun()
        
        c_v1, c_v2 = st.columns(2)
        if c_v1.button("🗑️ CANCELAR TODO"): st.session_state.carrito = []; st.rerun()
        if c_v2.button("🚀 FINALIZAR VENTA", type="primary"):
            for p in st.session_state.carrito:
                prod_db = supabase.table("productos").select("*").eq("id", p['id']).execute().data[0]
                if p['es_matriz']:
                    m_act = json.loads(prod_db['descripcion'])
                    m_act[p['Color']][p['Talla']] -= p['Cantidad']
                    supabase.table("productos").update({"stock": prod_db['stock']-p['Cantidad'], "descripcion": json.dumps(m_act)}).eq("id", p['id']).execute()
                else:
                    supabase.table("productos").update({"stock": prod_db['stock']-p['Cantidad']}).eq("id", p['id']).execute()
                
                meta = json.dumps({"v_col": p['Color'], "v_tal": p['Talla'], "es_matriz": p['es_matriz']})
                supabase.table("ventas").insert({
                    "producto": p['Producto'], "codigo_prod": p['codigo'], "cantidad": p['Cantidad'],
                    "precio_total": p['Precio']*p['Cantidad'], "ganancia": (p['Precio']-p['precio_inv'])*p['Cantidad'],
                    "vendedor": p['Vendedor'], "fecha_venta": datetime.now(ZONA_LOCAL).isoformat(), "color": meta
                }).execute()
            st.session_state.carrito = []; st.success("Venta realizada"); st.rerun()

# --- SECCIÓN: INVENTARIO (CORREGIDA) ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    cats, subs = obtener_config("categoria"), obtener_config("subcategoria")
    t1, t2, t3 = st.tabs(["📋 Lista", "🆕 Registrar Nuevo", "✏️ Editor Maestro"])

    with t1:
        res_i = supabase.table("productos").select("*").order("codigo").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            for _, r in df_i.iterrows():
                c_im, c_tx, c_ac1, c_ac2 = st.columns([1, 4, 0.5, 0.5])
                if r['foto_path']: c_im.image(r['foto_path'], width=80)
                c_tx.write(f"**{r['codigo']}** - {r['nombre']} (Stock: {r['stock']})")
                if c_ac1.button("✏️", key=f"ed_btn_{r['id']}"):
                    st.session_state.edit_id = r['id']
                    try: st.session_state.temp_matriz = json.loads(r['descripcion'])
                    except: st.session_state.temp_matriz = {}
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
            n_pub = st.number_input("Precio Público", 0.0, key="reg_pub")
            n_inv = st.number_input("Precio Proveedor", 0.0, key="reg_inv")
            n_foto = st.file_uploader("Imagen", key="reg_foto")
        with c_n2:
            st.write("**Panel de Variantes**")
            m_col = st.text_input("Color", key="mc_reg")
            m_tal = st.text_input("Talla", key="mt_reg")
            m_can = st.number_input("Stock", 0, key="mq_reg")
            if st.button("Añadir Variante", key="btn_add_reg"):
                if m_col and m_tal:
                    if m_col not in st.session_state.temp_matriz: st.session_state.temp_matriz[m_col] = {}
                    st.session_state.temp_matriz[m_col][m_tal] = m_can
            st.write("Variantes actuales:", st.session_state.temp_matriz)
            if st.button("Limpiar Variantes", key="btn_clr_reg"): st.session_state.temp_matriz = {}
        
        if st.button("🚀 GUARDAR PRODUCTO NUEVO"):
            total_stk = sum(sum(t.values()) for t in st.session_state.temp_matriz.values())
            url = ""
            if n_foto:
                fn = f"{n_sku}_{datetime.now().strftime('%H%M%S')}.jpg"
                supabase.storage.from_("fotos").upload(fn, n_foto.getvalue())
                url = supabase.storage.from_("fotos").get_public_url(fn)
            supabase.table("productos").insert({
                "codigo": n_sku, "nombre": n_nom, "precio_pub": n_pub, "precio_inv": n_inv,
                "stock": total_stk, "descripcion": json.dumps(st.session_state.temp_matriz),
                "foto_path": url, "categoria": n_cat, "subcategoria": n_sub
            }).execute()
            st.session_state.temp_matriz = {}; st.success("Registrado!"); st.rerun()

    with t3:
        if st.session_state.edit_id:
            p = supabase.table("productos").select("*").eq("id", st.session_state.edit_id).execute().data[0]
            st.subheader(f"Editando: {p['codigo']}")
            c_e1, c_e2 = st.columns(2)
            with c_e1:
                e_sku = st.text_input("SKU", value=p['codigo'], key="edit_sku")
                e_nom = st.text_input("Nombre", value=p['nombre'], key="edit_nom")
                e_cat = st.selectbox("Categoría", cats, index=cats.index(p['categoria']) if p['categoria'] in cats else 0, key="edit_cat")
                e_sub = st.selectbox("Subcategoría", subs, index=subs.index(p['subcategoria']) if p['subcategoria'] in subs else 0, key="edit_sub")
                e_pub = st.number_input("P. Público", value=float(p['precio_pub']), key="edit_pub")
                e_inv = st.number_input("P. Proveedor", value=float(p['precio_inv']), key="edit_inv")
            with c_e2:
                if p['foto_path']: st.image(p['foto_path'], width=100)
                e_foto = st.file_uploader("Cambiar Imagen", key="edit_foto")
                st.write("**Editar Variantes**")
                st.write(st.session_state.temp_matriz)
                m_col_e = st.text_input("Color", key="mc_edit")
                m_tal_e = st.text_input("Talla", key="mt_edit")
                m_can_e = st.number_input("Stock", 0, key="mq_edit")
                if st.button("Actualizar/Añadir Variante", key="btn_add_edit"):
                    if m_col_e and m_tal_e:
                        if m_col_e not in st.session_state.temp_matriz: st.session_state.temp_matriz[m_col_e] = {}
                        st.session_state.temp_matriz[m_col_e][m_tal_e] = m_can_e
                if st.button("Resetear Variantes", key="btn_clr_edit"): st.session_state.temp_matriz = {}

            if st.button("💾 GUARDAR TODOS LOS CAMBIOS"):
                total_stk = sum(sum(t.values()) for t in st.session_state.temp_matriz.values())
                upd = {"codigo": e_sku, "nombre": e_nom, "categoria": e_cat, "subcategoria": e_sub, 
                       "precio_pub": e_pub, "precio_inv": e_inv, "stock": total_stk, "descripcion": json.dumps(st.session_state.temp_matriz)}
                if e_foto:
                    fn = f"{e_sku}_{datetime.now().strftime('%H%M%S')}.jpg"
                    supabase.storage.from_("fotos").upload(fn, e_foto.getvalue())
                    upd["foto_path"] = supabase.storage.from_("fotos").get_public_url(fn)
                supabase.table("productos").update(upd).eq("id", st.session_state.edit_id).execute()
                st.session_state.edit_id = None; st.success("Actualizado"); st.rerun()
            if st.button("Cancelar"): st.session_state.edit_id = None; st.rerun()
        else: st.info("Usa el lápiz ✏️ en la lista.")

# --- SECCIONES RESTANTES ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
    tipo_cfg = st.selectbox("Tipo", ["categoria", "subcategoria"], key="cfg_tipo")
    valor_cfg = st.text_input("Nombre", key="cfg_val").upper()
    if st.button("Añadir"): supabase.table("configuracion").insert({"tipo": tipo_cfg, "valor": valor_cfg}).execute(); st.rerun()

elif menu == "Reportes":
    st.header("📊 Reportes")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data: st.dataframe(pd.DataFrame(res_v.data))
