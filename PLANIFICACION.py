import streamlit as st
import pandas as pd
import os
import time
import smtplib
from datetime import date, timedelta
from email.mime.text import MIMEText
import gspread
from google.oauth2.service_account import Credentials

# ===============================
# CONFIGURACIÓN DE LA PÁGINA
# ===============================
st.set_page_config(
    page_title="Gestión de Planificación y TPM - Softys",
    layout="wide",
    page_icon="🏭"
)

# ===============================
# MARCA DE AGUA DE FONDO (ERC)
# ===============================
st.markdown("""
<style>
.stApp::before {
    content: "ERC";
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%) rotate(-25deg);
    font-size: 22vw;
    font-weight: 900;
    font-family: Arial, sans-serif;
    color: rgba(120, 120, 120, 0.07);
    z-index: 0;
    pointer-events: none;
    user-select: none;
    white-space: nowrap;
}
</style>
""", unsafe_allow_html=True)

# ===============================
# COLOR EN CASILLEROS DE TARJETAS (Rojas / Verdes / Azules)
# ===============================
st.markdown("""
<style>
div[data-testid="stNumberInput"]:has(input[aria-label="Tarjetas Rojas"]) {
    background-color: rgba(255, 0, 0, 0.18);
    border-radius: 8px;
    padding: 6px;
}
div[data-testid="stNumberInput"]:has(input[aria-label="Tarjetas Verdes"]) {
    background-color: rgba(0, 170, 0, 0.18);
    border-radius: 8px;
    padding: 6px;
}
div[data-testid="stNumberInput"]:has(input[aria-label="Tarjetas Azules"]) {
    background-color: rgba(0, 110, 255, 0.18);
    border-radius: 8px;
    padding: 6px;
}
</style>
""", unsafe_allow_html=True)

st.title("🏭 Sistema Integrado de Planificación y TPM")
st.markdown("Control de Avisos, OM, Especialidades, Lubricación y Gestión de Pendientes por Línea.")

# ===============================
# LOGIN (usuario y contraseña)
# ===============================
def verificar_login():
    if st.session_state.get("autenticado", False):
        return True

    st.subheader("🔒 Acceso restringido")
    with st.form("form_login"):
        usuario_input = st.text_input("Usuario")
        clave_input = st.text_input("Contraseña", type="password")
        entrar = st.form_submit_button("Ingresar")

    if entrar:
        usuario_ok = usuario_input == st.secrets["auth"]["usuario"]
        clave_ok = clave_input == st.secrets["auth"]["password"]
        if usuario_ok and clave_ok:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

    return False

if not verificar_login():
    st.stop()

with st.sidebar:
    st.write("")
    if st.button("🚪 Cerrar sesión"):
        st.session_state["autenticado"] = False
        st.rerun()

# ===============================
# CONEXIÓN A GOOGLE SHEETS
# ===============================
COLUMNAS_REQUERIDAS = [
    "Fecha", "Linea", "Acciones_Dia", "Tareas_Electricas", "Tareas_Mecanicas",
    "Formulario_Mejoras", "Estado", "Tarjetas_Rojas", "Tarjetas_Verdes", "Tarjetas_Azules",
    "Avisos_Creados", "OM_Creadas", "Numero_Averias",
    "Lub_Planeados_MA", "Lub_Ejecutados_MA", "TPM_Inspeccion_MA", "Observaciones_MA",
    "Lub_Planeados_MP", "Lub_Ejecutados_MP", "TPM_Inspeccion_MP", "Observaciones_MP",
    "Preventivo_Fecha", "Preventivo_Tarea", "Fecha_Cierre", "Eficiencia_Diaria"
]

