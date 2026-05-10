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

# --- 2. FUNCIONES DE APOYO ---
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

def subir_imagen_supabase(archivo, sku):
    if archivo is None: return None
    try:
        extension = archivo.name.split(".")[-1]
        nombre_archivo = f"{sku}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"
        supabase.storage.from_('fotos').upload(nombre_archivo, archivo.getvalue())
        return supabase.storage.from_('fotos').get_public_url(nombre_archivo)
    except: return None

# --- 3. MANEJO DE SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []
if "edit_id" not in st.session_state: st.session_state.edit_id = None
if "temp_matriz" not in st.session_state: st.session_state.temp_matriz = {}

# --- 4. LOGIN ---
if not st.session_state.auth:
    st.title("⚖️ Acceso Duo Legal")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar", use_container_width=True):
        if (u == "admin" and p == "admin1") or (u == "equipo" and p == "equipo1"):
            st.session_state.auth, st.session_state.role = True, u
            st.rerun()
        else: st.error("Credenciales incorrectas")
    st.stop()

# --- 5. NAVEGACIÓN ---
with st.sidebar:
    st.title(f"⚖️ {st.session_state.role.upper()}")
    opc = ["Ventas", "Inventario"]
    if st.session_state.role == "admin": opc += ["Configuración", "Reportes"]
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
        busq_v = st.text_input("🔍 Buscar producto para vender...")
        if busq_v: 
            df_p = df_p[df_p['nombre'].str.contains(busq_v, case=False) | df_p['codigo'].str.contains(busq_v, case=False)]
        
        if not df_p.empty:
            sel_list = [f"{r['codigo']} - {r['nombre']}" for _, r in df_p.iterrows()]
            sel = st.selectbox("Seleccionar Producto", sel_list)
            item = df_p[df_p['codigo'] == sel.split(" - ")[0]].iloc[0]
            
            c1, c2 = st.columns([1, 2])
            with c1:
                foto_v = item.get('foto_path')
                if foto_v and str(foto_v).strip().lower() != "none":
                    try: st.image(foto_v, width=250)
                    except: st.write("🖼️❌")
            with c2:
                data_desc = cargar_json_seguro(item['descripcion'])
                matriz = {k: v for k, v in data_desc.items() if k != "_info_extra"}
                
                if matriz:
                    v_col = st.selectbox("Color", list(matriz.keys()))
                    v_tal = st.selectbox("Talla", list(matriz[v_col].keys()))
                    stock_v = matriz[v_col][v_tal]
                    st.metric("Stock Variante", stock_v)
                    v_cant = st.number_input("Cantidad", 1, max(1, int(stock_v)))
                else:
                    v_col, v_tal = "N/A", "N/A"
                    v_cant = st.number_input("Cantidad", 1, int(item['stock']))

                v_pre = st.number_input("Precio de Venta", value=float(item['precio_pub']))
                sel_vendedor = st.selectbox("Vendedor", vendedores)
                
                if st.button("➕ Agregar al Carrito", use_container_width=True):
                    st.session_state.carrito.append({
                        "temp_id": datetime.now().timestamp(), "id": item['id'], "Producto": item['nombre'], 
                        "Cantidad": v_cant, "Precio": v_pre, "Color": v_col, "Talla": v_tal,
                        "Vendedor": sel_vendedor, "es_matriz": bool(matriz), "codigo": item['codigo'],
                        "precio_inv": float(item['precio_inv'])
                    })
                    st.success("Añadido al carrito")

    if st.session_state.carrito:
        st.divider()
        sel_metodo = st.selectbox("Método de Pago", metodos)
        for i, p in enumerate(st.session_state.carrito):
            col_txt, col_btn = st.columns([5, 1])
            col_txt.write(f"**{p['Cantidad']}x {p['Producto']}** ({p['Color']}/{p['Talla']}) | ${p['Precio']*p['Cantidad']:,.2f}")
            if col_btn.button("❌", key=f"del_v_{p['temp_id']}"):
                st.session_state.carrito.pop(i); st.rerun()
        
        if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
            for p in st.session_state.carrito:
                prod_db = supabase.table("productos").select("*").eq("id", p['id']).execute().data[0]
                full_desc = cargar_json_seguro(prod_db['descripcion'])
                if p['es_matriz']:
                    full_desc[p['Color']][p['Talla']] -= p['Cantidad']
                    supabase.table("productos").update({"stock": prod_db['stock']-p['Cantidad'], "descripcion": json.dumps(full_desc)}).eq("id", p['id']).execute()
                    nombre_reporte = f"{p['Producto']} ({p['Color']}-{p['Talla']})"
                else:
                    supabase.table("productos").update({"stock": prod_db['stock']-p['Cantidad']}).eq("id", p['id']).execute()
                    nombre_reporte = p['Producto']
                
                supabase.table("ventas").insert({
                    "producto": nombre_reporte, "codigo_prod": p['codigo'], "cantidad": p['Cantidad'],
                    "precio_total": p['Precio']*p['Cantidad'], "ganancia": (p['Precio']-p['precio_inv'])*p['Cantidad'],
                    "vendedor": p['Vendedor'], "metodo_pago": sel_metodo, "fecha_venta": datetime.now(ZONA_LOCAL).isoformat()
                }).execute()
            st.session_state.carrito = []; st.success("Venta realizada"); st.rerun()

