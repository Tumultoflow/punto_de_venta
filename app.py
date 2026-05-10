import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import pytz
import io

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
    except: return ["GENERAL"]

def generar_sku(cat, sub):
    prefijo = f"{cat[:3]}-{sub[:3]}".upper()
    try:
        res = supabase.table("productos").select("codigo").like("codigo", f"{prefijo}%").execute()
        secuencias = [int(r['codigo'].split('-')[-1]) for r in res.data if '-' in r['codigo']]
        proximo = max(secuencias) + 1 if secuencias else 1
        return f"{prefijo}-{proximo:04d}"
    except: return f"{prefijo}-0001"

def generar_html_catalogo(df):
    html = """<html><head><meta charset="UTF-8"><style>
            body { font-family: sans-serif; margin: 20px; }
            .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }
            .card { border: 1px solid #eee; padding: 10px; text-align: center; border-radius: 10px; page-break-inside: avoid; }
            .card img { max-width: 100%; height: 180px; object-fit: contain; }
            .precio { font-size: 22px; color: #1a73e8; font-weight: bold; }
            h1 { text-align: center; border-bottom: 2px solid #333; }
        </style></head><body><h1>📦 CATÁLOGO TUMULTOFLOW</h1><div class="grid">"""
    for _, r in df.iterrows():
        img = r['foto_path'] if r['foto_path'] else "https://via.placeholder.com/200"
        html += f"""<div class="card"><img src="{img}"><div style="font-size:11px; color:gray;">{r['codigo']}</div>
                    <div style="font-weight:bold; height:40px;">{r['nombre']}</div><div class="precio">${r['precio_pub']:,.2f}</div></div>"""
    html += "</div></body></html>"
    return html

# --- 3. MANEJO DE SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "role" not in st.session_state: st.session_state.role = None
if "carrito" not in st.session_state: st.session_state.carrito = []
if "edit_id" not in st.session_state: st.session_state.edit_id = None

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
    st.title("⚖️ MENU")
    opc = ["Ventas", "Inventario"]
    if st.session_state.role == "admin": opc += ["Configuración", "Reportes"]
    menu = st.radio("Sección", opc)
    if st.button("Cerrar Sesión"):
        st.session_state.auth = False
        st.rerun()

# --- SECCIÓN: VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).order("codigo").execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        sel = st.selectbox("Producto", [f"{r['codigo']} - {r['nombre']}" for r in res.data])
        item = df_p[df_p['codigo'] == sel.split(" - ")[0]].iloc[0]
        
        c1, c2 = st.columns([1, 2])
        with c1:
            if item.get('foto_path'): st.image(item['foto_path'], width=200)
        with c2:
            v_cant = st.number_input("Cantidad", 1, int(item['stock']))
            v_pre = st.number_input("Precio unitario", value=float(item['precio_pub']))
            if st.button("➕ Agregar al Carrito"):
                st.session_state.carrito.append({
                    "id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'],
                    "cantidad": v_cant, "precio": v_pre, "precio_inv": float(item['precio_inv'])
                })
                st.toast(f"Agregado: {item['nombre']}")

        if st.session_state.carrito:
            st.divider()
            st.subheader("🛒 Resumen de Venta")
            st.table(pd.DataFrame(st.session_state.carrito)[['codigo', 'nombre', 'cantidad', 'precio']])
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                fecha_manual = st.date_input("Fecha de la venta", datetime.now(ZONA_LOCAL))
                v_vendedor = st.text_input("Vendedor", value=st.session_state.role.upper())
            
            with col_f2:
                st.write("") 
                if st.button("🗑️ VACIAR CARRITO", use_container_width=True):
                    st.session_state.carrito = []
                    st.rerun()

            if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
                hora_actual = datetime.now(ZONA_LOCAL).time()
                fecha_final = datetime.combine(fecha_manual, hora_actual).isoformat()
                
                for p in st.session_state.carrito:
                    p_db = supabase.table("productos").select("stock").eq("id", p['id']).execute()
                    n_stk = int(p_db.data[0]['stock']) - p['cantidad']
                    supabase.table("productos").update({"stock": n_stk}).eq("id", p['id']).execute()
                    supabase.table("ventas").insert({
                        "producto": p['nombre'], "codigo_prod": p['codigo'], "cantidad": p['cantidad'],
                        "precio_total": float(p['precio'] * p['cantidad']),
                        "ganancia": float((p['precio'] - p['precio_inv']) * p['cantidad']), 
                        "vendedor": v_vendedor, "fecha_venta": fecha_final
                    }).execute()
                st.session_state.carrito = []
                st.success("Venta Registrada")
                st.rerun()

