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
            if st.button("➕ Agregar"):
                st.session_state.carrito.append({
                    "id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'],
                    "cantidad": v_cant, "precio": v_pre, "precio_inv": float(item['precio_inv'])
                })
                st.toast("Agregado")

        if st.session_state.carrito:
            st.divider()
            st.table(pd.DataFrame(st.session_state.carrito)[['codigo', 'nombre', 'cantidad', 'precio']])
            v_vendedor = st.text_input("Vendedor", value=st.session_state.role.upper())
            if st.button("🚀 FINALIZAR VENTA", type="primary", use_container_width=True):
                # OBTENER FECHA ACTUAL PARA EL REGISTRO
                fecha_ahora = datetime.now(ZONA_LOCAL).isoformat()
                
                for p in st.session_state.carrito:
                    # Descontar stock
                    p_db = supabase.table("productos").select("stock").eq("id", p['id']).execute()
                    n_stk = int(p_db.data[0]['stock']) - p['cantidad']
                    supabase.table("productos").update({"stock": n_stk}).eq("id", p['id']).execute()
                    # Registrar venta con FECHA EXPLÍCITA
                    supabase.table("ventas").insert({
                        "producto": p['nombre'], 
                        "codigo_prod": p['codigo'], 
                        "cantidad": p['cantidad'],
                        "precio_total": float(p['precio'] * p['cantidad']),
                        "ganancia": float((p['precio'] - p['precio_inv']) * p['cantidad']), 
                        "vendedor": v_vendedor,
                        "fecha_venta": fecha_ahora # <--- CORRECCIÓN FECHA
                    }).execute()
                st.session_state.carrito = []
                st.success("Venta Guardada"); st.rerun()

# --- SECCIÓN: INVENTARIO ---
elif menu == "Inventario":
    st.header("📦 Inventario")
    cats, subs = obtener_config("categoria"), obtener_config("subcategoria")
    tabs = st.tabs(["📋 Catálogo e Impresión", "🆕 Nuevo Producto"])
    
    with tabs[0]:
        res = supabase.table("productos").select("*").order("codigo").execute()
        if res.data:
            df_i = pd.DataFrame(res.data)
            c1, c2 = st.columns(2)
            c1.download_button("🖼️ Catálogo con Fotos (Imprimir)", generar_html_catalogo(df_i), "catalogo.html", "text/html")
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                df_i[['codigo', 'nombre', 'precio_pub', 'stock']].to_excel(wr, index=False)
            c2.download_button("📊 Excel de Precios", buf.getvalue(), "precios.xlsx", "application/vnd.ms-excel")
            st.dataframe(df_i, column_config={"foto_path": st.column_config.ImageColumn("Foto")}, use_container_width=True)

    with tabs[1]:
        if st.session_state.role == "admin":
            n_cat = st.selectbox("Categoría", cats)
            n_sub = st.selectbox("Subcategoría", subs)
            n_sku = st.text_input("Código", value=generar_sku(n_cat, n_sub))
            n_nom = st.text_input("Nombre")
            n_pub = st.number_input("Precio Venta", 0.0)
            n_inv = st.number_input("Precio Costo", 0.0)
            n_stk = st.number_input("Stock", 0)
            n_foto = st.file_uploader("Imagen", type=['jpg','png','jpeg'])
            if st.button("Guardar"):
                fn = f"{n_sku}_{datetime.now().strftime('%H%M%S')}.jpg"
                supabase.storage.from_("fotos").upload(fn, n_foto.getvalue())
                url = supabase.storage.from_("fotos").get_public_url(fn)
                supabase.table("productos").insert({
                    "codigo": n_sku.upper(), "nombre": n_nom, "categoria": n_cat, "subcategoria": n_sub,
                    "precio_inv": n_inv, "precio_pub": n_pub, "stock": n_stk, "foto_path": url
                }).execute()
                st.success("Guardado"); st.rerun()

# --- SECCIÓN: CONFIGURACIÓN ---
elif menu == "Configuración":
    st.header("⚙️ Configuración")
    colA, colB = st.columns(2)
    with colA:
        tipo = st.selectbox("Añadir nuevo:", ["categoria", "subcategoria"])
        valor = st.text_input("Nombre").upper().strip()
        if st.button("Añadir"):
            supabase.table("configuracion").insert({"tipo": tipo, "valor": valor}).execute()
            st.rerun()
    with colB:
        tipo_v = st.radio("Ver:", ["categoria", "subcategoria"], horizontal=True)
        res_c = supabase.table("configuracion").select("*").eq("tipo", tipo_v).execute()
        for r in res_c.data:
            c1, c2 = st.columns([4, 1])
            c1.write(r['valor'])
            if c2.button("🗑️", key=r['id']):
                supabase.table("configuracion").delete().eq("id", r['id']).execute(); st.rerun()

# --- SECCIÓN: REPORTES (CORREGIDA) ---
elif menu == "Reportes":
    st.header("📊 Reportes Semanales")
    t_rep = st.tabs(["📈 Análisis por Semana", "📋 Historial Completo", "🚫 Anulaciones"])
    
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        
        # --- BLOQUE DE CORRECCIÓN DE FECHAS ---
        try:
            # Convertir a datetime y asegurar que sea timezone-aware
            df_v['fecha_venta'] = pd.to_datetime(df_v['fecha_venta'], utc=True).dt.tz_convert('America/Mexico_City')
            df_v['Semana'] = df_v['fecha_venta'].dt.strftime('%Y - Sem %U')
        except Exception as e:
            st.error(f"Error procesando fechas: {e}")
            df_v['Semana'] = "Sin Fecha"
        
        with t_rep[0]:
            st.subheader("Ventas y Ganancias por Semana")
            df_semanal = df_v.groupby('Semana').agg({
                'precio_total': 'sum',
                'ganancia': 'sum',
                'id': 'count'
            }).rename(columns={'precio_total': 'Ventas ($)', 'ganancia': 'Ganancia ($)', 'id': 'Cant. Artículos'})
            
            st.dataframe(df_semanal.sort_index(ascending=False), use_container_width=True)
            st.bar_chart(df_semanal[['Ventas ($)', 'Ganancia ($)']])

        with t_rep[1]:
            st.subheader("Historial Detallado")
            # Mostrar fecha formateada bonita
            df_v['Fecha'] = df_v['fecha_venta'].dt.strftime('%d/%m/%Y %H:%M')
            st.dataframe(df_v[['Fecha', 'producto', 'cantidad', 'precio_total', 'vendedor']], use_container_width=True)

        with t_rep[2]:
            st.subheader("Cancelar Venta")
            opc_anul = [f"{r['id']} | {r['producto']} | ${r['precio_total']}" for r in res_v.data]
            sel_anul = st.selectbox("Venta a eliminar:", opc_anul)
            if st.button("Confirmar Anulación"):
                id_a = int(sel_anul.split(" | ")[0])
                v_sel = next(i for i in res_v.data if i['id'] == id_a)
                p_res = supabase.table("productos").select("stock").eq("codigo", v_sel['codigo_prod']).execute()
                if p_res.data:
                    n_s = p_res.data[0]['stock'] + v_sel['cantidad']
                    supabase.table("productos").update({"stock": n_s}).eq("codigo", v_sel['codigo_prod']).execute()
                supabase.table("ventas").delete().eq("id", id_a).execute()
                st.success("Venta anulada"); st.rerun()
    else:
        st.info("No hay ventas registradas aún.")
