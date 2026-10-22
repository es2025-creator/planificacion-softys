import streamlit as st
import pandas as pd
import os
import time
import smtplib
import json
import base64
import uuid
import altair as alt
from datetime import datetime as _datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
from datetime import date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
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

# Evita que Chrome/Edge traduzcan la página sola (rompe React: "removeChild")
_JS_NOTRANSLATE = """<script>
const d = window.parent.document;
d.documentElement.setAttribute("translate", "no");
d.documentElement.setAttribute("lang", "es");
if (!d.querySelector('meta[name="google"]')) {
    const m = d.createElement("meta"); m.name = "google"; m.content = "notranslate"; d.head.appendChild(m);
}
</script>"""
if hasattr(st, "iframe"):            # Streamlit reciente
    st.iframe(_JS_NOTRANSLATE, height=1)
else:                                # Streamlit más antiguo
    import streamlit.components.v1 as _components
    _components.html(_JS_NOTRANSLATE, height=0)

# ===============================
# TEMA ELEGANTE (azul marino + dorado) — se adapta al modo claro / oscuro de Streamlit
# ===============================
COLOR_ROJO, COLOR_VERDE, COLOR_AZUL = "#D32F2F", "#2E7D32", "#1565C0"
COLOR_DORADO, COLOR_ACR_EJEC = "#C9A227", "#2F6FDB"   # se ven bien en fondo claro y oscuro

try:
    _tipo_tema = st.context.theme.type   # "light" | "dark" | None (si aún no se conoce)
except Exception:
    _tipo_tema = None


# Selectores de casillas: sirven para versiones nuevas de Streamlit (sin "baseweb") y para las antiguas.
_CAMPOS = (
    '[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div, '
    '[data-testid="stNumberInputContainer"], [data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"], '
    '[data-testid="stDateInputField"], [data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"]')
_INTERNOS = 'input, textarea, [data-testid="stDateInputField"] [role="spinbutton"]'
_PASOS = ('button[data-testid^="stNumberInputStep"], [data-testid="stSelectbox"] button, '
          '[data-testid="stMultiSelect"] button')
_LISTAS = ('[data-baseweb="popover"] ul, [data-baseweb="menu"], [role="listbox"], '
           '[data-testid="stSelectboxVirtualDropdown"], .react-aria-Popover')
_OPCIONES = '[data-baseweb="popover"] li, [data-baseweb="popover"] li *, [role="option"], [role="option"] *'
_HOVER = '[data-baseweb="popover"] li:hover, [role="option"]:hover, [role="option"][data-focused="true"]'

def _aplicar(css):
    return (css.replace("{CAMPOS}", _CAMPOS).replace("{INTERNOS}", _INTERNOS).replace("{PASOS}", _PASOS)
               .replace("{LISTAS}", _LISTAS).replace("{OPCIONES}", _OPCIONES).replace("{HOVER}", _HOVER))

CSS_BASE = """
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0B2545 0%, #13315C 100%); }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label p { color: #F1E7C1 !important; border: 0; }
[data-testid="stSidebar"] [data-baseweb="select"] div, [data-testid="stSidebar"] [data-testid="stSelectbox"] [role="group"],
[data-testid="stSidebar"] [data-testid="stSelectbox"] button, [data-testid="stSidebar"] [data-testid="stSelectbox"] input,
[data-testid="stSidebar"] [data-baseweb="select"] input {
    background-color: #F4F7FC !important; color: #0B2545 !important; -webkit-text-fill-color: #0B2545 !important; }
[data-testid="stSidebar"] [data-baseweb="select"] svg, [data-testid="stSidebar"] [data-testid="stSelectbox"] svg { fill: #0B2545 !important; }

h1 { font-weight: 800 !important; letter-spacing: .3px; border-bottom: 3px solid #C9A227; padding-bottom: .35rem; }
hr { border-color: rgba(201,162,39,.55) !important; }

.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button,
[data-testid="stFileUploaderDropzone"] button {
    background: linear-gradient(135deg, #0B2545, #13315C); border: 1px solid #C9A227;
    border-radius: 10px; font-weight: 600; box-shadow: 0 2px 8px rgba(11,37,69,.18);
}
.stButton > button *, .stFormSubmitButton > button *, .stDownloadButton > button *,
[data-testid="stFileUploaderDropzone"] button * { color: #ffffff !important; }
.stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover,
[data-testid="stFileUploaderDropzone"] button:hover { background: #C9A227; border-color: #C9A227; }
.stButton > button:hover *, .stFormSubmitButton > button:hover *, .stDownloadButton > button:hover *,
[data-testid="stFileUploaderDropzone"] button:hover * { color: #0B2545 !important; }
.stButton > button:disabled, .stFormSubmitButton > button:disabled { opacity: .4; cursor: not-allowed; box-shadow: none; }
[data-testid="stExpander"], [data-testid="stForm"] { border-radius: 14px; }
[data-testid="stMetric"] { border-left: 5px solid #C9A227; border-radius: 12px; padding: .7rem 1rem; }
"""