# --- SECCIÓN: INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    cats, subs = obtener_config("categoria"), obtener_config("subcategoria")
    tabs = st.tabs(["📋 Lista de Productos", "🆕 Nuevo Producto", "✏️ Editar Producto"])
    
    with tabs[0]:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            df_i = pd.DataFrame(res.data)
            c_desc1, c_desc2 = st.columns(2)
            with c_desc1:
                st.download_button("🖼️ Catálogo Fotos (HTML)", generar_html_catalogo(df_i), "catalogo.html", "text/html", use_container_width=True, key="dl_cat_inv")
            with c_desc2:
                buf = io.BytesIO(); df_i[['codigo', 'nombre', 'precio_pub', 'stock']].to_excel(pd.ExcelWriter(buf, engine='xlsxwriter'), index=False)
                st.download_button("📊 Lista Excel", buf.getvalue(), "precios.xlsx", "application/vnd.ms-excel", use_container_width=True, key="dl_xls_inv")
            
            st.divider()
            cols_h = [1, 3, 1, 1, 1, 1] if st.session_state.role == "admin" else [1, 3, 1, 1, 1]
            h = st.columns(cols_h)
            h[1].write("**Producto**")
            h[2].write("**Stock**")
            h[3].write("**P. Público**")
            if st.session_state.role == "admin": h[4].write("**P. Costo**")
            
            st.divider()
            for _, r in df_i.iterrows():
                col = st.columns(cols_h)
                if r['foto_path']: col[0].image(r['foto_path'], width=60)
                col[1].write(f"**{r['codigo']}** - {r['nombre']} ({r.get('color', 'N/A')}/{r.get('piezas', 'N/A')})")
                col[2].write(f"{r['stock']}")
                col[3].write(f"${r['precio_pub']:,.2f}")
                
                if st.session_state.role == "admin":
                    col[4].write(f"${r['precio_inv']:,.2f}")
                    with col[5]:
                        c_a1, c_a2 = st.columns(2)
                        if c_a1.button("✏️", key=f"edit_inv_b_{r['id']}"):
                            st.session_state.edit_id = r['id']
                            st.rerun()
                        if c_a2.button("🗑️", key=f"del_inv_b_{r['id']}"):
                            supabase.table("productos").delete().eq("id", r['id']).execute()
                            st.rerun()

    with tabs[1]:
        if st.session_state.role == "admin":
            st.subheader("Registrar nuevo ingreso")
            c_n1, c_n2 = st.columns(2)
            with c_n1:
                n_cat = st.selectbox("Categoría", cats, key="n_cat_sel")
                n_sub = st.selectbox("Subcategoría", subs, key="n_sub_sel")
                # GENERACIÓN DINÁMICA DE SKU
                sku_sugerido = generar_sku(n_cat, n_sub)
                n_sku = st.text_input("Código", value=sku_sugerido, key="n_sku_inp")
                n_nom = st.text_input("Nombre", key="n_nom_inp")
                n_color = st.text_input("Color", key="n_color_inp")
            with c_n2:
                n_piezas = st.text_input("Talle / Piezas", key="n_pz_inp")
                n_pub = st.number_input("Precio Venta", 0.0, key="n_pub_inp")
                n_inv = st.number_input("Precio Costo", 0.0, key="n_inv_inp")
                n_stk = st.number_input("Stock", 0, key="n_stk_inp")
                n_foto = st.file_uploader("Imagen", type=['jpg','png','jpeg'], key="n_foto_inp")
            
            if st.button("🚀 Guardar Producto", key="btn_save_final"):
                if n_nom and n_foto:
                    fn = f"{n_sku}_{datetime.now().strftime('%H%M%S')}.jpg"
                    supabase.storage.from_("fotos").upload(fn, n_foto.getvalue())
                    url = supabase.storage.from_("fotos").get_public_url(fn)
                    supabase.table("productos").insert({
                        "codigo": n_sku.upper(), "nombre": n_nom, "categoria": n_cat, "subcategoria": n_sub,
                        "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk, "foto_path": url,
                        "color": n_color, "piezas": n_piezas
                    }).execute()
                    st.success("Guardado con éxito"); st.rerun()

    with tabs[2]:
        if st.session_state.edit_id:
            res_e = supabase.table("productos").select("*").eq("id", st.session_state.edit_id).execute()
            if res_e.data:
                p_edit = res_e.data[0]
                st.subheader(f"Editando: {p_edit['codigo']}")
                e_nom = st.text_input("Nombre", value=p_edit['nombre'], key="e_nom_edit")
                e_color = st.text_input("Color", value=p_edit.get('color', ''), key="e_col_edit")
                e_piezas = st.text_input("Talle/Piezas", value=p_edit.get('piezas', ''), key="e_pz_edit")
                e_pub = st.number_input("Precio Venta", value=float(p_edit['precio_pub']), key="e_pub_edit")
                e_inv = st.number_input("Precio Costo", value=float(p_edit['precio_inv']), key="e_inv_edit")
                e_stk = st.number_input("Stock", value=int(p_edit['stock']), key="e_stk_edit")
                
                c_eb1, c_eb2 = st.columns(2)
                if c_eb1.button("💾 Guardar Cambios", type="primary", key="e_save_btn"):
                    supabase.table("productos").update({
                        "nombre": e_nom, "color": e_color, "piezas": e_piezas,
                        "precio_pub": e_pub, "precio_inv": e_inv, "stock": e_stk
                    }).eq("id", st.session_state.edit_id).execute()
                    st.session_state.edit_id = None
                    st.success("Actualizado"); st.rerun()
                if c_eb2.button("❌ Cancelar", key="e_cancel_btn"):
                    st.session_state.edit_id = None
                    st.rerun()
        else:
            st.info("Selecciona un producto en la lista de Inventario.")

