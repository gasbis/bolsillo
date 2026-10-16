"""Cálculo de los periodos de fecha del filtro de la pantalla principal.

Funciones puras (sin Reflex ni base de datos) para poder probarlas
sueltas. Un periodo se define por:

- `periodo`: uno de PERIODOS.
- `referencia`: un día cualquiera dentro del periodo que se está viendo
  (las flechas ‹ › lo mueven al periodo anterior/siguiente).
- `desde` / `hasta`: solo para PERIODO_INTERVALO.

y se traduce en un rango [inicio, fin] (ambos inclusive). `None` en
cualquiera de los dos extremos significa "sin límite por ese lado".
"""

from datetime import date, timedelta
from typing import Optional

PERIODO_DIA = "Día"
PERIODO_SEMANA = "Semana"
PERIODO_MES = "Mes"
PERIODO_ANYO = "Año"
PERIODO_TODAS = "Todas"
PERIODO_INTERVALO = "Intervalo"
PERIODO_ELEGIR_DIA = "Elegir día"

PERIODOS = [
    PERIODO_DIA,
    PERIODO_SEMANA,
    PERIODO_MES,
    PERIODO_ANYO,
    PERIODO_TODAS,
    PERIODO_INTERVALO,
    PERIODO_ELEGIR_DIA,
]

# Periodos que se pueden recorrer con las flechas ‹ ›.
PERIODOS_NAVEGABLES = {
    PERIODO_DIA,
    PERIODO_SEMANA,
    PERIODO_MES,
    PERIODO_ANYO,
    PERIODO_ELEGIR_DIA,
}

# Sin depender del locale del servidor (en un contenedor suele ser "C").
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
_MESES_CORTOS = [m[:3] for m in MESES]
_DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

Rango = tuple[Optional[date], Optional[date]]


def a_fecha(texto: str) -> Optional[date]:
    """'2026-10-15' (formato de <input type="date">) → date; vacío o
    incorrecto → None."""
    try:
        return date.fromisoformat(texto) if texto else None
    except ValueError:
        return None


def _fin_de_mes(d: date) -> date:
    siguiente = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return siguiente - timedelta(days=1)


def rango(periodo: str, referencia: date, desde: str = "", hasta: str = "") -> Rango:
    if periodo in (PERIODO_DIA, PERIODO_ELEGIR_DIA):
        return referencia, referencia
    if periodo == PERIODO_SEMANA:
        lunes = referencia - timedelta(days=referencia.weekday())
        return lunes, lunes + timedelta(days=6)
    if periodo == PERIODO_MES:
        return referencia.replace(day=1), _fin_de_mes(referencia)
    if periodo == PERIODO_ANYO:
        return date(referencia.year, 1, 1), date(referencia.year, 12, 31)
    if periodo == PERIODO_INTERVALO:
        inicio, fin = a_fecha(desde), a_fecha(hasta)
        if inicio and fin and inicio > fin:
            inicio, fin = fin, inicio
        return inicio, fin
    return None, None  # PERIODO_TODAS


def desplazar(periodo: str, referencia: date, pasos: int) -> date:
    """Mueve la referencia `pasos` periodos hacia delante (o hacia atrás si
    es negativo). En periodos no navegables la devuelve tal cual."""
    if periodo in (PERIODO_DIA, PERIODO_ELEGIR_DIA):
        return referencia + timedelta(days=pasos)
    if periodo == PERIODO_SEMANA:
        return referencia + timedelta(weeks=pasos)
    if periodo == PERIODO_MES:
        meses = referencia.year * 12 + referencia.month - 1 + pasos
        anyo, mes = divmod(meses, 12)
        primero = date(anyo, mes + 1, 1)
        # El 31 de enero + 1 mes es el 28/29 de febrero, no el 3 de marzo.
        return primero.replace(day=min(referencia.day, _fin_de_mes(primero).day))
    if periodo == PERIODO_ANYO:
        anyo = referencia.year + pasos
        # El 29 de febrero no existe en todos los años.
        dia = min(referencia.day, _fin_de_mes(date(anyo, referencia.month, 1)).day)
        return date(anyo, referencia.month, dia)
    return referencia


def _corta(d: date, con_anyo: bool = True) -> str:
    texto = f"{d.day} {_MESES_CORTOS[d.month - 1]}"
    return f"{texto} {d.year}" if con_anyo else texto


def etiqueta(periodo: str, referencia: date, desde: str = "", hasta: str = "",
             hoy: Optional[date] = None) -> str:
    """Texto que se muestra bajo la cabecera, p.ej. 'Octubre 2026'."""
    hoy = hoy or date.today()
    if periodo in (PERIODO_DIA, PERIODO_ELEGIR_DIA):
        if referencia == hoy:
            return "Hoy"
        if referencia == hoy - timedelta(days=1):
            return "Ayer"
        dia = _DIAS_SEMANA[referencia.weekday()].capitalize()
        return f"{dia}, {_corta(referencia)}"
    if periodo == PERIODO_SEMANA:
        inicio, fin = rango(periodo, referencia)
        return f"{_corta(inicio, con_anyo=inicio.year != fin.year)} – {_corta(fin)}"
    if periodo == PERIODO_MES:
        return f"{MESES[referencia.month - 1].capitalize()} {referencia.year}"
    if periodo == PERIODO_ANYO:
        return str(referencia.year)
    if periodo == PERIODO_INTERVALO:
        inicio, fin = rango(periodo, referencia, desde, hasta)
        if inicio and fin:
            return f"{_corta(inicio)} – {_corta(fin)}"
        if inicio:
            return f"Desde {_corta(inicio)}"
        if fin:
            return f"Hasta {_corta(fin)}"
        return "Todas las fechas"
    return "Todas las fechas"


# --- Fechas sueltas (listado de movimientos) -------------------------------


def fecha_corta(d: date, hoy: Optional[date] = None) -> str:
    """'14 oct' (o '14 oct 2025' si no es de este año)."""
    hoy = hoy or date.today()
    return _corta(d, con_anyo=d.year != hoy.year)


def fecha_dia(d: date, hoy: Optional[date] = None) -> str:
    """Cabecera de un día en el listado: 'Hoy', 'Ayer' o
    'Miércoles, 14 oct' (con el año si no es el actual)."""
    hoy = hoy or date.today()
    if d == hoy:
        return "Hoy"
    if d == hoy - timedelta(days=1):
        return "Ayer"
    return f"{_DIAS_SEMANA[d.weekday()].capitalize()}, {fecha_corta(d, hoy)}"
