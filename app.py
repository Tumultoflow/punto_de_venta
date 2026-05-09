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
def generar_html_catalogo(df):
    """Genera un archivo HTML con diseño de catálogo para imprimir."""
    html = """
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; }
            .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
            .card { border: 1px solid #ccc; padding: 10px; text-align: center; border-radius: 8px; page-break-inside: avoid; }
            .card img { max-width: 100%; height: 150px; object-fit: contain; }
            .precio { font-size: 20px; color: #2e7d32; font-weight: bold; }
            .sku { font-size: 12px; color: #666; }
            h1 { text-align: center; }
            @media print { .no-print { display: none; } }
        </style>
    </head>
    <body>
        <h1>Catálogo de Precios - TumultoFlow</h1>
        <div class="grid">
    """
    for _, r in df.iterrows():
        img = r['foto_path'] if r['foto_path'] else "https://via.placeholder.com/150"
        html += f"""
        <div class="card">
            <img src="{img}">
            <div class="sku">{r['codigo']}</div>
            <div style="font-weight:bold;">{r['nombre']}</div>
            <div>{r['categoria']}</div>
            <div class="precio">${r['precio_pub']:,.2f}</div>
        </div>
        """
    html += "</div></body></html>"
    return html

# --- 3. MANEJO DE SESIÓN Y LOGIN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "role" not in st.session_state: st.session_state.role = None
if "carrito" not in st.session_state: st.session_state.carrito = []

if not st.session_state.auth:
    st.title("⚖️ Acceso Sistema TumultoFlow")
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

# --- 4. NAVEGACIÓN ---
with st.sidebar:
    st.title("⚖️ MENU")
    opciones = ["Ventas", "Inventario"]
    if st.session_state.role == "admin": opciones += ["Configuración", "Reportes"]
    menu = st.radio("Ir a:", opciones)
    if st.button("Cerrar Sesión"):
        st.session_state.auth = False
        st.rerun()

# --- SECCIÓN: VENTAS ---
if menu == "Ventas":
    st.header("💰 Punto de Venta")
    res = supabase.table("productos").select("*").gt("stock", 0).order("codigo").execute()
    if res.data:
        df_p = pd.DataFrame(res.data)
        sel_prod = st.selectbox("📦 Producto", [f"{r['codigo']} - {r['nombre']}" for r in res.data])
        item = df_p[df_p['codigo'] == sel_prod.split(" - ")[0]].iloc[0]
        
        c1, c2 = st.columns([1, 2])
        with c1:
            if item.get('foto_path'): st.image(item['foto_path'], width=200)
        with c2:
            st.subheader(item['nombre'])
            v_cant = st.number_input("Cantidad", 1, int(item['stock']))
            v_pre = st.number_input("Precio Final", value=float(item['precio_pub']))
            if st.button("➕ Añadir al Carrito"):
                st.session_state.carrito.append({
                    "id": item['id'], "codigo": item['codigo'], "nombre": item['nombre'],
                    "cantidad": v_cant, "precio": v_pre, "precio_inv": float(item['precio_inv'])
                })
                st.toast("Añadido al carrito")

        if st.session_state.carrito:
            st.divider()
            st.subheader("🛒 Carrito Actual")
            df_car = pd.DataFrame(st.session_state.carrito)
            st.table(df_car[['codigo', 'nombre', 'cantidad', 'precio']])
            v_vend = st.text_input("Vendedor", value="Equipo" if st.session_state.role == "equipo" else "")
            
            if st.button("🚀 FINALIZAR Y REGISTRAR VENTA", type="primary", use_container_width=True):
                try:
                    for p in st.session_state.carrito:
                        # 1. Obtener stock actual de la DB para evitar errores de desfase
                        prod_db = supabase.table("productos").select("stock").eq("id", p['id']).execute()
                        stock_actual = prod_db.data[0]['stock']
                        
                        # 2. Descontar stock
                        supabase.table("productos").update({"stock": stock_actual - p['cantidad']}).eq("id", p['id']).execute()
                        
                        # 3. Registrar venta
                        supabase.table("ventas").insert({
                            "producto": str(p['nombre']),
                            "codigo_prod": str(p['codigo']),
                            "cantidad": int(p['cantidad']),
                            "precio_total": float(p['precio'] * p['cantidad']),
                            "ganancia": float((p['precio'] - p['precio_inv']) * p['cantidad']),
                            "vendedor": str(v_vend)
                        }).execute()
                    
                    st.session_state.carrito = []
                    st.success("¡Venta registrada exitosamente!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error crítico al registrar: {e}")

# --- SECCIÓN: INVENTARIO (CON CATÁLOGO IMPRIMIBLE) ---
elif menu == "Inventario":
    st.header("📦 Inventario y Catálogo")
    res = supabase.table("productos").select("*").order("codigo").execute()
    if res.data:
        df_i = pd.DataFrame(res.data)
        
        # --- BLOQUE DE DESCARGA DE CATÁLOGO ---
        st.info("💡 Genera el catálogo visual para que el equipo lo imprima o lo traiga en su celular.")
        col_cat1, col_cat2 = st.columns(2)
        
        with col_cat1:
            html_content = generar_html_catalogo(df_i)
            st.download_button(
                label="🖼️ Descargar Catálogo con Imágenes (Para Imprimir)",
                data=html_content,
                file_name="catalogo_imprimible_tumultoflow.html",
                mime="text/html",
                use_container_width=True
            )
        with col_cat2:
            # Opción rápida en Excel por si necesitan editar algo
            buffer = io.BytesIO()
            df_i[['codigo', 'nombre', 'precio_pub', 'stock']].to_excel(buffer, index=False)
            st.download_button(
                label="Excel de Precios (Solo Texto)",
                data=buffer,
                file_name="lista_precios.xlsx",
                use_container_width=True
            )
        
        st.divider()
        # --- TABLA DE GESTIÓN ---
        st.dataframe(
            df_i,
            column_config={
                "foto_path": st.column_config.ImageColumn("Foto"),
                "precio_pub": st.column_config.NumberColumn("Venta", format="$%.2f"),
                "precio_inv": st.column_config.NumberColumn("Costo", format="$%.2f") if st.session_state.role == "admin" else None
            },
            use_container_width=True
        )

# --- SECCIÓN: REPORTES (ADMIN) ---
elif menu == "Reportes" and st.session_state.role == "admin":
    st.header("📊 Reportes Semanales")
    res_v = supabase.table("ventas").select("*").order("fecha_venta", desc=True).execute()
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        df_v['fecha_venta'] = pd.to_datetime(df_v['fecha_venta']).dt.tz_convert('America/Mexico_City')
        st.metric("Ingresos Totales", f"${df_v['precio_total'].sum():,.2f}")
        st.dataframe(df_v, use_container_width=True)
    else:
        st.warning("No hay ventas registradas.")