# --- SECCIÓN: CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
    colA, colB = st.columns(2)
    with colA:
        tipo = st.selectbox("Añadir nuevo:", ["categoria", "subcategoria"], key="cfg_t")
        valor = st.text_input("Nombre", key="cfg_v").upper().strip()
        if st.button("Añadir", key="cfg_b"):
            supabase.table("configuracion").insert({"tipo": tipo, "valor": valor}).execute()
            st.rerun()
    with colB:
        tipo_v = st.radio("Ver:", ["categoria", "subcategoria"], horizontal=True, key="cfg_rv")
        res_c = supabase.table("configuracion").select("*").eq("tipo", tipo_v).execute()
        for r in res_c.data:
            c1, c2 = st.columns([4, 1])
            c1.write(r['valor'])
            if c2.button("🗑️", key=f"cfg_del_{r['id']}"):
                supabase.table("configuracion").delete().eq("id", r['id']).execute(); st.rerun()

# --- SECCIÓN: REPORTES ---
elif menu == "Reportes":
    st.header("📊 Reportes y Gestión")
    t_rep = st.tabs(["📈 Análisis Semanal", "📋 Historial Completo", "🛠️ Corregir o Anular Ventas"])
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        df_v['fecha_limpia'] = pd.to_datetime(df_v['fecha_venta'], utc=True, errors='coerce').dt.tz_convert('America/Mexico_City')
        df_v['Semana'] = df_v['fecha_limpia'].dt.strftime('%Y - Sem %U').fillna("SIN FECHA")
        with t_rep[0]:
            df_semanal = df_v.groupby('Semana').agg({'precio_total': 'sum', 'ganancia': 'sum', 'id': 'count'})
            st.dataframe(df_semanal.sort_index(ascending=False), use_container_width=True)
        with t_rep[1]:
            df_v['Fecha Formato'] = df_v['fecha_limpia'].dt.strftime('%d/%m/%Y %H:%M').fillna("🚫 Sin Fecha")
            st.dataframe(df_v[['Fecha Formato', 'producto', 'cantidad', 'precio_total', 'vendedor']], use_container_width=True)
        with t_rep[2]:
            opc_v = [f"{r['id']} | {r['producto']}" for r in res_v.data]
            sel_v = st.selectbox("Venta:", opc_v, key="rep_sel")
            id_sel = int(sel_v.split(" | ")[0])
            c_r1, c_r2 = st.columns(2)
            with c_r1:
                n_f = st.date_input("Fecha correcta", key="rep_d")
                if st.button("Fix Fecha", key="rep_f_btn"):
                    f_f = datetime.combine(n_f, datetime.min.time()).replace(hour=12).isoformat()
                    supabase.table("ventas").update({"fecha_venta": f_f}).eq("id", id_sel).execute()
                    st.rerun()
            with c_r2:
                if st.button("Eliminar Venta", key="rep_del_btn"):
                    v_d = next(i for i in res_v.data if i['id'] == id_sel)
                    p_r = supabase.table("productos").select("stock").eq("codigo", v_d['codigo_prod']).execute()
                    if p_r.data:
                        supabase.table("productos").update({"stock": p_r.data[0]['stock'] + v_d['cantidad']}).eq("codigo", v_d['codigo_prod']).execute()
                    supabase.table("ventas").delete().eq("id", id_sel).execute()
                    st.rerun()
    else: st.info("No hay registros.")