# --- SECCIÓN: INVENTARIO (SIN CATÁLOGO) ---
elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    
    if st.session_state.role == "admin":
        tabs_opc = ["📋 Lista de Productos", "🆕 Registrar Nuevo", "✏️ Editor Maestro"]
    else:
        tabs_opc = ["📋 Lista de Productos"]
    
    pestañas = st.tabs(tabs_opc)

    # 📋 LISTA
    with pestañas[0]:
        busq_i = st.text_input("🔍 Filtrar inventario...")
        res_i = supabase.table("productos").select("*").order("codigo").execute()
        if res_i.data:
            df_i = pd.DataFrame(res_i.data)
            if busq_i: 
                df_i = df_i[df_i['nombre'].str.contains(busq_i, case=False) | df_i['codigo'].str.contains(busq_i, case=False)]
            
            for _, r in df_i.iterrows():
                c_im, c_tx, c_btn1, c_btn2 = st.columns([1, 4, 0.5, 0.5])
                foto = r.get('foto_path')
                if foto and str(foto).strip().lower() != "none":
                    try: c_im.image(foto, width=80)
                    except: c_im.write("🖼️❌")
                else: c_im.write("🚫📸")
                
                c_tx.write(f"**{r['codigo']}** - {r['nombre']}")
                c_tx.caption(f"Stock Total: {r['stock']} | Precio Público: ${r['precio_pub']:,.2f}")
                
                if st.session_state.role == "admin":
                    if c_btn1.button("✏️", key=f"ed_l_{r['id']}"):
                        st.session_state.edit_id = r['id']
                        st.session_state.temp_matriz = cargar_json_seguro(r['descripcion'])
                        st.rerun()
                    if c_btn2.button("🗑️", key=f"del_l_{r['id']}"):
                        supabase.table("productos").delete().eq("id", r['id']).execute(); st.rerun()
                st.divider()

    # 🆕 REGISTRAR (ADMIN)
    if st.session_state.role == "admin":
        cats = [c['valor'] for c in obtener_config("categoria")] or ["GENERAL"]
        subs = [s['valor'] for s in obtener_config("subcategoria")] or ["GENERAL"]
        
        with pestañas[1]:
            c_n1, c_n2 = st.columns(2)
            with c_n1:
                n_cat = st.selectbox("Categoría", cats)
                n_sub = st.selectbox("Subcategoría", subs)
                n_sku = st.text_input("SKU Sugerido", value=generar_sku(n_cat, n_sub))
                n_nom = st.text_input("Nombre del Artículo")
                n_pub = st.number_input("Precio de Venta", 0.0)
                n_inv = st.number_input("Precio Costo (Inversión)", 0.0)
                n_desc = st.text_area("Notas Adicionales")
                n_foto = st.file_uploader("Subir Imagen", type=["jpg","png","jpeg"])
            with c_n2:
                st.write("**Definir Variantes**")
                v_c, v_t, v_s = st.text_input("Color"), st.text_input("Talla"), st.number_input("Stock Inicial", 0)
                if st.button("➕ Añadir a Matriz"):
                    if v_c and v_t:
                        c_up, t_up = v_c.upper().strip(), v_t.upper().strip()
                        if c_up not in st.session_state.temp_matriz: st.session_state.temp_matriz[c_up] = {}
                        st.session_state.temp_matriz[c_up][t_up] = int(v_s)
                st.json(st.session_state.temp_matriz)
            
            if st.button("🚀 GUARDAR PRODUCTO COMPLETO", type="primary", use_container_width=True):
                url = subir_imagen_supabase(n_foto, n_sku)
                st.session_state.temp_matriz["_info_extra"] = n_desc
                validas = {k: v for k, v in st.session_state.temp_matriz.items() if k != "_info_extra"}
                total_stock = sum(int(q) for c, t in validas.items() for q in t.values())
                supabase.table("productos").insert({
                    "codigo": n_sku, "nombre": n_nom, "precio_pub": n_pub, "precio_inv": n_inv, 
                    "stock": total_stock, "descripcion": json.dumps(st.session_state.temp_matriz), 
                    "categoria": n_cat, "subcategoria": n_sub, "foto_path": url
                }).execute()
                st.session_state.temp_matriz = {}; st.success("Registrado con éxito"); st.rerun()

        # ✏️ EDITOR
        with pestañas[2]:
            if st.session_state.edit_id:
                p = supabase.table("productos").select("*").eq("id", st.session_state.edit_id).execute().data[0]
                st.subheader(f"Editando: {p['nombre']}")
                ce1, ce2 = st.columns(2)
                with ce1:
                    e_nom = st.text_input("Nombre", p['nombre'])
                    e_pub = st.number_input("P. Venta", value=float(p['precio_pub']))
                    e_inv = st.number_input("P. Costo", value=float(p['precio_inv']))
                    e_desc = st.text_area("Notas", value=st.session_state.temp_matriz.get("_info_extra", ""))
                    e_foto = st.file_uploader("Cambiar Imagen", type=["jpg","png","jpeg"])
                with ce2:
                    st.write("**Editar Stock/Variantes**")
                    ex_c, ex_t, ex_s = st.text_input("Color Matriz"), st.text_input("Talla Matriz"), st.number_input("Nuevo Stock", 0)
                    if st.button("Actualizar Matriz"):
                        if ex_c and ex_t:
                            c_u, t_u = ex_c.upper().strip(), ex_t.upper().strip()
                            if c_u not in st.session_state.temp_matriz: st.session_state.temp_matriz[c_u] = {}
                            st.session_state.temp_matriz[c_u][t_u] = int(ex_s); st.rerun()
                    
                    for cn, tallas in list(st.session_state.temp_matriz.items()):
                        if cn != "_info_extra":
                            for tn, qs in list(tallas.items()):
                                r1, r2 = st.columns([3,1])
                                r1.write(f"🔹 {cn} - {tn}: {qs}")
                                if r2.button("🗑️", key=f"dv_{cn}_{tn}"):
                                    del st.session_state.temp_matriz[cn][tn]
                                    if not st.session_state.temp_matriz[cn]: del st.session_state.temp_matriz[cn]
                                    st.rerun()
                
                if st.button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True):
                    url = subir_imagen_supabase(e_foto, p['codigo']) or p['foto_path']
                    st.session_state.temp_matriz["_info_extra"] = e_desc
                    validas_e = {k: v for k, v in st.session_state.temp_matriz.items() if k != "_info_extra"}
                    total_e = sum(int(q) for c, t in validas_e.items() for q in t.values())
                    supabase.table("productos").update({
                        "nombre": e_nom, "precio_pub": e_pub, "precio_inv": e_inv, 
                        "stock": total_e, "descripcion": json.dumps(st.session_state.temp_matriz), "foto_path": url
                    }).eq("id", st.session_state.edit_id).execute()
                    st.session_state.edit_id = None; st.success("Actualizado"); st.rerun()
            else: st.info("Selecciona un producto con el icono ✏️ en la lista.")

