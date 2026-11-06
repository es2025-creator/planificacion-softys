"""
sap_import.py  -  Módulo para cargar en la pizarra el listado de órdenes
exportado desde SAP (IW38, disposición PIZARRA, "Texto con tabuladores").

Uso en PLANIFICACION.py:
    from sap_import import mostrar_modulo_sap, estado_de_sp
    ...
    mostrar_modulo_sap()          # pestañas OM (IW38) y SP (ME5A)
    estado_de_sp("15898993")      # en el formulario: estado de la SP anotada
"""

import io
from datetime import date

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# CONFIGURACIÓN (ajustable sin tocar el resto del código)
# ---------------------------------------------------------------------------

# Tramo de la ubicación técnica  ->  nombre de línea en la pizarra.
# La ubicación viene así: 1101-LCON-LAM1-CO-SME-0006  -> se toma "LAM1".
MAPA_LINEAS = {
    "LAM1": "LAM 1",
    "LAM2": "LAM 2",
    "LAM3": "LAM 3",
    "L260": "260",
    "L230": "230",
    "L190": "190",
    "PALE": "PALETIZADO",   # ajustar al código real de paletizado
}

# Solo se consideran las órdenes cuya ubicación técnica empieza así
# (1101 = Puente Alto, LCON = Conversión). Para incluir más áreas, agrégalas a la tupla.
UBICACIONES_INCLUIDAS = ("1101-LCON",)

# Nombres de columna de SAP -> nombres internos
COLUMNAS = {
    "Aviso": "aviso",
    "Orden": "orden",
    "Status del sistema": "status",
    "Texto breve": "texto",
    "Inic.extr.": "inicio",
    "Cl.": "clase",
    "Ubicación técnica": "ubicacion",
    "Res/SPed": "res_sped",
    "Equipo": "equipo",
    "Fin extr.": "fin",
    "PtoTrbRes": "puesto",
}

# Significado de los status de sistema más comunes
STATUS_TEXTO = {
    "ABIE": "Abierta",
    "LIB.": "Liberada",
    "NOTI": "Notif. parcial",
    "NOTO": "Notificada",
    "CTEC": "Cerrada técnicamente",
    "CERR": "Cerrada",
}


# ---------------------------------------------------------------------------
# LECTURA DEL ARCHIVO
# ---------------------------------------------------------------------------

def leer_export_sap(archivo) -> pd.DataFrame:
    """Lee el .txt exportado de IW38 y devuelve un DataFrame limpio."""
    crudo = _bytes(archivo)

    # SAP exporta en Windows-1252 (por eso las tildes salen raras en otros lados)
    for cod in ("utf-8", "cp1252", "latin-1"):
        try:
            texto = crudo.decode(cod)
            break
        except UnicodeDecodeError:
            continue

    lineas = texto.splitlines()

    # Buscar la fila de títulos (la que tiene "Orden" entre tabuladores)
    idx = next(i for i, l in enumerate(lineas) if "\tOrden\t" in l)
    cuerpo = "\n".join(l for l in lineas[idx:] if l.strip())

    df = pd.read_csv(io.StringIO(cuerpo), sep="\t", dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    df = df.drop(columns=[c for c in df.columns if c == "" or c.startswith("Unnamed")])
    df = df.rename(columns=lambda c: _columna_interna(c))
    df = df[[c for c in COLUMNAS.values() if c in df.columns]]

    for c in df.columns:
        df[c] = df[c].str.strip()

    df = df[df["orden"] != ""]
    total = len(df)
    if UBICACIONES_INCLUIDAS:
        df = df[df["ubicacion"].str.startswith(UBICACIONES_INCLUIDAS)]
    excluidas = total - len(df)

    for c in ("inicio", "fin"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], format="%d.%m.%Y", errors="coerce").dt.date

    df["linea"] = df["ubicacion"].apply(linea_desde_ubicacion)
    df["estado"] = df["status"].apply(estado_principal)
    df["cerrada"] = df["status"].str.contains(r"\bCTEC\b|\bCERR\b", regex=True)
    hoy = date.today()
    df["atrasada"] = (~df["cerrada"]) & df["fin"].notna() & (df["fin"] < hoy)
    df = df.reset_index(drop=True)
    df.attrs["excluidas"] = excluidas
    return df


def _bytes(archivo) -> bytes:
    if isinstance(archivo, (bytes, bytearray)):
        return bytes(archivo)
    if hasattr(archivo, "getvalue"):
        return archivo.getvalue()
    if hasattr(archivo, "read"):
        return archivo.read()
    with open(archivo, "rb") as f:
        return f.read()


def _clave(texto: str) -> str:
    """Quita tildes y caracteres raros para comparar nombres de columna."""
    import unicodedata
    t = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in t if ch.isascii() and ch.isalnum()).lower()