CSS_CLARO = """
.stApp { background: linear-gradient(180deg, #f7f8fc 0%, #e8edf6 100%); }
:where([data-testid="stMain"]) :where(p, span, label, li, div, summary, h1, h2, h3, h4, h5, h6) { color: #14213D !important; }
h1, h2, h3 { color: #0B2545 !important; }
{CAMPOS} { background-color: #ffffff !important; border: 1px solid #c5cfe3 !important; border-radius: 10px !important; }
{INTERNOS} { background-color: transparent !important; color: #0B2545 !important; -webkit-text-fill-color: #0B2545 !important; }
{PASOS} { background: #eef2fa !important; color: #0B2545 !important; }
{PASOS} svg { fill: #0B2545 !important; }
{LISTAS} { background: #ffffff !important; }
{OPCIONES} { color: #0B2545 !important; }
{HOVER} { background: #eef2fa !important; }
[data-testid="stFileUploaderDropzone"] { background: #f4f7fc !important; border: 1px dashed #aab7d3 !important; }
[data-testid="stExpander"], [data-testid="stForm"] { background: #ffffff; border: 1px solid #d9e0ee; box-shadow: 0 4px 14px rgba(11,37,69,.08); }
[data-testid="stMetric"] { background: #ffffff; box-shadow: 0 2px 10px rgba(11,37,69,.08); }
"""

CSS_OSCURO = """
.stApp { background: linear-gradient(180deg, #0B1B33 0%, #12294A 100%); }
:where([data-testid="stMain"]) :where(p, span, label, li, div, summary, h4, h5, h6) { color: #E8EEF9 !important; }
h1, h2, h3 { color: #F1E7C1 !important; }
{CAMPOS} { background-color: #1F3A63 !important; border: 1px solid rgba(201,162,39,.55) !important; border-radius: 10px !important; }
{INTERNOS} { background-color: transparent !important; color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
{PASOS} { background: #2A4A7C !important; color: #ffffff !important; }
{PASOS} svg { fill: #ffffff !important; }
{LISTAS} { background: #1F3A63 !important; }
{OPCIONES} { color: #ffffff !important; }
{HOVER} { background: #2A4A7C !important; }
[data-testid="stFileUploaderDropzone"] { background: #1F3A63 !important; border: 1px dashed rgba(201,162,39,.6) !important; }
[data-testid="stExpander"], [data-testid="stForm"] { background: rgba(255,255,255,.05); border: 1px solid rgba(201,162,39,.35); }
[data-testid="stMetric"] { background: #16305A; }
"""

if _tipo_tema == "dark":
    _css = CSS_BASE + _aplicar(CSS_OSCURO)
elif _tipo_tema == "light":
    _css = CSS_BASE + _aplicar(CSS_CLARO)
else:   # aún no se conoce el modo: se sigue el del sistema operativo
    _css = CSS_BASE + _aplicar(CSS_CLARO) + "@media (prefers-color-scheme: dark) {" + _aplicar(CSS_OSCURO) + "}"
st.markdown("<style>" + _css + "</style>", unsafe_allow_html=True)

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
# CONEXIÓN A GOOGLE SHEETS (base de datos persistente)
# ===============================
COLUMNAS_REQUERIDAS = [
    "Fecha", "Linea", "Acciones_Dia", "Tareas_Electricas", "Tareas_Mecanicas",
    "Formulario_Mejoras", "Estado", "Tarjetas_Rojas", "Tarjetas_Verdes", "Tarjetas_Azules",
    "Avisos_Creados", "OM_Creadas", "Numero_Averias",
    "Lub_Planeados_MA", "Lub_Ejecutados_MA", "TPM_Inspeccion_MA", "Observaciones_MA",
    "Lub_Planeados_MP", "Lub_Ejecutados_MP", "TPM_Inspeccion_MP", "Observaciones_MP",
    "Preventivo_Fecha", "Preventivo_Tarea", "Fecha_Cierre", "Eficiencia_Diaria",
    "Dias_Sin_Accidentes", "ACR_Solicitado", "ACR_Ejecutado",
    "MTTR_min", "MTBF_h", "Disponibilidad_pct", "Preventivo_Adjunto"
]
COLS_NUM_NUEVAS = ["Dias_Sin_Accidentes", "ACR_Solicitado", "ACR_Ejecutado",
                   "MTTR_min", "MTBF_h", "Disponibilidad_pct"]

@st.cache_resource
def conectar_libro():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    cliente = gspread.authorize(creds)
    return cliente.open_by_key(st.secrets["gsheet"]["sheet_id"])

@st.cache_resource
def conectar_sheet():
    return conectar_libro().sheet1

def cargar_datos():
    hoja = conectar_sheet()
    registros = hoja.get_all_records()

    if not registros:
        # Hoja vacía: la inicializamos con dos filas de ejemplo
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
        for _c in COLUMNAS_REQUERIDAS:
            if _c not in df_inicial.columns:
                df_inicial[_c] = 0 if _c in COLS_NUM_NUEVAS else ""
        df_inicial = df_inicial[COLUMNAS_REQUERIDAS]
        guardar_datos(df_inicial)
        return df_inicial

    df = pd.DataFrame(registros)
    for col in COLUMNAS_REQUERIDAS:
        if col not in df.columns:
            df[col] = 0 if (col in COLS_NUM_NUEVAS or any(x in col for x in ["Tarjetas", "Avisos", "OM", "Numero", "Lub", "TPM", "Eficiencia"])) else ""
    df = df[COLUMNAS_REQUERIDAS]
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    # Fecha_Cierre puede venir vacía (tarea aún pendiente); se deja como NaT en ese caso.
    df["Fecha_Cierre"] = pd.to_datetime(df["Fecha_Cierre"], errors="coerce")
    df["Eficiencia_Diaria"] = pd.to_numeric(df["Eficiencia_Diaria"], errors="coerce").fillna(0)
    for _c in COLS_NUM_NUEVAS:
        df[_c] = pd.to_numeric(df[_c], errors="coerce").fillna(0)
    # Google Sheets convierte líneas como "190" en números; se normalizan a texto
    # para que coincidan con las opciones del selector de línea.
    df["Linea"] = df["Linea"].astype(str).str.strip()
    df["Estado"] = df["Estado"].astype(str).str.strip()
    return df