@st.cache_resource
def conectar_sheet():
    scopes = ["https://googleapis.com"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    cliente = gspread.authorize(creds)
    hoja = cliente.open_by_key(st.secrets["gsheet"]["sheet_id"]).sheet1
    return hoja

def cargar_datos():
    hoja = conectar_sheet()
    registros = hoja.get_all_records()

    if not registros:
        df_inicial = pd.DataFrame([{
            "Fecha": str(date.today()), "Linea": "PALETIZADO",
            "Acciones_Dia": "Sistema inicializado correctamente.", "Tareas_Electricas": "Revisión inicial", "Tareas_Mecanicas": "Inspección de polines",
            "Formulario_Mejoras": "", "Estado": "Listo", "Tarjetas_Rojas": 0, "Tarjetas_Verdes": 0, "Tarjetas_Azules": 0,
            "Avisos_Creados": 0, "OM_Creadas": 0, "Numero_Averias": 0,
            "Lub_Planeados_MA": 0, "Lub_Ejecutados_MA": 0, "TPM_Inspeccion_MA": 0, "Observaciones_MA": "",
            "Lub_Planeados_MP": 0, "Lub_Ejecutados_MP": 0, "TPM_Inspeccion_MP": 0, "Observaciones_MP": "",
            "Preventivo_Fecha": str(date.today()), "Preventivo_Tarea": "",
            "Fecha_Cierre": str(date.today()), "Eficiencia_Diaria": 0
        }, {
            "Fecha": str(date.today()), "Linea": "LAM 3",
            "Acciones_Dia": "Sistema inicializado correctamente.", "Tareas_Electricas": "Revisión inicial", "Tareas_Mecanicas": "Inspección de cadenas",
            "Formulario_Mejoras": "", "Estado": "Listo", "Tarjetas_Rojas": 0, "Tarjetas_Verdes": 0, "Tarjetas_Azules": 0,
            "Avisos_Creados": 0, "OM_Creadas": 0, "Numero_Averias": 0,
            "Lub_Planeados_MA": 0, "Lub_Ejecutados_MA": 0, "TPM_Inspeccion_MA": 0, "Observaciones_MA": "",
            "Lub_Planeados_MP": 0, "Lub_Ejecutados_MP": 0, "TPM_Inspeccion_MP": 0, "Observaciones_MP": "",
            "Preventivo_Fecha": str(date.today()), "Preventivo_Tarea": "",
            "Fecha_Cierre": str(date.today()), "Eficiencia_Diaria": 0
        }])
        guardar_datos(df_inicial)
        return df_inicial

    df = pd.DataFrame(registros)
    for col in COLUMNAS_REQUERIDAS:
        if col not in df.columns:
            df[col] = 0 if any(x in col for x in ["Tarjetas", "Avisos", "OM", "Numero", "Lub", "TPM", "Eficiencia"]) else ""
    df = df[COLUMNAS_REQUERIDAS]
    
    df["Fecha"] = pd.to_datetime(df["Fecha"].astype(str).str.strip(), errors="coerce")
    df["Fecha"] = df["Fecha"].fillna(pd.to_datetime(date.today()))
    
    df["Fecha_Cierre"] = pd.to_datetime(df["Fecha_Cierre"], errors="coerce")
    df["Eficiencia_Diaria"] = pd.to_numeric(df["Eficiencia_Diaria"], errors="coerce").fillna(0)
    df["Linea"] = df["Linea"].astype(str).str.strip()
    df["Estado"] = df["Estado"].astype(str).str.strip()
    return df

def guardar_datos(df):
    hoja = conectar_sheet()
    df_guardar = df.copy()

    def _sanitizar_valor(v):
        try:
            if pd.isna(v):
                return ""
        except (TypeError, ValueError):
            pass
        if isinstance(v, date):
            return str(v)
        if hasattr(v, "item"):
            try:
                return v.item()
            except Exception:
                return str(v)
        return v

    for col in df_guardar.columns:
        df_guardar[col] = df_guardar[col].map(_sanitizar_valor)

    valores = [df_guardar.columns.values.tolist()] + df_guardar.values.tolist()

    tipos_validos = (str, int, float, bool, type(None))
    valores = [
        [v if isinstance(v, tipos_validos) else str(v) for v in fila]
        for fila in valores
    ]

    for intento in range(3):
        try:
            filas_previas = len(hoja.col_values(1))
            hoja.update(valores)
            if filas_previas > len(valores):
                hoja.batch_clear([f"A{len(valores) + 1}:Z{filas_previas}"])
            break
        except Exception as e:
            if intento == 2:
                st.error(f"Error crítico al guardar en Google Sheets: {e}")
            else:
                time.sleep(2)

def enviar_correo_preventivo(fecha_prev, linea, tarea):
    try:
        correo_emisor = st.secrets["email"]["usuario"]
        password_correo = st.secrets["email"]["password"]
        smtp_server = st.secrets["email"].get("smtp_server", "://gmail.com")
        smtp_port = int(st.secrets["email"].get("smtp_port", 587))

        destinatarios_linea = st.secrets.get("email_recipients", {}).get(linea, None)

        if not destinatarios_linea:
            st.session_state["ultimo_error_mail"] = f"No hay correos configurados para la línea '{linea}' en Secrets."
            return False

        lista_destinatarios = []
        if destinatarios_linea.get("mecanico"):
            lista_destinatarios.append(destinatarios_linea["mecanico"])
        if destinatarios_linea.get("electrico"):
            lista_destinatarios.append(destinatarios_linea["electrico"])

        if not lista_destinatarios:
            st.session_state["ultimo_error_mail"] = f"La línea '{linea}' no tiene correos de mecánico ni eléctrico configurados."
            return False

        msg = MIMEText(f"🚨 ALERTA DE MANTENCIÓN PREVENTIVA:\n\nSe ha programado una mantención para la línea {linea}.\nFecha: {fecha_prev}\nTrabajo a realizar: {tarea}\n\nPor favor gestionar los recursos y herramientas.")
        msg['Subject'] = f"⚠️ Preventivo Programado - Línea {linea} ({fecha_prev})"
        msg['From'] = correo_emisor
        msg['To'] = ", ".join(lista_destinatarios)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(correo_emisor, password_correo)
        server.sendmail(correo_emisor, lista_destinatarios, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.session_state["ultimo_error_mail"] = str(e)
        return False

df_historico = cargar_datos()

# ===============================
# SELECTOR DE LÍNEA PRODUCTIVA
# ===============================
st.sidebar.header("🕹️ Navegación de Pantallas")
LINEAS_DISPONIBLES = ["LAM 1", "LAM 2", "260", "230", "190", "LAM 3", "PALETIZADO"]
linea_activa = st.sidebar.selectbox("Selecciona la Línea Productiva:", LINEAS_DISPONIBLES)

st.subheader(f"🖥️ Pantalla Actual: Área de {linea_activa}")

# ===============================
# SENSOR DE ALERTAS
# ===============================
col_alertas1, col_alertas2 = st.columns(2)

with col_alertas1:
    df_pendientes_linea = df_historico[(df_historico["Estado"] == "Pendiente") & (df_historico["Linea"] == linea_activa)].copy()