def _columna_interna(nombre: str, mapa: dict = None) -> str:
    mapa = mapa or COLUMNAS
    k = _clave(nombre)
    for sap, interna in mapa.items():
        ks = _clave(sap)
        if k == ks or (len(k) == len(ks) and all(a == b or not b.isascii() for a, b in zip(nombre, sap))):
            return interna
    # tolerancia a tildes perdidas ("Ubicaci?n t?cnica")
    for sap, interna in mapa.items():
        a, b = nombre.lower(), sap.lower()
        if len(a) >= 8 and len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= 2:
            return interna
    return nombre


def linea_desde_ubicacion(ubic: str) -> str:
    partes = (ubic or "").split("-")
    if len(partes) >= 3:
        cod = partes[2]
        if cod in MAPA_LINEAS:
            return MAPA_LINEAS[cod]
        if cod.startswith("LAM") and cod[3:].isdigit():      # LAM4 -> LAM 4
            return f"LAM {cod[3:]}"
        if cod.startswith("L") and cod[1:].isdigit():        # L180 -> 180
            return cod[1:]
        return f"Otra ({partes[1]}-{cod})"
    if len(partes) == 2:
        return f"Otra ({partes[1]})"
    return "Sin ubicación"


def estado_principal(status: str) -> str:
    codigos = (status or "").split()
    for clave in ("CERR", "CTEC", "NOTO", "NOTI", "LIB.", "ABIE"):
        if clave in codigos:
            return STATUS_TEXTO[clave]
    return codigos[0] if codigos else ""


def buscar_orden(df: pd.DataFrame, numero: str):
    """Devuelve la fila de una OM/OT (o de su aviso) o None."""
    numero = str(numero).strip()
    fila = df[(df["orden"] == numero) | (df["aviso"] == numero)]
    return None if fila.empty else fila.iloc[0]


# ---------------------------------------------------------------------------
# SECCIÓN STREAMLIT
# ---------------------------------------------------------------------------

def _subida_nueva(tipo: str, archivo) -> bool:
    """True solo la primera vez que se procesa este archivo (evita guardarlo en cada recarga)."""
    firma = (archivo.name, archivo.size)
    if st.session_state.get(f"_subido_{tipo}") == firma:
        return False
    st.session_state[f"_subido_{tipo}"] = firma
    return True


def mostrar_modulo_sap(al_subir=None, info_carga=None):
    """Sección completa: pestañas de órdenes (IW38) y solicitudes de pedido (ME5A).
    al_subir(tipo, archivo): se llama una vez por archivo nuevo ("om" o "sp"), p. ej. para guardarlo.
    info_carga: dict {"om": "texto", "sp": "texto"} con la última carga, para mostrarlo."""
    info_carga = info_carga or {}
    tab_om, tab_sp = st.tabs(["Órdenes (IW38)", "Solicitudes de pedido (ME5A)"])
    with tab_om:
        mostrar_modulo_om(al_subir, info_carga.get("om"))
    with tab_sp:
        mostrar_modulo_sp(al_subir, info_carga.get("sp"))


