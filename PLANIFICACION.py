import streamlit as st
import pandas as pd
import os
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

st.title("🏭 Sistema Integrado de Planificación y TPM")
st.markdown("Control de Avisos, OM, Especialidades, Lubricación y Gestión de Pendientes por Línea.")

# ===============================
# CONEXIÓN A GOOGLE SHEETS (base de datos persistente)
# ===============================
COLUMNAS_REQUERIDAS = [
    "Fecha", "Linea", "Acciones_Dia", "Tareas_Electricas", "Tareas_Mecanicas",
    "Formulario_Mejoras", "Estado", "Tarjetas_Rojas", "Tarjetas_Verdes", "Tarjetas_Azules",
    "Avisos_Creados", "OM_Creadas", "Numero_Averias",
    "Lub_Planeados", "Lub_Ejecutados", "TPM_Limpieza", "TPM_Inspeccion",
    "Preventivo_Fecha", "Preventivo_Tarea"
]

@st.cache_resource
def conectar_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
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
        # Hoja vacía: la inicializamos con dos filas de ejemplo
        df_inicial = pd.DataFrame([{
            "Fecha": str(date.today()), "Linea": "PALETIZADO",
            "Acciones_Dia": "Sistema inicializado correctamente.", "Tareas_Electricas": "Revisión inicial", "Tareas_Mecanicas": "Inspección de polines",
            "Formulario_Mejoras": "", "Estado": "Listo", "Tarjetas_Rojas": 0, "Tarjetas_Verdes": 0, "Tarjetas_Azules": 0,
            "Avisos_Creados": 0, "OM_Creadas": 0, "Numero_Averias": 0, "Lub_Planeados": 0, "Lub_Ejecutados": 0,
            "TPM_Limpieza": 0, "TPM_Inspeccion": 0, "Preventivo_Fecha": str(date.today()), "Preventivo_Tarea": ""
        }, {
            "Fecha": str(date.today()), "Linea": "LAM 3",
            "Acciones_Dia": "Sistema inicializado correctamente.", "Tareas_Electricas": "Revisión inicial", "Tareas_Mecanicas": "Inspección de cadenas",
            "Formulario_Mejoras": "", "Estado": "Listo", "Tarjetas_Rojas": 0, "Tarjetas_Verdes": 0, "Tarjetas_Azules": 0,
            "Avisos_Creados": 0, "OM_Creadas": 0, "Numero_Averias": 0, "Lub_Planeados": 0, "Lub_Ejecutados": 0,
            "TPM_Limpieza": 0, "TPM_Inspeccion": 0, "Preventivo_Fecha": str(date.today()), "Preventivo_Tarea": ""
        }])
        df_inicial["Fecha"] = pd.to_datetime(df_inicial["Fecha"]
        guardar_datos(df_inicial)
        return df_inicial

    df = pd.DataFrame(registros)
    for col in COLUMNAS_REQUERIDAS:
        if col not in df.columns:
            df[col] = 0 if any(x in col for x in ["Tarjetas", "Avisos", "OM", "Numero", "Lub", "TPM"]) else ""
    df = df[COLUMNAS_REQUERIDAS]
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df

def guardar_datos(df):
    hoja = conectar_sheet()
    df_guardar = df.copy()
    df_guardar["Fecha"] = df_guardar["Fecha"].astype(str)
    hoja.clear()
    hoja.update([df_guardar.columns.values.tolist()] + df_guardar.values.tolist())

def enviar_correo_preventivo(fecha_prev, linea, tarea):
    try:
        correo_emisor = st.secrets["email"]["usuario"]
        correo_receptor = st.secrets["email"]["receptor"]
        password_correo = st.secrets["email"]["password"]
        smtp_server = st.secrets["email"].get("smtp_server", "smtp.gmail.com")
        smtp_port = int(st.secrets["email"].get("smtp_port", 587))

        msg = MIMEText(f"🚨 ALERTA DE MANTENCIÓN PREVENTIVA:\n\nSe ha programado una mantención para la línea {linea}.\nFecha: {fecha_prev}\nTrabajo a realizar: {tarea}\n\nPor favor gestionar los recursos y herramientas.")
        msg['Subject'] = f"⚠️ Preventivo Programado - Línea {linea} ({fecha_prev})"
        msg['From'] = correo_emisor
        msg['To'] = correo_receptor

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(correo_emisor, password_correo)
        server.sendmail(correo_emisor, correo_receptor, msg.as_string())
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
linea_activa = st.sidebar.selectbox("Selecciona la Línea Productiva:", ["PALETIZADO", "LAM 3"])

st.subheader(f"🖥️ Pantalla Actual: Área de {linea_activa}")

# ===============================
# SENSOR DE ALERTAS EXCLUSIVO DE LA LÍNEA SELECCIONADA
# ===============================
col_alertas1, col_alertas2 = st.columns(2)

with col_alertas1:
    df_pendientes_linea = df_historico[(df_historico["Estado"] == "Pendiente") & (df_historico["Linea"] == linea_activa)].copy()
    if not df_pendientes_linea.empty:
        st.error(f"🚨 **RECORDATORIO PENDIENTES: {linea_activa}**")
        for idx, row in df_pendientes_linea.iterrows():
            f_str = pd.to_datetime(row['Fecha']).strftime('%Y-%m-%d')
            st.warning(f"⏳ **Turno {f_str}:** {row['Acciones_Dia']}")

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
            p_f_str = row['Preventivo_Fecha'].strftime('%Y-%m-%d')
            st.success(f"🔧 **[{p_f_str}]:** {row['Preventivo_Tarea']}")
    else:
        st.write("✅ No hay trabajos preventivos agendados para esta semana.")

# ===============================
# FORMULARIO DE INGRESO
# ===============================
with st.expander(f"📝 Registrar Nueva Reunión / Turno para {linea_activa}", expanded=True):
    with st.form("form_planificacion", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)

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

        with c3:
            st.markdown("### 💧 Módulo Lubricación y TPM")
            lub_planeados = st.number_input("Puntos de Lubricación Planeados", min_value=0, step=1)
            lub_ejecutados = st.number_input("Puntos de Lubricación Ejecutados", min_value=0, step=1)
            tpm_limpieza = st.number_input("Inspecciones de Limpieza", min_value=0, step=1)
            tpm_inspeccion = st.number_input("Anomalías Detectadas", min_value=0, step=1)

            st.markdown("---")
            st.markdown("### 📅 Alerta de Preventivo Técnico")
            prev_fecha = st.date_input("Fecha Mantención Preventiva", date.today())
            prev_tarea = st.text_input("Trabajo Preventivo a Realizar")
            enviar_mail = st.checkbox("Enviar alerta por correo al guardar")

        st.write("")
        boton_enviar = st.form_submit_button("💾 Guardar Datos del Turno")

if boton_enviar:
    if enviar_mail and prev_tarea:
        exito_mail = enviar_correo_preventivo(prev_fecha.strftime('%Y-%m-%d'), linea_activa, prev_tarea)
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
        "Lub_Planeados": lub_planeados,
        "Lub_Ejecutados": lub_ejecutados,
        "TPM_Limpieza": tpm_limpieza,
        "TPM_Inspeccion": tpm_inspeccion,
        "Preventivo_Fecha": str(prev_fecha),
        "Preventivo_Tarea": prev_tarea
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
if not df_linea.empty:
    df_linea["Fecha_Str"] = df_linea["Fecha"].dt.strftime("%Y-%m-%d")
    fechas_disponibles = sorted(df_linea["Fecha_Str"].unique(), reverse=True)
    fecha_consulta = st.selectbox("Selecciona la fecha que deseas auditar:", fechas_disponibles)

    fila_seleccionada = df_linea[df_linea["Fecha_Str"] == fecha_consulta]

    if not fila_seleccionada.empty:
        registro_dia = fila_seleccionada.iloc[0]  # Corrección de extracción de fila limpia

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
        with det3:
            st.info(f"💡 **Ideas de Mejora:**\n{registro_dia['Formulario_Mejoras']}")
            st.metric("💧 Puntos Lubricación (Ejecutados / Planeados)", f"{int(registro_dia['Lub_Ejecutados'])} / {int(registro_dia['Lub_Planeados'])}")
            st.write(f"📅 **Próximo Preventivo:** {registro_dia['Preventivo_Fecha']}")
            st.write(f"🔧 **Tarea:** {registro_dia['Preventivo_Tarea']}")
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
        fechas_pendientes = df_solo_pendientes["Fecha_Str"].unique()

        st.info("💡 Selecciona una reunión antigua para marcar sus compromisos como completados (Listo).")
        col_act1, col_act2, col_act3 = st.columns([2, 2, 1])

        with col_act1:
            fecha_a_cambiar = st.selectbox("Reuniones con tareas PENDIENTES:", fechas_pendientes, key="fecha_pendiente_cambio")

        with col_act2:
            nuevo_estado = st.selectbox("Cambiar estado de la actividad a:", ["Listo", "Pendiente"], key="estado_pendiente_cambio")

        with col_act3:
            st.write("")
            st.write("")
            if st.button("⚡ Ejecutar y Cerrar Tarea"):
                indice_registro = df_historico[
                    (df_historico["Fecha"].dt.strftime("%Y-%m-%d") == fecha_a_cambiar) &
                    (df_historico["Linea"] == linea_activa)
                ].index

                df_historico.loc[indice_registro, "Estado"] = nuevo_estado
                guardar_datos(df_historico)

                st.success(f"✅ ¡Compromiso del {fecha_a_cambiar} actualizado a '{nuevo_estado}' con éxito!")
                st.rerun()
    else:
        st.success(f"🎉 ¡Felicidades! No quedan actividades pendientes por ejecutar en la línea {linea_activa}.")
else:
    st.info("No hay registros en el historial para modificar.")
