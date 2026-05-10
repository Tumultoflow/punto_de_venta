import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta
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

def generar_sku(cat):
    prefijo = f"{cat[:3]}".upper()
    try:
        res = supabase.table("productos").select("codigo").like("codigo", f"{prefijo}%").execute()
        secuencias = [int(r['codigo'].split('-')[-1]) for r in res.data if '-' in r['codigo']]
        proximo = max(secuencias) + 1 if secuencias else 1
        return f"{prefijo}-{proximo:04d}"
    except: return f"{prefijo}-0001"

def cargar_json_seguro(campo):
    try:
        if campo and str(campo).strip().startswith('{'):
            return json.loads(campo)
        return {"_info_extra": str(campo) if campo else ""}
    except: return {"_info_extra": ""}

# --- 3. SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "role" not in st.session_state: st.session_state.role = None
if "carrito" not in st.session_state: st.session_state.carrito = []
if "edit_id" not in st.session_state: st.session_state.edit_id = None
if "temp_matriz" not in st.session_state: st.session_state.temp_matriz = {}

# --- 4. LOGIN ---
if not st.session_state.auth:
    st.title("⚖️ Acceso TumultoFlow")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if u == "admin" and p == "admin1":
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "equipo1":
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
        else: st.error("Credenciales incorrectas")
    st.stop()

# --- 5. NAVEGACIÓN ---
with st.sidebar:
    st.title(f"⚖️ {st.session_state.role.upper()}")
    opc = ["Ventas", "Inventario"]
    if st.session_state.role == "admin":
        opc += ["Configuración", "Reportes"]
    menu = st.radio("Sección", opc)
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.auth = False
        st.rerun()

# --- SECCIÓN: VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    metodos = [m['valor'] for m in obtener_config("metodo_pago")] or ["EFECTIVO"]
    vendedores = [v['valor'] for v in obtener_config("vendedor")] or ["TIENDA"]
    
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        busq = st.text_input("🔍 Buscar por nombre o código...")
        if busq: df_p = df_p[df_p['nombre'].str.contains(busq, case=False) | df_p['codigo'].str.contains(busq, case=False)]
        
        if not df_p.empty:
            sel_list = [f"{r['codigo']} - {r['nombre']}" for _, r in df_p.iterrows()]
            sel = st.selectbox("Seleccionar Producto", sel_list)
            item = df_p[df_p['codigo'] == sel.split(" - ")[0]].iloc[0]
            
            c1, c2 = st.columns([1, 2])
            with c1:
                if item.get('foto_path'): st.image(item['foto_path'], width=200)
            with c2:
                data_desc = cargar_json_seguro(item['descripcion'])
                texto_desc = data_desc.get("_info_extra", "Sin descripción")
                matriz = {k: v for k, v in data_desc.items() if k != "_info_extra"}

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
                sel_vendedor = st.selectbox("Vendedor", vendedores)
                
                if st.button("➕ Agregar al Carrito"):
                    st.session_state.carrito.append({
                        "temp_id": datetime.now().timestamp(), "id": item['id'], "Producto": item['nombre'], 
                        "Cantidad": v_cant, "Precio": v_pre, "Color": v_col, "Talla": v_tal,
                        "Vendedor": sel_vendedor, "es_matriz": bool(matriz),
                        "precio_inv": float(item['precio_inv']), "codigo": item['codigo']
                    })
                    st.rerun()

    if st.session_state.carrito:
        st.divider()
        sel_metodo = st.selectbox("Método de Pago", metodos)
        for i, p in enumerate(st.session_state.carrito):
            col_txt, col_btn = st.columns([5, 1])
            col_txt.write(f"**{p['Cantidad']}x {p['Producto']}** ({p['Color']}-{p['Talla']}) | Vende: {p['Vendedor']} | ${p['Precio']*p['Cantidad']:,.2f}")
            if col_btn.button("❌", key=f"del_v_{p.get('temp_id', i)}"):
                st.session_state.carrito.pop(i); st.rerun()
        
        if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
            for p in st.session_state.carrito:
                prod_db = supabase.table("productos").select("*").eq("id", p['id']).execute().data[0]
                full_desc = cargar_json_seguro(prod_db['descripcion'])
                if p['es_matriz']:
                    full_desc[p['Color']][p['Talla']] -= p['Cantidad']
                    supabase.table("productos").update({"stock": prod_db['stock']-p['Cantidad'], "descripcion": json.dumps(full_desc)}).eq("id", p['id']).execute()
                else:
                    supabase.table("productos").update({"stock": prod_db['stock']-p['Cantidad']}).eq("id", p['id']).execute()
                
                supabase.table("ventas").insert({
                    "producto": p['Producto'], "codigo_prod": p['codigo'], "cantidad": p['Cantidad'],
                    "precio_total": p['Precio']*p['Cantidad'], "ganancia": (p['Precio']-p['precio_inv'])*p['Cantidad'],
                    "vendedor": p['Vendedor'], "metodo_pago": sel_metodo, "fecha_venta": datetime.now(ZONA_LOCAL).isoformat()
                }).execute()
            st.session_state.carrito = []; st.success("Venta realizada"); st.rerun()

