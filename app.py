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

def generar_sku(cat, sub):
    prefijo = f"{cat[:3]}-{sub[:3]}".upper()
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
if "temp_img_url" not in st.session_state: st.session_state.temp_img_url = ""

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
        st.session_state.role = None
        st.rerun()

# --- SECCIÓN: VENTAS (SIN CAMBIOS) ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    metodos = [m['valor'] for m in obtener_config("metodo_pago")] or ["EFECTIVO"]
    vendedores = [v['valor'] for v in obtener_config("vendedor")] or ["TIENDA"]
    
    res = supabase.table("productos").select("*").gt("stock", 0).execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        busq_v = st.text_input("🔍 Buscar para vender...", key="busq_v")
        if busq_v: df_p = df_p[df_p['nombre'].str.contains(busq_v, case=False) | df_p['codigo'].str.contains(busq_v, case=False)]
        
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
            col_txt.write(f"**{p['Cantidad']}x {p['Producto']}** ({p['Color']}-{p['Talla']}) | ${p['Precio']*p['Cantidad']:,.2f}")
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

# --- SECCIÓN: INVENTARIO (CORREGIDA) ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    cats = [c['valor'] for c in obtener_config("categoria")] or ["GENERAL"]
    subs = [s['valor'] for s in obtener_config("subcategoria")] or ["GENERAL"]
    
    t1, t2, t3 = st.tabs(["📋 Lista", "🆕 Registrar Nuevo", "✏️ Editor Maestro"])

    with t1:
        busq_i = st.text_input("🔍 Buscar en inventario...", key="busq_inv")
        res_i = supabase.table("productos").select("*").order("codigo").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            if busq_i:
                df_i = df_i[df_i['nombre'].str.contains(busq_i, case=False) | df_i['codigo'].str.contains(busq_i, case=False)]
            
            for _, r in df_i.iterrows():
                c_im, c_tx, c_ac1, c_ac2 = st.columns([1, 4, 0.5, 0.5])
                if r['foto_path']: c_im.image(r['foto_path'], width=80)
                d_json = cargar_json_seguro(r['descripcion'])
                c_tx.write(f"**{r['codigo']}** - {r['nombre']}")
                c_tx.caption(f"Cat: {r['categoria']} | Sub: {r.get('subcategoria', 'N/A')}")
                if st.session_state.role == "admin": 
                    c_tx.caption(f"Stock: {r['stock']} | Costo: ${r['precio_inv']} | Venta: ${r['precio_pub']}")
                
                if c_ac1.button("✏️", key=f"ed_l_{r['id']}"):
                    st.session_state.edit_id = r['id']
                    st.session_state.temp_matriz = d_json
                    # Forzamos la actualización de la URL en la sesión
                    st.session_state.temp_img_url = r['foto_path'] if r['foto_path'] else ""
                    st.rerun()
                if st.session_state.role == "admin" and c_ac2.button("🗑️", key=f"del_l_{r['id']}"):
                    supabase.table("productos").delete().eq("id", r['id']).execute(); st.rerun()
                st.divider()

    with t2:
        c_n1, c_n2 = st.columns(2)
        with c_n1:
            n_cat = st.selectbox("Categoría", cats, key="n_cat")
            n_sub = st.selectbox("Subcategoría", subs, key="n_sub")
            n_sku = st.text_input("SKU", value=generar_sku(n_cat, n_sub), key="n_sku")
            n_nom = st.text_input("Nombre", key="n_nom")
            n_desc = st.text_area("Descripción", key="n_desc")
            n_pub = st.number_input("P. Público", 0.0, key="n_pub")
            n_inv = st.number_input("P. Proveedor", 0.0, key="n_inv") if st.session_state.role == "admin" else 0.0
            n_img = st.text_input("URL de Imagen (opcional)", key="n_img")
        with c_n2:
            st.write("**Variantes**")
            m_col = st.text_input("Color", key="m_c")
            m_tal = st.text_input("Talla", key="m_t")
            m_can = st.number_input("Stock", 0, key="m_q")
            if st.button("Añadir Variante", key="btn_add_v"):
                if m_col and m_tal:
                    if m_col not in st.session_state.temp_matriz: st.session_state.temp_matriz[m_col] = {}
                    st.session_state.temp_matriz[m_col][m_tal] = m_can
            st.write("Estructura actual:", {k: v for k, v in st.session_state.temp_matriz.items() if k != "_info_extra"})
        
        if st.button("🚀 GUARDAR NUEVO PRODUCTO"):
            st.session_state.temp_matriz["_info_extra"] = n_desc
            total = sum(sum(v.values()) for k, v in st.session_state.temp_matriz.items() if k != "_info_extra")
            supabase.table("productos").insert({
                "codigo": n_sku, "nombre": n_nom, "precio_pub": n_pub, "precio_inv": n_inv, 
                "stock": total, "descripcion": json.dumps(st.session_state.temp_matriz), 
                "categoria": n_cat, "subcategoria": n_sub, "foto_path": n_img
            }).execute()
            st.session_state.temp_matriz = {}; st.rerun()

    with t3:
        if st.session_state.edit_id:
            p = supabase.table("productos").select("*").eq("id", st.session_state.edit_id).execute().data[0]
            st.subheader(f"Editor Maestro: {p['codigo']}")
            
            # --- FUNCIÓN DE ACTUALIZACIÓN DE SESIÓN PARA LA IMAGEN ---
            def update_img_url():
                st.session_state.temp_img_url = st.session_state.e_img_url_input

            c_e1, c_e2 = st.columns(2)
            with c_e1:
                e_nom = st.text_input("Nombre", value=p['nombre'], key="e_nom")
                e_cat = st.selectbox("Categoría", cats, index=cats.index(p['categoria']) if p['categoria'] in cats else 0, key="e_cat")
                e_sub = st.selectbox("Subcategoría", subs, index=subs.index(p.get('subcategoria')) if p.get('subcategoria') in subs else 0, key="e_sub")
                e_pub = st.number_input("P. Público", value=float(p['precio_pub']), key="e_pub")
                e_inv = st.number_input("P. Inversión", value=float(p['precio_inv']), key="e_inv") if st.session_state.role == "admin" else float(p['precio_inv'])
                e_desc = st.text_area("Descripción", value=st.session_state.temp_matriz.get("_info_extra", ""), key="e_desc")
                
                # --- ACTUALIZACIÓN DE IMAGEN (CORREGIDA) ---
                st.divider()
                st.write("**Imagen del Producto**")
                # Usamos la URL almacenada en la sesión para mostrar la vista previa
                if st.session_state.temp_img_url: 
                    st.image(st.session_state.temp_img_url, width=150, caption="Vista Previa")
                
                # Input de texto vinculado a la sesión con on_change
                e_img = st.text_input("Nueva URL de Imagen", 
                                      value=st.session_state.temp_img_url, 
                                      key="e_img_url_input", 
                                      on_change=update_img_url)
            
            with c_e2:
                st.write("**Actualizar Stock y Variantes**")
                nx_c = st.text_input("Color", key="nx_c")
                nx_t = st.text_input("Talla", key="nx_t")
                nx_q = st.number_input("Cant.", 0, key="nx_q")
                if st.button("Actualizar/Agregar Variante", key="btn_nx"):
                    if nx_c and nx_t:
                        if nx_c not in st.session_state.temp_matriz: st.session_state.temp_matriz[nx_c] = {}
                        st.session_state.temp_matriz[nx_c][nx_t] = nx_q
                
                st.divider()
                for c_n, tallas in list(st.session_state.temp_matriz.items()):
                    if c_n != "_info_extra":
                        st.write(f"🎨 {c_n}")
                        for t_n, q_v in list(tallas.items()):
                            r1, r2, r3 = st.columns([2, 1, 1])
                            r1.write(f"Talla: {t_n}")
                            r2.write(f"Stock: {q_v}")
                            if r3.button("🗑️", key=f"del_{c_n}_{t_n}"):
                                del st.session_state.temp_matriz[c_n][t_n]
                                if not st.session_state.temp_matriz[c_n]: del st.session_state.temp_matriz[c_n]
                                st.rerun()

            c_btn1, c_btn2 = st.columns(2)
            # Usamos st.session_state.temp_img_url para guardar
            if c_btn1.button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True, key="btn_save_m"):
                st.session_state.temp_matriz["_info_extra"] = e_desc
                total_stk = sum(sum(v.values()) for k, v in st.session_state.temp_matriz.items() if k != "_info_extra")
                supabase.table("productos").update({
                    "nombre": e_nom, "categoria": e_cat, "subcategoria": e_sub,
                    "precio_pub": e_pub, "precio_inv": e_inv, "stock": total_stk, 
                    "descripcion": json.dumps(st.session_state.temp_matriz),
                    "foto_path": st.session_state.temp_img_url # Guardamos el valor de la sesión
                }).eq("id", st.session_state.edit_id).execute()
                st.session_state.edit_id = None
                st.session_state.temp_img_url = "" # Limpiamos sesión
                st.success("Producto actualizado!"); st.rerun()
            
            if c_btn2.button("Cancelar Edición", use_container_width=True, key="btn_can"): 
                st.session_state.edit_id = None
                st.session_state.temp_img_url = "" # Limpiamos sesión
                st.rerun()
        else: st.info("Selecciona un producto en la pestaña 'Lista'.")

# --- SECCIÓN: CONFIGURACIÓN (SIN CAMBIOS) ---
elif menu == "Configuración" and st.session_state.role == "admin":
    st.header("⚙️ Configuración")
    tipo = st.selectbox("Configurar", ["categoria", "subcategoria", "vendedor", "metodo_pago"], key="cfg_s")
    valor = st.text_input("Valor", key="cfg_v").upper()
    if st.button("Añadir Registro", key="cfg_a"):
        supabase.table("configuracion").insert({"tipo": tipo, "valor": valor}).execute(); st.rerun()
    for item in obtener_config(tipo):
        cl1, cl2 = st.columns([4, 1])
        cl1.write(item['valor'])
        if cl2.button("🗑️", key=f"dc_{item['id']}"):
            supabase.table("configuracion").delete().eq("id", item['id']).execute(); st.rerun()

# --- SECCIÓN: REPORTES (SIN CAMBIOS) ---
elif menu == "Reportes" and st.session_state.role == "admin":
    st.header("📊 Reportes")
    c_f1, c_f2 = st.columns(2)
    f_ini = c_f1.date_input("Inicio", datetime.now() - timedelta(days=30), key="r_i")
    f_fin = c_f2.date_input("Fin", datetime.now(), key="r_f")
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