# --- SECCIÓN: CONFIGURACIÓN ---
elif menu == "Configuración" and st.session_state.role == "admin":
    st.header("⚙️ Ajustes del Sistema")
    opc_cfg = {"CATEGORÍAS": "categoria", "SUBCATEGORÍAS": "subcategoria", "VENDEDORES": "vendedor", "MÉTODOS DE PAGO": "metodo_pago"}
    tab_n = st.selectbox("Elemento a configurar:", list(opc_cfg.keys()))
    tipo_db = opc_cfg[tab_n]
    
    nuevo_v = st.text_input(f"Agregar nuevo {tab_n}:").upper().strip()
    if st.button("➕ Añadir"):
        if nuevo_v: supabase.table("configuracion").insert({"tipo": tipo_db, "valor": nuevo_v}).execute(); st.rerun()
    
    st.divider()
    for item in obtener_config(tipo_db):
        cv, cb = st.columns([4, 1])
        cv.write(f"• {item['valor']}")
        if cb.button("🗑️", key=f"cfg_{item['id']}"): 
            supabase.table("configuracion").delete().eq("id", item['id']).execute(); st.rerun()

# --- SECCIÓN: REPORTES ---
elif menu == "Reportes" and st.session_state.role == "admin":
    st.header("📊 Reporte de Ventas")
    f1, f2 = st.columns(2)
    ini = f1.date_input("Desde", datetime.now() - timedelta(days=7))
    fin = f2.date_input("Hasta", datetime.now())
    
    res = supabase.table("ventas").select("*").gte("fecha_venta", ini.isoformat()).lte("fecha_venta", (fin + timedelta(days=1)).isoformat()).execute()
    if res.data:
        df = pd.DataFrame(res.data)
        st.metric("Venta Bruta", f"${df['precio_total'].sum():,.2f}")
        st.metric("Ganancia Neta", f"${df['ganancia'].sum():,.2f}")
        st.dataframe(df[["fecha_venta", "producto", "cantidad", "precio_total", "vendedor", "metodo_pago"]], use_container_width=True)
    else: st.warning("No hay ventas en este rango.")