# --- SECCIÓN: INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    cats = [c['valor'] for c in obtener_config("categoria")] or ["GENERAL"]
    
    t1, t2, t3 = st.tabs(["📋 Lista", "🆕 Registrar Nuevo", "✏️ Editor Maestro"])

    with t1:
        res_i = supabase.table("productos").select("*").order("codigo").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            for _, r in df_i.iterrows():
                c_im, c_tx, c_ac1, c_ac2 = st.columns([1, 4, 0.5, 0.5])
                if r['foto_path']: c_im.image(r['foto_path'], width=80)
                d_json = cargar_json_seguro(r['descripcion'])
                c_tx.write(f"**{r['codigo']}** - {r['nombre']} ({r['categoria']})")
                stock_label = f"Stock: {r['stock']}"
                if st.session_state.role == "admin": 
                    stock_label += f" | Costo: ${r['precio_inv']} | Venta: ${r['precio_pub']}"
                c_tx.caption(stock_label)
                
                if c_ac1.button("✏️", key=f"edit_l_{r['id']}"):
                    st.session_state.edit_id = r['id']
                    st.session_state.temp_matriz = d_json
                    st.rerun()
                if st.session_state.role == "admin" and c_ac2.button("🗑️", key=f"del_l_{r['id']}"):
                    supabase.table("productos").delete().eq("id", r['id']).execute(); st.rerun()
                st.divider()

    with t2:
        c_n1, c_n2 = st.columns(2)
        with c_n1:
            n_cat = st.selectbox("Categoría", cats, key="n_cat_reg")
            n_sku = st.text_input("SKU", value=generar_sku(n_cat), key="n_sku_reg")
            n_nom = st.text_input("Nombre Producto", key="n_nom_reg")
            n_desc = st.text_area("Descripción", key="n_desc_reg")
            n_pub = st.number_input("Precio Público", 0.0, key="n_pub_reg")
            n_inv = st.number_input("Precio Proveedor", 0.0, key="n_inv_reg") if st.session_state.role == "admin" else 0.0
        with c_n2:
            st.write("**Variantes**")
            m_col = st.text_input("Color", key="m_col_reg")
            m_tal = st.text_input("Talla", key="m_tal_reg")
            m_can = st.number_input("Stock", 0, key="m_can_reg")
            if st.button("Añadir", key="btn_add_var_reg"):
                if m_col and m_tal:
                    if m_col not in st.session_state.temp_matriz: st.session_state.temp_matriz[m_col] = {}
                    st.session_state.temp_matriz[m_col][m_tal] = m_can
            st.write("Estructura:", {k: v for k, v in st.session_state.temp_matriz.items() if k != "_info_extra"})
        
        if st.button("🚀 GUARDAR NUEVO PRODUCTO", key="btn_save_new"):
            st.session_state.temp_matriz["_info_extra"] = n_desc
            total = sum(sum(v.values()) for k, v in st.session_state.temp_matriz.items() if k != "_info_extra")
            supabase.table("productos").insert({"codigo": n_sku, "nombre": n_nom, "precio_pub": n_pub, "precio_inv": n_inv, "stock": total, "descripcion": json.dumps(st.session_state.temp_matriz), "categoria": n_cat}).execute()
            st.session_state.temp_matriz = {}; st.rerun()

    with t3:
        if st.session_state.edit_id:
            p = supabase.table("productos").select("*").eq("id", st.session_state.edit_id).execute().data[0]
            st.subheader(f"Editando: {p['codigo']}")
            ce1, ce2 = st.columns(2)
            with ce1:
                e_nom = st.text_input("Nombre", value=p['nombre'], key="e_nom")
                e_cat = st.selectbox("Categoría", cats, index=cats.index(p['categoria']) if p['categoria'] in cats else 0, key="e_cat")
                e_pub = st.number_input("P. Público", value=float(p['precio_pub']), key="e_pub")
                e_inv = st.number_input("P. Inversión", value=float(p['precio_inv']), key="e_inv") if st.session_state.role == "admin" else float(p['precio_inv'])
                e_desc = st.text_area("Descripción", value=st.session_state.temp_matriz.get("_info_extra", ""), key="e_desc")
            with ce2:
                st.write("**Actualizar Variantes**")
                nx_c = st.text_input("Color", key="ex_c")
                nx_t = st.text_input("Talla", key="ex_t")
                nx_q = st.number_input("Cant.", 0, key="ex_q")
                if st.button("Actualizar", key="btn_ex"):
                    if nx_c and nx_t:
                        if nx_c not in st.session_state.temp_matriz: st.session_state.temp_matriz[nx_c] = {}
                        st.session_state.temp_matriz[nx_c][nx_t] = nx_q
                st.divider()
                for c_n, tallas in list(st.session_state.temp_matriz.items()):
                    if c_n != "_info_extra":
                        for t_n, q_v in list(tallas.items()):
                            r1, r2, r3 = st.columns([2, 1, 1])
                            r1.write(f"{c_n} - {t_n}")
                            r2.write(f"Stock: {q_v}")
                            if r3.button("🗑️", key=f"del_v_{c_n}_{t_n}"):
                                del st.session_state.temp_matriz[c_n][t_n]
                                if not st.session_state.temp_matriz[c_n]: del st.session_state.temp_matriz[c_n]
                                st.rerun()

            if st.button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True, key="btn_m_save"):
                st.session_state.temp_matriz["_info_extra"] = e_desc
                total_stk = sum(sum(v.values()) for k, v in st.session_state.temp_matriz.items() if k != "_info_extra")
                supabase.table("productos").update({"nombre": e_nom, "categoria": e_cat, "precio_pub": e_pub, "precio_inv": e_inv, "stock": total_stk, "descripcion": json.dumps(st.session_state.temp_matriz)}).eq("id", st.session_state.edit_id).execute()
                st.session_state.edit_id = None; st.rerun()
        else: st.info("Selecciona un producto de la lista.")