def guardar_datos(df):
    hoja = conectar_sheet()
    df_guardar = df.copy()

    def _sanitizar_valor(v):
        # Convierte cualquier fecha/hora (Timestamp, date, NaT) a texto plano,
        # y cualquier valor vacío/nulo a "", para que Google Sheets lo acepte.
        try:
            if pd.isna(v):
                return ""
        except (TypeError, ValueError):
            pass
        if isinstance(v, date):
            return str(v)
        # Convierte tipos numéricos de numpy (int64, float64, bool_, etc.)
        # a tipos nativos de Python, que sí son válidos para enviar a Google Sheets.
        if hasattr(v, "item"):
            try:
                return v.item()
            except Exception:
                return str(v)
        return v

    for col in df_guardar.columns:
        df_guardar[col] = df_guardar[col].map(_sanitizar_valor)

    valores = [df_guardar.columns.values.tolist()] + df_guardar.values.tolist()

    # Última red de seguridad: cualquier valor que no sea texto, número,
    # booleano o vacío, se convierte a texto para evitar errores de envío.
    tipos_validos = (str, int, float, bool, type(None))
    valores = [
        [v if isinstance(v, tipos_validos) else str(v) for v in fila]
        for fila in valores
    ]

    # Se escribe primero y solo después se limpian las filas sobrantes, así una
    # falla de Google a mitad de camino nunca deja la hoja vacía. Si Google
    # responde con un error temporal, se reintenta hasta 3 veces.
    for intento in range(3):
        try:
            filas_previas = len(hoja.col_values(1))
            if hoja.col_count < len(valores[0]):
                hoja.resize(cols=len(valores[0]))
            if hoja.row_count < len(valores):
                hoja.resize(rows=len(valores) + 100)
            hoja.update(valores)
            if filas_previas > len(valores):
                hoja.batch_clear([f"A{len(valores) + 1}:AZ{filas_previas}"])
            break
        except gspread.exceptions.APIError as e:
            if intento == 2:
                # Streamlit oculta el texto de las excepciones, así que se muestra
                # aquí el motivo real que devuelve Google.
                try:
                    detalle = f"{e.response.status_code} - {e.response.text[:500]}"
                except Exception:
                    detalle = str(e)
                st.error(f"⚠️ Google Sheets rechazó el guardado. Detalle: {detalle}")
                st.stop()
            time.sleep(5 * (intento + 1))

# ===============================
# ADJUNTOS (se guardan en la hoja "Adjuntos" del mismo Google Sheet)
# ===============================
HOJA_ADJUNTOS = "Adjuntos"
CHUNK = 40_000          # caracteres por celda (límite de Sheets: 50.000)
MAX_ADJUNTO_MB = 3      # tamaño máximo por archivo

def _hoja_adjuntos():
    libro = conectar_libro()
    try:
        return libro.worksheet(HOJA_ADJUNTOS)
    except gspread.WorksheetNotFound:
        ws = libro.add_worksheet(title=HOJA_ADJUNTOS, rows=1000, cols=3)
        ws.append_row(["id", "n", "datos_base64"])
        return ws

def guardar_adjunto(nombre, datos, mime):
    """Guarda el archivo en trozos y devuelve el texto (JSON) que se anota en el registro."""
    adj_id = uuid.uuid4().hex[:10]
    b64 = base64.b64encode(datos).decode()
    trozos = [b64[i:i + CHUNK] for i in range(0, len(b64), CHUNK)]
    ws = _hoja_adjuntos()
    filas = [[adj_id, i, t] for i, t in enumerate(trozos)]
    for k in range(0, len(filas), 30):
        ws.append_rows(filas[k:k + 30], value_input_option="RAW")
    return json.dumps({"id": adj_id, "nombre": nombre, "tipo": mime or "application/octet-stream",
                       "n": len(trozos), "kb": round(len(datos) / 1024, 1)}, ensure_ascii=False)

def leer_adjunto(meta):
    ws = _hoja_adjuntos()
    pos = [i + 1 for i, v in enumerate(ws.col_values(1)) if v == meta["id"]]
    if not pos:
        raise ValueError("el adjunto ya no existe en la hoja 'Adjuntos'")
    filas = ws.get(f"A{min(pos)}:C{max(pos)}")
    trozos = sorted((int(f[1]), f[2]) for f in filas if len(f) >= 3 and f[0] == meta["id"])
    return base64.b64decode("".join(t for _, t in trozos))

# ===============================
# CONFIGURACIÓN (hoja "Config"): contador de días sin accidentes por línea
# ===============================
HOJA_CONFIG = "Config"

def _hoja_config():
    libro = conectar_libro()
    try:
        return libro.worksheet(HOJA_CONFIG)
    except gspread.WorksheetNotFound:
        ws = libro.add_worksheet(title=HOJA_CONFIG, rows=100, cols=2)
        ws.append_row(["clave", "valor"])
        return ws

@st.cache_data(ttl=120, show_spinner=False)
def leer_config():
    try:
        filas = _hoja_config().get_all_values()
    except Exception:
        return {}
    return {f[0]: f[1] for f in filas[1:] if len(f) >= 2 and f[0]}

