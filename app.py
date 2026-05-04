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

# --- 2. FUNCIONES DE LÓGICA DE SKUs ---

def generar_sku(cat, sub):
    """Genera el siguiente SKU disponible para una combinación cat-sub."""
    prefijo = f"{cat[:3]}-{sub[:3]}".upper()
    try:
        res = supabase.table("productos").select("codigo").like("codigo", f"{prefijo}%").execute()
        # Extraemos los números de secuencia existentes para evitar saltos
        codigos = [r['codigo'] for r in res.data]
        secuencias = []
        for c in codigos:
            try: secuencias.append(int(c.split('-')[-1]))
            except: continue
        
        proximo = max(secuencias) + 1 if secuencias else 1
        return f"{prefijo}-{proximo:04d}"
    except:
        return f"{prefijo}-0001"

def validar_duplicado(sku, id_actual=None):
    """Verifica si un SKU ya existe (útil para ediciones manuales)."""
    query = supabase.table("productos").select("id").eq("codigo", sku.upper())
    if id_actual:
        query = query.neq("id", id_actual)
    res = query.execute()
    return len(res.data) > 0

def reestructurar_todos_los_codigos():
    """⚠️ FUNCIÓN CRÍTICA: Reasigna códigos a TODA la base de datos desde 0001."""
    productos = supabase.table("productos").select("*").order("created_at").execute()
    if not productos.data: return
    
    contadores = {} # Diccionario para llevar la cuenta por grupo
    
    for p in productos.data:
        prefijo = f"{p['categoria'][:3]}-{p['subcategoria'][:3]}".upper()
        contadores[prefijo] = contadores.get(prefijo, 0) + 1
        nuevo_sku = f"{prefijo}-{contadores[prefijo]:04d}"
        
        # Actualizar en base de datos
        supabase.table("productos").update({"codigo": nuevo_sku}).eq("id", p['id']).execute()

# --- 3. AUTENTICACIÓN Y SESIÓN ---
if "auth" not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Acceso")
    u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "admin1": 
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif u == "equipo" and p == "equipo1": 
            st.session_state.auth, st.session_state.role = True, "equipo"
            st.rerun()
    st.stop()

# --- 4. MENÚ LATERAL ---
with st.sidebar:
    st.header(f"👤 {st.session_state.role.upper()}")
    menu = st.radio("Navegación", ["Ventas", "Inventario", "Configuración", "Reportes"])
    if st.button("Cerrar Sesión"):
        st.session_state.auth = False
        st.rerun()

# --- 5. SECCIÓN INVENTARIO (CON REORGANIZACIÓN) ---
if menu == "Inventario":
    st.header("📦 Gestión de Inventario")
    cats = obtener_config("categoria") if 'obtener_config' in globals() else ["GENERAL"]
    # (Asumiendo que tienes la función obtener_config del código anterior)
    
    # BOTÓN ESPECIAL DE MANTENIMIENTO (Solo Admin)
    if st.session_state.role == "admin":
        with st.expander("🛠️ Herramientas de Mantenimiento"):
            st.warning("Esta acción renombrará TODOS los productos existentes basándose en su categoría actual y reiniciará las secuencias desde 0001.")
            if st.button("♻️ REORGANIZAR TODOS LOS SKUs AHORA"):
                with st.spinner("Procesando base de datos..."):
                    reestructurar_todos_los_codigos()
                st.success("¡Base de datos reorganizada con éxito!")
                st.rerun()

    tab1, tab2 = st.tabs(["📋 Lista y Edición", "🆕 Nuevo Producto"])

    with tab1:
        res = supabase.table("productos").select("*").order("codigo").execute()
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
        
        if not df.empty:
            st.subheader("📝 Editar Producto")
            opciones = [f"{r['codigo']} | {r['nombre']}" for r in res.data]
            seleccion = st.selectbox("Buscar producto:", ["-- Seleccionar --"] + opciones)
            
            if seleccion != "-- Seleccionar --":
                cod_actual = seleccion.split(" | ")[0]
                item = df[df['codigo'] == cod_actual].iloc[0]
                
                # Formulario dinámico
                with st.form(f"edit_{item['id']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_nom = st.text_input("Nombre", value=item['nombre'])
                        new_cat = st.selectbox("Categoría", cats, index=cats.index(item['categoria']) if item['categoria'] in cats else 0)
                        new_sub = st.text_input("Subcategoría", value=item['subcategoria']) # O selectbox si prefieres
                    
                    with col2:
                        # LOGICA DE CAMBIO DE CÓDIGO EN TIEMPO REAL
                        if new_cat != item['categoria']:
                            sugerencia = generar_sku(new_cat, new_sub)
                            st.info(f"Sugerencia por cambio de categoría: **{sugerencia}**")
                            new_cod = st.text_input("Código SKU", value=sugerencia)
                        else:
                            new_cod = st.text_input("Código SKU", value=item['codigo'])
                        
                        new_stk = st.number_input("Stock", value=int(item['stock']))
                        new_pub = st.number_input("Precio", value=float(item['precio_pub']))

                    # Validar si el código ya existe
                    duplicado = validar_duplicado(new_cod, item['id'])
                    if duplicado: st.error("⚠️ Este código ya pertenece a otro producto.")

                    if st.form_submit_button("Guardar Cambios") and not duplicado:
                        supabase.table("productos").update({
                            "nombre": new_nom, "codigo": new_cod.upper(),
                            "categoria": new_cat, "subcategoria": new_sub,
                            "stock": new_stk, "precio_pub": new_pub
                        }).eq("id", item['id']).execute()
                        st.success("Actualizado")
                        st.rerun()

            st.divider()
            st.dataframe(df, use_container_width=True)

    with tab2:
        st.subheader("Registrar producto con SKU automático")
        # Aquí iría el formulario de "Nuevo Producto" similar al que ya tienes, 
        # usando la función generar_sku(n_cat, n_sub) para el valor default del campo código.

# --- (El resto de las secciones: Ventas, Config, Reportes se mantienen igual) ---