# --- SECCIÓN: CONFIGURACIÓN ---
elif menu == "Configuración" and st.session_state.role == "admin":
    st.header("⚙️ Configuración")
    tipo = st.selectbox("Dato a configurar", ["categoria", "vendedor", "metodo_pago"], key="cfg_sel")
    valor = st.text_input("Nuevo valor", key="cfg_val").upper()
    if st.button("Añadir", key="cfg_add"):
        supabase.table("configuracion").insert({"tipo": tipo, "valor": valor}).execute(); st.rerun()
    
    st.subheader("Registros actuales")
    for item in obtener_config(tipo):
        cl1, cl2 = st.columns([4, 1])
        cl1.write(item['valor'])
        if cl2.button("🗑️", key=f"dcfg_{item['id']}"):
            supabase.table("configuracion").delete().eq("id", item['id']).execute(); st.rerun()

# --- SECCIÓN: REPORTES ---
elif menu == "Reportes" and st.session_state.role == "admin":
    st.header("📊 Reportes")
    c_f1, c_f2 = st.columns(2)
    f_ini = c_f1.date_input("Inicio", datetime.now() - timedelta(days=30), key="r_ini")
    f_fin = c_f2.date_input("Fin", datetime.now(), key="r_fin")
    res_v = supabase.table("ventas").select("*").gte("fecha_venta", f_ini.isoformat()).lte("fecha_venta", (f_fin + timedelta(days=1)).isoformat()).execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        df_v['fecha_venta'] = pd.to_datetime(df_v['fecha_venta']).dt.tz_localize(None).dt.tz_localize('UTC').dt.tz_convert('America/Mexico_City')
        m1, m2, m3 = st.columns(3)
        m1.metric("Ventas", f"${df_v['precio_total'].sum():,.2f}")
        m2.metric("Ganancia", f"${df_v['ganancia'].sum():,.2f}")
        m3.metric("Tickets", len(df_v))
        st.line_chart(df_v.groupby(df_v['fecha_venta'].dt.date)['precio_total'].sum())
        st.dataframe(df_v, use_container_width=True)