def guardar_config(clave, valor):
    ws = _hoja_config()
    claves = ws.col_values(1)
    if clave in claves:
        ws.update_cell(claves.index(clave) + 1, 2, valor)
    else:
        ws.append_row([clave, valor], value_input_option="RAW")
    leer_config.clear()

def hoy_chile():
    try:
        return _datetime.now(ZoneInfo("America/Santiago")).date()
    except Exception:
        return date.today()

def fecha_inicio_sin_accidentes(linea):
    """Fecha desde la que se cuentan los días (se guarda como 'd:AAAA-MM-DD' para que Sheets no la convierta)."""
    v = leer_config().get(f"sin_accidentes|{linea}", "")
    try:
        return date.fromisoformat(v.replace("d:", "").strip())
    except Exception:
        return None

def _meta_adjunto(valor):
    try:
        m = json.loads(valor) if isinstance(valor, str) and valor.strip().startswith("{") else None
        return m if m and "id" in m else None
    except Exception:
        return None

def adjunto_ui(valor, clave):
    """Muestra el adjunto de un registro con botón para cargarlo y descargarlo."""
    m = _meta_adjunto(valor)
    if not m:
        return
    st.caption(f"📎 {m['nombre']} ({m['kb']} KB)")
    k = f"adjbytes_{m['id']}"
    if k in st.session_state:
        st.download_button("⬇ Descargar adjunto", st.session_state[k], file_name=m["nombre"],
                           mime=m["tipo"], key=f"dl_{clave}")
    elif st.button("📎 Cargar adjunto", key=f"ld_{clave}"):
        try:
            st.session_state[k] = leer_adjunto(m)
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo leer el adjunto: {e}")

def enviar_correo_preventivo(fecha_prev, linea, tarea, acciones_dia="", adjunto=None):
    try:
        correo_emisor = st.secrets["email"]["usuario"]
        password_correo = st.secrets["email"]["password"]
        smtp_server = st.secrets["email"].get("smtp_server", "smtp.gmail.com")
        smtp_port = int(st.secrets["email"].get("smtp_port", 587))

        # Busca los correos del mecánico y eléctrico asignados a esta línea
        # en la sección [email_recipients] de los Secrets.
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

        correo_receptor = ", ".join(lista_destinatarios)

        bloque_acciones = f"\n\nAcciones del Día / Compromisos registrados:\n{acciones_dia}" if acciones_dia else ""

        cuerpo = f"🚨 ALERTA DE MANTENCIÓN PREVENTIVA:\n\nSe ha programado una mantención para la línea {linea}.\nFecha: {fecha_prev}\nTrabajo a realizar: {tarea}{bloque_acciones}\n\nPor favor gestionar los recursos y herramientas."
        msg = MIMEMultipart()
        msg.attach(MIMEText(cuerpo))
        if adjunto:
            nombre_adj, datos_adj, mime_adj = adjunto
            t1, _, t2 = (mime_adj or "application/octet-stream").partition("/")
            parte = MIMEBase(t1, t2 or "octet-stream")
            parte.set_payload(datos_adj)
            encoders.encode_base64(parte)
            parte.add_header("Content-Disposition", "attachment", filename=("utf-8", "", nombre_adj))
            msg.attach(parte)
        msg['Subject'] = f"⚠️ Preventivo Programado - Línea {linea} ({fecha_prev})"
        msg['From'] = correo_emisor
        msg['To'] = correo_receptor

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
# SELECTOR DE LÍNEA PRODUCTIVA (BARRA LATERAL)
# ===============================
st.sidebar.header("🕹️ Navegación de Pantallas")
LINEAS_DISPONIBLES = ["LAM 1", "LAM 2", "260", "230", "190", "LAM 3", "PALETIZADO"]
linea_activa = st.sidebar.selectbox("Selecciona la Línea Productiva:", LINEAS_DISPONIBLES)

st.subheader(f"🖥️ Pantalla Actual: Área de {linea_activa}")

HOY = hoy_chile()
_clave_acc = f"sin_accidentes|{linea_activa}"
_inicio_acc = fecha_inicio_sin_accidentes(linea_activa)
if _inicio_acc:
    dias_sin_acc = max(0, (HOY - _inicio_acc).days)
else:   # contador aún sin configurar: se usa el último valor registrado
    _df_ult = df_historico[df_historico["Linea"] == linea_activa].sort_values("Fecha", kind="stable")
    dias_sin_acc = int(_df_ult["Dias_Sin_Accidentes"].iloc[-1]) if not _df_ult.empty else 0
st.metric("🛡️ Días sin accidentes", dias_sin_acc)
if _inicio_acc:
    st.caption(f"Contando desde el {_inicio_acc:%d-%m-%Y}. Se actualiza solo cada día.")
else:
    st.caption("Contador sin configurar: ábrelo aquí abajo y escribe cuántos días llevan.")

with st.expander("⚙️ Configurar contador de días sin accidentes"):
    cfg1, cfg2 = st.columns(2)
    with cfg1:
        n_dias_acc = st.number_input("Días que llevan HOY sin accidentes", min_value=0, step=1, key="cfg_dias_acc")
        if st.button("✅ Fijar contador", key="btn_fijar_acc"):
            try:
                guardar_config(_clave_acc, "d:" + (HOY - timedelta(days=int(n_dias_acc))).isoformat())
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo guardar el contador: {e}")
    with cfg2:
        conf_acc = st.checkbox("Confirmo que ocurrió un accidente", key="chk_acc")
        if st.button("🚨 Reiniciar a 0", key="btn_reset_acc", disabled=not conf_acc):
            try:
                guardar_config(_clave_acc, "d:" + HOY.isoformat())
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo reiniciar el contador: {e}")

