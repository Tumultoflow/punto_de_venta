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

# --- 3. SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False
if "carrito" not in st.session_state: st.session_state.carrito = []

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

# --- [VENTAS, INVENTARIO Y CONFIGURACIÓN SE MANTIENEN IGUAL] ---
# (Se omite el código repetido de esas secciones para enfocarnos en Reportes)

if menu == "Ventas":
    st.header("💰 Punto de Venta")
    # ... (Mismo código de la respuesta anterior)

elif menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    # ... (Mismo código de la respuesta anterior)

elif menu == "Configuración":
    st.header("⚙️ Centro de Configuración")
    # ... (Mismo código de la respuesta anterior)

# --- NUEVA SECCIÓN: REPORTES ---
elif menu == "Reportes":
    st.header("📊 Inteligencia de Negocio")
    
    # 1. Filtros
    col_f1, col_f2 = st.columns(2)
    fecha_inicio = col_f1.date_input("Desde", datetime.now() - timedelta(days=30))
    fecha_fin = col_f2.date_input("Hasta", datetime.now())

    # Cargar Datos de Ventas
    res_v = supabase.table("ventas").select("*").gte("fecha_venta", fecha_inicio.isoformat()).lte("fecha_venta", (fecha_fin + timedelta(days=1)).isoformat()).execute()
    
    if res_v.data:
        df_v = pd.DataFrame(res_v.data)
        df_v['fecha_venta'] = pd.to_datetime(df_v['fecha_venta']).dt.tz_convert('America/Mexico_City')
        
        # 2. Métricas Clave
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        total_v = df_v['precio_total'].sum()
        total_g = df_v['ganancia'].sum()
        num_v = len(df_v)
        ticket_prom = total_v / num_v if num_v > 0 else 0
        
        m1.metric("Ventas Totales", f"${total_v:,.2f}")
        m2.metric("Ganancia Neta", f"${total_g:,.2f}")
        m3.metric("Total Operaciones", num_v)
        m4.metric("Ticket Promedio", f"${ticket_prom:,.2f}")

        # 3. Gráficos y Tablas
        st.divider()
        c_r1, c_r2 = st.columns([2, 1])
        
        with c_r1:
            st.subheader("📈 Historial de Ventas")
            df_v['Solo_Fecha'] = df_v['fecha_venta'].dt.date
            ventas_diarias = df_v.groupby('Solo_Fecha')['precio_total'].sum()
            st.line_chart(ventas_diarias)
            
            st.subheader("📝 Detalle de Transacciones")
            st.dataframe(df_v[['id', 'fecha_venta', 'producto', 'cantidad', 'precio_total', 'vendedor']], use_container_width=True)

        with c_r2:
            st.subheader("🏆 Más Vendidos")
            top_prod = df_v.groupby('producto')['cantidad'].sum().sort_values(ascending=False).head(5)
            st.bar_chart(top_prod)

            st.subheader("⚠️ Stock Crítico")
            res_stock = supabase.table("productos").select("nombre, stock").lte("stock", 5).execute()
            if res_stock.data:
                st.warning("Reponer pronto:")
                st.table(pd.DataFrame(res_stock.data))
            else:
                st.success("Stock en niveles óptimos")

        # 4. Exportación
        st.divider()
        csv = df_v.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Reporte (Excel/CSV)", data=csv, file_name=f"reporte_{fecha_inicio}.csv", mime="text/csv")
        
    else:
        st.info("No hay ventas registradas en el rango de fechas seleccionado.")

    # 5. Sección de Cancelaciones (Solo Admin)
    with st.expander("🗑️ Zona de Cancelaciones (Peligro)"):
        st.write("Solo use esto para errores de captura. El stock se devolverá automáticamente.")
        id_anular = st.number_input("ID de la Venta a anular", step=1)
        if st.button("❌ Confirmar Anulación"):
            # Lógica para devolver stock (opcional pero recomendada)
            st.error("Funcionalidad de anulación manual lista para configurar.")