def mostrar_modulo_om(al_subir=None, info=None):
    st.header("📥 Órdenes desde SAP (IW38)")
    st.caption("Exporta en SAP: IW38 → disposición PIZARRA → Lista → Guardar → "
               "Fichero → Texto con tabuladores, y súbelo aquí.")

    if info:
        st.caption(f"Última carga: {info}")
    archivo = st.file_uploader("Archivo exportado de SAP (.txt)", type=["txt", "xls"], key="up_om")
    if archivo is not None and _subida_nueva("om", archivo):
        try:
            st.session_state["sap_df"] = leer_export_sap(archivo)
            st.session_state["sap_nombre"] = archivo.name
            if al_subir:
                al_subir("om", archivo)
            _d = st.session_state["sap_df"]
            st.success(f"✅ {len(_d)} órdenes de Conversión cargadas"
                       + (f" ({_d.attrs.get('excluidas', 0)} de otras áreas se omitieron)."
                          if _d.attrs.get("excluidas") else "."))
        except StopIteration:
            st.error("No encontré la fila de títulos. ¿Exportaste con la disposición PIZARRA "
                     "y formato 'Texto con tabuladores'?")
            return

    df = st.session_state.get("sap_df")
    if df is None:
        st.info("Aún no se ha cargado ningún archivo de SAP.")
        return

    # --- Filtros ---
    c1, c2 = st.columns(2)
    lineas = sorted(df["linea"].unique())
    sel_lineas = c1.multiselect("Línea", lineas, default=lineas)
    puestos = sorted(df["puesto"].unique())
    sel_puestos = c2.multiselect("Puesto de trabajo", puestos, default=puestos)
    vista = df[df["linea"].isin(sel_lineas) & df["puesto"].isin(sel_puestos)]

    # --- Indicadores ---
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Órdenes", len(vista))
    k2.metric("Atrasadas", int(vista["atrasada"].sum()))
    k3.metric("Cerradas téc.", int(vista["cerrada"].sum()))
    k4.metric("Con notif. parcial", int(vista["status"].str.contains(r"\bNOTI\b").sum()))

    st.bar_chart(vista.groupby("linea").size().rename("Órdenes"))

    # --- Tabla ---
    mostrar = vista[["orden", "aviso", "linea", "texto", "estado", "clase",
                     "inicio", "fin", "puesto", "equipo", "atrasada"]].rename(columns={
        "orden": "OM/OT", "aviso": "Aviso", "linea": "Línea", "texto": "Texto breve",
        "estado": "Estado", "clase": "Clase", "inicio": "Inicio", "fin": "Fin",
        "puesto": "Puesto", "equipo": "Equipo", "atrasada": "Atrasada"})

    st.dataframe(
        mostrar.style.apply(
            lambda r: ["background-color: #ffd6d6"] * len(r) if r["Atrasada"] else [""] * len(r),
            axis=1),
        width="stretch", hide_index=True)

    # --- Buscador ---
    st.subheader("🔎 Buscar OM / OT / Aviso")
    num = st.text_input("Número")
    if num:
        fila = buscar_orden(df, num)
        if fila is None:
            st.warning("No está en el último archivo cargado.")
        else:
            st.success(f"**{fila['orden']}** – {fila['texto']}")
            st.write(f"Línea: **{fila['linea']}** · Estado: **{fila['estado']}** · "
                     f"Puesto: **{fila['puesto']}** · Equipo: {fila['equipo'] or '—'}")
            st.write(f"Fechas: {fila['inicio']} → {fila['fin']}"
                     + ("  ⚠️ **atrasada**" if fila["atrasada"] else ""))
            st.caption(f"Status SAP: {fila['status']}")


def ordenes_para_autocompletar():
    """Para usar en el formulario de la pizarra: devuelve el DataFrame cargado o None."""
    return st.session_state.get("sap_df")


# ===========================================================================
# SOLICITUDES DE PEDIDO (ME5A, disposición SP_PIZARRA)
# ===========================================================================

COLUMNAS_SP = {
    "S": "status_trat",
    "Sol.pedido": "sp",
    "Pos.": "pos",
    "Texto breve": "texto",
    "Mon.": "moneda",
    "Valor total": "valor",
    "Ce.": "centro",
    "Autor": "autor",
    "Fe.entrega": "fe_entrega",
    "Fe.sol.": "fe_solicitud",
    "Fe.liber.": "fe_liberacion",
    "Lib": "lib",
    "Nombre del proveedor": "proveedor",
    "Solicit.": "solicitante",
    "Fe.pedido": "fe_pedido",
    "GCp": "grupo_compras",
    "Material": "material",
    "I": "imputacion",
    "CtdSolPed": "cantidad",
}

# Status de tratamiento de la SP (columna "S")
#   N = sin tratar, A = con solicitud de oferta, B = con pedido (OC)
# Indicador de liberación (columna "Lib"): en este sistema aparecen "2" y "X".
#   Supuesto a confirmar con compras: "2" = liberada, "X" = pendiente de liberación.
LIB_LIBERADA = "2"


def _fecha(serie: pd.Series) -> pd.Series:
    """Acepta 07.06.2022 y 20220610."""
    a = pd.to_datetime(serie, format="%d.%m.%Y", errors="coerce")
    b = pd.to_datetime(serie, format="%Y%m%d", errors="coerce")
    return a.fillna(b).dt.date


def _numero(txt: str) -> float:
    txt = (txt or "").strip()
    if not txt:
        return 0.0
    if "," in txt:                      # 1.116,00
        txt = txt.replace(".", "").replace(",", ".")
    else:                               # 129.927.909
        txt = txt.replace(".", "")
    try:
        return float(txt)
    except ValueError:
        return 0.0


def semaforo_sp(fila) -> str:
    if fila["status_trat"] == "B":
        return "🔵 Con pedido (OC)"
    if fila["lib"] and fila["lib"] != LIB_LIBERADA:
        return "🔴 Por aprobar"
    if fila["status_trat"] == "A":
        return "🟡 En cotización"
    return "🟡 Aprobada, sin gestionar"