## ===============================
# SENSOR DE ALERTAS EXCLUSIVO DE LA LÍNEA SELECCIONADA
# ===============================
col_alertas1, col_alertas2 = st.columns(2)

with col_alertas1:
    df_pendientes_linea = df_historico[(df_historico["Estado"] == "Pendiente") & (df_historico["Linea"] == linea_activa)].copy()
    if not df_pendientes_linea.empty:
        st.error(f"🚨 **RECORDATORIO PENDIENTES: {linea_activa}**")
        for idx, row in df_pendientes_linea.iterrows():
            # ESTA ES LA LÍNEA CLAVE: Verifica que la celda de la fecha no venga vacía o corrupta
            if pd.notna(row['Fecha']):
                f_str = pd.to_datetime(row['Fecha']).strftime('%Y-%m-%d')
                st.warning(f"⏳ **Turno {f_str}:** {row['Acciones_Dia']}")
            else:
                st.warning(f"⏳ **Turno sin fecha registrada:** {row['Acciones_Dia']}")

with col_alertas2:
    df_historico["Preventivo_Fecha"] = pd.to_datetime(df_historico["Preventivo_Fecha"], errors="coerce")
    hoy = pd.to_datetime(date.today())
    dentro_de_una_semana = hoy + timedelta(days=7)

    df_prev_linea = df_historico[
        (df_historico["Preventivo_Fecha"] >= hoy) &
        (df_historico["Preventivo_Fecha"] <= dentro_de_una_semana) &
        (df_historico["Preventivo_Tarea"].fillna("") != "") &
        (df_historico["Linea"] == linea_activa)
    ].copy()

    st.info(f"📅 **MANTENCIONES PREVENTIVAS DE LA SEMANA: {linea_activa}**")
    if not df_prev_linea.empty:
        for idx, row in df_prev_linea.iterrows():
            # PROTECCIÓN EXTRA: También aseguramos las fechas de las tareas preventivas de la semana
            if pd.notna(row['Preventivo_Fecha']):
                p_f_str = row['Preventivo_Fecha'].strftime('%Y-%m-%d')
                st.success(f"🔧 **[{p_f_str}]:** {row['Preventivo_Tarea']}")
            else:
                st.success(f"🔧 **[Fecha indefinida]:** {row['Preventivo_Tarea']}")
            adjunto_ui(row.get("Preventivo_Adjunto", ""), f"sem_{idx}")
    else:
        st.write("✅ No hay trabajos preventivos agendados para esta semana.")