def leer_export_me5a(archivo) -> pd.DataFrame:
    crudo = _bytes(archivo)
    for cod in ("utf-8", "cp1252", "latin-1"):
        try:
            texto = crudo.decode(cod)
            break
        except UnicodeDecodeError:
            continue
    lineas = texto.splitlines()
    idx = next(i for i, l in enumerate(lineas) if "\tSol.pedido\t" in l)
    cuerpo = "\n".join(l for l in lineas[idx:] if l.strip())

    df = pd.read_csv(io.StringIO(cuerpo), sep="\t", dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns=lambda c: _columna_interna(c, COLUMNAS_SP))
    df = df.loc[:, ~df.columns.duplicated()]
    df = df[[c for c in COLUMNAS_SP.values() if c in df.columns]]
    for c in df.columns:
        df[c] = df[c].str.strip()
    df = df[df["sp"] != ""]

    for c in ("fe_entrega", "fe_solicitud", "fe_liberacion", "fe_pedido"):
        if c in df.columns:
            df[c] = _fecha(df[c])
    df["valor_num"] = df["valor"].apply(_numero)
    df["cantidad"] = df["cantidad"].apply(_numero)
    df["semaforo"] = df.apply(semaforo_sp, axis=1)
    hoy = date.today()
    df["dias_abierta"] = df["fe_solicitud"].apply(lambda d: (hoy - d).days if pd.notna(d) else None)
    return df.reset_index(drop=True)


def estado_de_sp(numero: str):
    """Para el formulario de la pizarra: estado de una SP por su número (o None).
    Si la SP tiene varias posiciones, devuelve la menos avanzada."""
    df = st.session_state.get("sp_df")
    if df is None or not numero:
        return None
    filas = df[df["sp"] == str(numero).strip()]
    if filas.empty:
        return None
    orden = ["🔴 Por aprobar", "🟡 Aprobada, sin gestionar", "🟡 En cotización", "🔵 Con pedido (OC)"]
    return min(filas["semaforo"], key=lambda s: orden.index(s) if s in orden else 99)


def mostrar_modulo_sp(al_subir=None, info=None):
    st.header("🧾 Solicitudes de pedido desde SAP (ME5A)")
    st.caption("Exporta en SAP: ME5A → centro 1101 → disposición SP_PIZARRA → Lista → "
               "Guardar → Fichero → Texto con tabuladores, y súbelo aquí.")

    if info:
        st.caption(f"Última carga: {info}")
    archivo = st.file_uploader("Archivo exportado de ME5A (.txt)", type=["txt", "xls"], key="up_sp")
    if archivo is not None and _subida_nueva("sp", archivo):
        try:
            st.session_state["sp_df"] = leer_export_me5a(archivo)
            if al_subir:
                al_subir("sp", archivo)
            st.success(f"✅ {len(st.session_state['sp_df'])} posiciones de SP cargadas.")
        except StopIteration:
            st.error("No encontré la fila de títulos (debe tener la columna 'Sol.pedido').")
            return

    df = st.session_state.get("sp_df")
    if df is None:
        st.info("Aún no se ha cargado el export de ME5A.")
        return

    c1, c2, c3 = st.columns(3)
    solicit = sorted(df["solicitante"].unique())
    sel_sol = c1.multiselect("Solicitante", solicit, default=solicit)
    sel_sem = c2.multiselect("Estado", sorted(df["semaforo"].unique()),
                             default=sorted(df["semaforo"].unique()))
    max_dias = int(df["dias_abierta"].max() or 0)
    dias = c3.slider("Abiertas hace más de (días)", 0, max(max_dias, 1), 0)
    vista = df[df["solicitante"].isin(sel_sol) & df["semaforo"].isin(sel_sem)
               & (df["dias_abierta"].fillna(0) >= dias)]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("SP (posiciones)", len(vista))
    k2.metric("🔴 Por aprobar", int((vista["semaforo"] == "🔴 Por aprobar").sum()))
    k3.metric("🔵 Con OC", int((vista["semaforo"] == "🔵 Con pedido (OC)").sum()))
    k4.metric("Más de 1 año abiertas", int((vista["dias_abierta"].fillna(0) > 365).sum()))

    st.dataframe(
        vista[["sp", "pos", "texto", "semaforo", "fe_solicitud", "fe_entrega", "fe_pedido",
               "proveedor", "solicitante", "cantidad", "dias_abierta"]].rename(columns={
            "sp": "SP", "pos": "Pos.", "texto": "Texto", "semaforo": "Estado",
            "fe_solicitud": "Solicitada", "fe_entrega": "Entrega", "fe_pedido": "Fecha OC",
            "proveedor": "Proveedor", "solicitante": "Solicitante", "cantidad": "Cant.",
            "dias_abierta": "Días abierta"}),
        width="stretch", hide_index=True)

    st.subheader("🔎 Buscar SP")
    num = st.text_input("Número de SP", key="buscar_sp")
    if num:
        filas = df[df["sp"] == num.strip()]
        if filas.empty:
            st.warning("No está entre las SP abiertas del último archivo (puede estar concluida).")
        else:
            for _, f in filas.iterrows():
                st.write(f"**Pos. {f['pos']}** – {f['texto']} · {f['semaforo']} · "
                         f"Proveedor: {f['proveedor'] or '—'} · Entrega: {f['fe_entrega']}")