# ===============================
# FORMULARIO DE INGRESO
# ===============================
with st.expander(f"📝 Registrar Nueva Reunión / Turno para {linea_activa}", expanded=True):
    with st.form("form_planificacion", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.markdown("### 📋 Bitácora General")
            fecha = st.date_input("Fecha de la Reunión", date.today())
            acciones = st.text_area("Acciones del Día / Compromisos")
            mejoras = st.text_area("Formulario de Mejoras / Ideas")
            estado_inicial = st.selectbox("Estado de las Acciones", ["Pendiente", "Listo"])

            st.markdown("---")
            st.markdown("### ⚡ Especialidades Técnicas")
            tareas_elec = st.text_area("Tareas Eléctricas Ejecutadas")
            tareas_meca = st.text_area("Tareas Mecánicas Ejecutadas")

        with c2:
            st.markdown("### ⚙️ Órdenes e Indicadores")
            num_averias = st.number_input("Número de Averías Reportadas", min_value=0, step=1)
            avisos_creados = st.number_input("Avisos SAP/Sistema Creados", min_value=0, step=1)
            om_creadas = st.number_input("Órdenes de Mantención (OM) Ejecutadas/Guardadas", min_value=0, step=1)

            st.markdown("---")
            st.markdown("### 🔴 Gestión de Tarjetas")
            t_rojas = st.number_input("Tarjetas Rojas", min_value=0, step=1)
            t_verdes = st.number_input("Tarjetas Verdes", min_value=0, step=1)
            t_azules = st.number_input("Tarjetas Azules", min_value=0, step=1)

            st.markdown("---")
            st.markdown("### 📈 Eficiencia")
            eficiencia_dia = st.number_input("Eficiencia del Día (%)", min_value=0, max_value=100, step=1, key="eficiencia_dia")

        with c3:
            st.markdown("### 💧 Módulo Lubricación y TPM MA")
            lub_planeados_ma = st.number_input("Puntos de Lubricación Planeados (MA)", min_value=0, step=1, key="lub_plan_ma")
            lub_ejecutados_ma = st.number_input("Puntos de Lubricación Ejecutados (MA)", min_value=0, step=1, key="lub_ejec_ma")
            tpm_inspeccion_ma = st.number_input("Anomalías Detectadas (MA)", min_value=0, step=1, key="tpm_insp_ma")
            observaciones_ma = st.text_area("Observaciones Detectadas (MA)", key="obs_ma")

        with c4:
            st.markdown("### 💧 Módulo Lubricación y TPM MP")
            lub_planeados_mp = st.number_input("Puntos de Lubricación Planeados (MP)", min_value=0, step=1, key="lub_plan_mp")
            lub_ejecutados_mp = st.number_input("Puntos de Lubricación Ejecutados (MP)", min_value=0, step=1, key="lub_ejec_mp")
            tpm_inspeccion_mp = st.number_input("Anomalías Detectadas (MP)", min_value=0, step=1, key="tpm_insp_mp")
            observaciones_mp = st.text_area("Observaciones Detectadas (MP)", key="obs_mp")

        st.markdown("---")
        st.markdown("### 🛡️ Seguridad, ACR y Confiabilidad")
        s1, s2 = st.columns(2)
        with s1:
            dias_sin_acc_in = dias_sin_acc   # automático: viene del contador
            st.metric("Días sin accidentes (automático)", dias_sin_acc)
            acr_solicitado = st.number_input("ACR solicitado", min_value=0, step=1)
            acr_ejecutado = st.number_input("ACR ejecutado", min_value=0, step=1)
        with s2:
            mttr_in = st.number_input("MTTR (min)", min_value=0.0, step=0.5, format="%.1f")
            mtbf_in = st.number_input("MTBF (h)", min_value=0.0, step=0.5, format="%.1f")
            disp_in = st.number_input(
                "Disponibilidad (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.1f",
                help="Referencia: Disponibilidad = MTBF / (MTBF + MTTR en horas) × 100")

        st.markdown("---")
        st.markdown("### 📅 Alerta de Preventivo Técnico")
        col_prev1, col_prev2, col_prev3 = st.columns(3)
        with col_prev1:
            prev_fecha = st.date_input("Fecha Mantención Preventiva", date.today())
        with col_prev2:
            prev_tarea = st.text_input("Trabajo Preventivo a Realizar")
            prev_adjunto = st.file_uploader(
                f"📎 Adjuntar documento (cualquier tipo, máx. {MAX_ADJUNTO_MB} MB)", key="prev_adjunto")
        with col_prev3:
            st.write("")
            enviar_mail = st.checkbox("Enviar alerta por correo al guardar")

        st.write("")
        boton_enviar = st.form_submit_button("💾 Guardar Datos del Turno")

if boton_enviar:
    adjunto_meta, adjunto_mail = "", None
    if prev_adjunto is not None:
        datos_adj = prev_adjunto.getvalue()
        if len(datos_adj) > MAX_ADJUNTO_MB * 1024 * 1024:
            st.warning(f"📎 '{prev_adjunto.name}' supera {MAX_ADJUNTO_MB} MB: el registro se guardará sin adjunto.")
        else:
            adjunto_mail = (prev_adjunto.name, datos_adj, prev_adjunto.type)
            try:
                adjunto_meta = guardar_adjunto(prev_adjunto.name, datos_adj, prev_adjunto.type)
            except Exception as e:
                st.warning(f"📎 No se pudo guardar el adjunto ({e}); el registro se guardará sin él.")

    if enviar_mail and prev_tarea:
        exito_mail = enviar_correo_preventivo(prev_fecha.strftime('%Y-%m-%d'), linea_activa, prev_tarea, acciones, adjunto_mail)
        if exito_mail:
            st.success("📩 Alerta de correo enviada correctamente.")
        else:
            st.warning(f"⚠️ No se envió por mail ({st.session_state.get('ultimo_error_mail', 'error desconocido')}), pero el registro se guardará.")

    nueva_fila = {
        "Fecha": pd.to_datetime(fecha),
        "Linea": linea_activa,
        "Acciones_Dia": acciones,
        "Tareas_Electricas": tareas_elec,
        "Tareas_Mecanicas": tareas_meca,
        "Formulario_Mejoras": mejoras,
        "Estado": estado_inicial,
        "Tarjetas_Rojas": t_rojas,
        "Tarjetas_Verdes": t_verdes,
        "Tarjetas_Azules": t_azules,
        "Avisos_Creados": avisos_creados,
        "OM_Creadas": om_creadas,
        "Numero_Averias": num_averias,
        "Lub_Planeados_MA": lub_planeados_ma,
        "Lub_Ejecutados_MA": lub_ejecutados_ma,
        "TPM_Inspeccion_MA": tpm_inspeccion_ma,
        "Observaciones_MA": observaciones_ma,
        "Lub_Planeados_MP": lub_planeados_mp,
        "Lub_Ejecutados_MP": lub_ejecutados_mp,
        "TPM_Inspeccion_MP": tpm_inspeccion_mp,
        "Observaciones_MP": observaciones_mp,
        "Preventivo_Fecha": str(prev_fecha),
        "Preventivo_Tarea": prev_tarea,
        # Si la tarea ya nace "Lista", se cierra el mismo día (0 días de demora).
        # Si nace "Pendiente", queda sin fecha de cierre hasta que se marque Lista.
        "Fecha_Cierre": str(fecha) if estado_inicial == "Listo" else "",
        "Eficiencia_Diaria": eficiencia_dia,
        "Dias_Sin_Accidentes": dias_sin_acc_in,
        "ACR_Solicitado": acr_solicitado,
        "ACR_Ejecutado": acr_ejecutado,
        "MTTR_min": mttr_in,
        "MTBF_h": mtbf_in,
        "Disponibilidad_pct": disp_in,
        "Preventivo_Adjunto": adjunto_meta
    }

    df_historico = pd.concat([df_historico, pd.DataFrame([nueva_fila])], ignore_index=True)
    guardar_datos(df_historico)
    st.success("✅ ¡Datos guardados exitosamente!")
    st.rerun()

# Filtrar datos de la tabla para la línea en pantalla
df_linea = df_historico[df_historico["Linea"] == linea_activa].copy()

# ===============================
# SECCIÓN: REVISAR UN DÍA EN ESPECÍFICO (DETALLE)
# ===============================
st.divider()
st.header("🔍 Consultar Detalle de un Día Específico")

def etiqueta_registro(i):
    fila = df_linea.loc[i]
    texto = str(fila["Acciones_Dia"]).replace("\n", " ")
    if len(texto) > 90:
        texto = texto[:90] + "…"
    return f"{fila['Fecha_Str']} — {texto}"

if not df_linea.empty:
    df_linea["Fecha_Str"] = df_linea["Fecha"].dt.strftime("%Y-%m-%d")
    registros_disponibles = list(df_linea.sort_values("Fecha", ascending=False).index)
    registro_consulta = st.selectbox(
        "Selecciona la tarea que deseas auditar:",
        registros_disponibles,
        format_func=etiqueta_registro,
        key="registro_consulta"
    )

    if registro_consulta is not None:
        registro_dia = df_linea.loc[registro_consulta]

        det1, det2, det3 = st.columns(3)
        with det1:
            st.info(f"📋 **Acciones/Compromisos:**\n{registro_dia['Acciones_Dia']}")
            st.info(f"⚡ **Tareas Eléctricas:**\n{registro_dia['Tareas_Electricas']}")
            st.info(f"⚙️ **Tareas Mecánicas:**\n{registro_dia['Tareas_Mecanicas']}")
        with det2:
            st.metric("Estado de la Reunión", registro_dia['Estado'])
            st.metric("💥 Número de Averías", int(registro_dia['Numero_Averias']))
            st.metric("📨 Avisos Generados", int(registro_dia['Avisos_Creados']))
            st.metric("⚙️ Órdenes de Mantención (OM)", int(registro_dia['OM_Creadas']))
            st.metric("📈 Eficiencia del Día", f"{int(registro_dia['Eficiencia_Diaria'])}%")
            if pd.notna(registro_dia['Fecha_Cierre']):
                dias_demora = (registro_dia['Fecha_Cierre'] - registro_dia['Fecha']).days
                st.metric("⏱️ Demora en Ejecutarla", f"{dias_demora} día(s)")
            else:
                st.metric("⏱️ Demora en Ejecutarla", "Aún pendiente")
        with det3:
            st.info(f"💡 **Ideas de Mejora:**\n{registro_dia['Formulario_Mejoras']}")
            st.metric("💧 Lubricación MA (Ejecutados / Planeados)", f"{int(registro_dia['Lub_Ejecutados_MA'])} / {int(registro_dia['Lub_Planeados_MA'])}")
            st.metric("💧 Lubricación MP (Ejecutados / Planeados)", f"{int(registro_dia['Lub_Ejecutados_MP'])} / {int(registro_dia['Lub_Planeados_MP'])}")
            st.write(f"📝 **Observaciones MA:** {registro_dia['Observaciones_MA']}")
            st.write(f"📝 **Observaciones MP:** {registro_dia['Observaciones_MP']}")
            st.write(f"📅 **Próximo Preventivo:** {registro_dia['Preventivo_Fecha']}")
            st.write(f"🔧 **Tarea:** {registro_dia['Preventivo_Tarea']}")
            adjunto_ui(registro_dia["Preventivo_Adjunto"], f"det_{registro_consulta}")
            st.write(f"🛡️ **Días sin accidentes:** {int(registro_dia['Dias_Sin_Accidentes'])}")
            st.write(f"🔎 **ACR solicitado / ejecutado:** {int(registro_dia['ACR_Solicitado'])} / {int(registro_dia['ACR_Ejecutado'])}")
            st.write(f"📉 **MTTR:** {registro_dia['MTTR_min']:.1f} min · **MTBF:** {registro_dia['MTBF_h']:.1f} h · **Disponibilidad:** {registro_dia['Disponibilidad_pct']:.1f} %")
else:
    st.info("No hay registros disponibles en esta línea.")

# ===============================
# EDICIÓN / CUMPLIMIENTO HISTÓRICO
# ===============================
st.divider()
st.subheader(f"🔄 Gestión de Compromisos y Cumplimiento: {linea_activa}")

if not df_linea.empty:
    df_solo_pendientes = df_linea[df_linea["Estado"] == "Pendiente"]

    if not df_solo_pendientes.empty:
        st.info("💡 Selecciona una tarea pendiente para marcarla como completada (Listo). Cada tarea se cierra por separado.")
        col_act1, col_act2, col_act3 = st.columns([4, 2, 1])

        with col_act1:
            registro_a_cambiar = st.selectbox(
                "Tareas PENDIENTES:",
                list(df_solo_pendientes.index),
                format_func=etiqueta_registro,
                key="registro_pendiente_cambio"
            )

        with col_act2:
            nuevo_estado = st.selectbox("Cambiar estado de la actividad a:", ["Listo", "Pendiente"], key="estado_pendiente_cambio")

        with col_act3:
            st.write("")
            st.write("")
            if st.button("⚡ Ejecutar y Cerrar Tarea"):
                df_historico.loc[registro_a_cambiar, "Estado"] = nuevo_estado
                if nuevo_estado == "Listo":
                    # Se registra la fecha de hoy como cierre, para medir cuánto demoró.
                    df_historico.loc[registro_a_cambiar, "Fecha_Cierre"] = pd.to_datetime(date.today())
                else:
                    # Si se reabre como Pendiente, se borra la fecha de cierre previa.
                    df_historico.loc[registro_a_cambiar, "Fecha_Cierre"] = pd.NaT
                guardar_datos(df_historico)

                st.success("✅ ¡Tarea actualizada con éxito!")
                st.rerun()
    else:
        st.success(f"🎉 ¡Felicidades! No quedan actividades pendientes por ejecutar en la línea {linea_activa}.")
else:
    st.info("No hay registros en el historial para modificar.")

# ===============================
# ELIMINAR REGISTRO
# ===============================
st.divider()
st.subheader(f"🗑️ Eliminar un Registro: {linea_activa}")

if not df_linea.empty:
    registros_para_borrar = list(df_linea.sort_values("Fecha", ascending=False).index)

    col_del1, col_del2 = st.columns([3, 1])
    with col_del1:
        registro_a_borrar = st.selectbox(
            "Selecciona el registro a eliminar (⚠️ acción irreversible):",
            registros_para_borrar,
            format_func=etiqueta_registro,
            key="registro_borrar"
        )
    with col_del2:
        st.write("")
        st.write("")
        confirmar_borrado = st.checkbox("Confirmar", key="check_borrar")

    if st.button("🗑️ Eliminar registro seleccionado", disabled=not confirmar_borrado):
        df_historico = df_historico.drop(index=[registro_a_borrar]).reset_index(drop=True)
        guardar_datos(df_historico)

        st.success("🗑️ Registro eliminado correctamente.")
        st.rerun()
else:
    st.info("No hay registros para eliminar en esta línea.")

# ===============================
# GRÁFICOS
# ===============================
st.divider()
st.header(f"📊 Gráficos: {linea_activa}")

if not df_linea.empty:
    df_grafico = df_linea.sort_values("Fecha").copy()
    df_grafico["Fecha_Str"] = df_grafico["Fecha"].dt.strftime("%Y-%m-%d")
    df_grafico_indexado = df_grafico.set_index("Fecha_Str")

    g1, g2 = st.columns(2)

    with g1:
        st.markdown("**🔴 Tarjetas por fecha (Rojas / Verdes / Azules)**")
        st.bar_chart(df_grafico_indexado[["Tarjetas_Rojas", "Tarjetas_Verdes", "Tarjetas_Azules"]],
                     color=[COLOR_ROJO, COLOR_VERDE, COLOR_AZUL])

        st.markdown("**💥 Averías vs Avisos vs OM**")
        st.line_chart(df_grafico_indexado[["Numero_Averias", "Avisos_Creados", "OM_Creadas"]])

        st.markdown("**📈 Eficiencia Diaria (%)**")
        st.line_chart(df_grafico_indexado[["Eficiencia_Diaria"]])

    with g2:
        st.markdown("**💧 Cumplimiento de Lubricación MA (Ejecutados vs Planeados)**")
        st.bar_chart(df_grafico_indexado[["Lub_Planeados_MA", "Lub_Ejecutados_MA"]])

        st.markdown("**💧 Cumplimiento de Lubricación MP (Ejecutados vs Planeados)**")
        st.bar_chart(df_grafico_indexado[["Lub_Planeados_MP", "Lub_Ejecutados_MP"]])

        st.markdown("**⚙️ TPM: Anomalías Detectadas (MA vs MP)**")
        st.line_chart(df_grafico_indexado[["TPM_Inspeccion_MA", "TPM_Inspeccion_MP"]])

        st.markdown("**⏱️ Demora en Ejecutar Tareas (días entre registro y cierre)**")
        df_demora = df_grafico[df_grafico["Fecha_Cierre"].notna()].copy()
        if not df_demora.empty:
            df_demora["Dias_Demora"] = (df_demora["Fecha_Cierre"] - df_demora["Fecha"]).dt.days
            df_demora_indexado = df_demora.set_index("Fecha_Str")
            st.bar_chart(df_demora_indexado[["Dias_Demora"]])
        else:
            st.write("✅ Aún no hay tareas cerradas para calcular demora.")

    # ----- Seguridad, ACR y confiabilidad -----
    st.markdown("---")
    st.subheader("🛡️ Seguridad, ACR y Confiabilidad")
    df_n = df_grafico.groupby("Fecha_Str").last()

    def _serie(col, titulo, color, tope_100=False):
        st.markdown(titulo)
        d = df_n[df_n[col] > 0][[col]]
        if d.empty:
            st.caption("Aún no hay datos ingresados.")
        elif tope_100:
            graf = alt.Chart(d.reset_index()).mark_area(
                color=color, opacity=0.3, line={"color": color}, point={"color": color}
            ).encode(
                x=alt.X("Fecha_Str:N", title="Fecha"),
                y=alt.Y(f"{col}:Q", scale=alt.Scale(domain=[0, 100]), title="%"),
            )
            st.altair_chart(graf)
        else:
            st.line_chart(d, color=color)

    n1, n2 = st.columns(2)
    with n1:
        st.markdown("**🛡️ Días sin accidentes**")
        st.line_chart(df_n[["Dias_Sin_Accidentes"]], color=COLOR_VERDE)
        st.markdown("**🔎 ACR solicitado vs ejecutado**")
        st.bar_chart(df_n[["ACR_Solicitado", "ACR_Ejecutado"]], color=[COLOR_DORADO, COLOR_ACR_EJEC], stack=False)
    with n2:
        _serie("MTTR_min", "**🛠️ MTTR (min)**", "#E67E22")
        _serie("MTBF_h", "**🔁 MTBF (h)**", COLOR_AZUL)
        _serie("Disponibilidad_pct", "**✅ Disponibilidad (%)**", COLOR_VERDE, tope_100=True)
else:
    st.info("No hay suficientes datos para graficar en esta línea todavía.")



