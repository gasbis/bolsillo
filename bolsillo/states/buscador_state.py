"""Buscador de movimientos (lupa de la cabecera).

Busca entre TODOS los movimientos del usuario (gastos, ingresos y
transferencias), sin tener en cuenta el periodo ni la cuenta del filtro:
la idea es encontrar "aquel" movimiento esté donde esté.

Un único campo de texto. Lo escrito se compara, sin distinguir
mayúsculas ni acentos, con:

- la categoría ("Transferencias" en las transferencias),
- las notas,
- el importe: si lo escrito es un número. "12,50" (o "12.50") encuentra
  los de 12,50 €; "12" sin decimales encuentra los de 12,00 a 12,99 €.
  Se compara sin signo, así que también salen las devoluciones (gastos
  en negativo).

Si se escriben varias palabras, tienen que aparecer todas (en la
categoría o en las notas, en cualquier orden): "super leche" encuentra
un gasto de "Supermercado" con la nota "leche y huevos".

El filtrado se hace en Python y no en SQL: así lo de los acentos
funciona igual en SQLite y en Postgres, y el volumen de una persona
(unos miles de movimientos) se recorre en un instante.

Tocar un resultado lo abre en su formulario para editarlo o borrarlo;
igual que con el listado de movimientos, el buscador se cierra y al
terminar se vuelve a abrir (`reabrir`) con la misma búsqueda repetida,
para ver ya el cambio.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

import reflex as rx

from bolsillo import periodos
from bolsillo.models import TIPO_GASTO, TIPO_INGRESO, TIPO_TRANSFERENCIA
from bolsillo.resumen_db import Movimiento, movimientos
from bolsillo.states.auth_state import AuthState
from bolsillo.states.resumen_state import euros
from bolsillo.states.volver import ORIGEN_BUSCADOR

# Más resultados no caben con soltura en un móvil; se avisa de cuántos
# quedan fuera para que se afine la búsqueda.
MAX_RESULTADOS = 200
# Con menos letras (y sin ser un número) saldría casi todo.
MIN_LETRAS = 2

# Color del importe de un resultado.
VERDE, ROJO, GRIS = "green", "red", "gray"

_NUMERO = re.compile(r"^-?\d+(?:[.,]\d{1,2})?$")


@dataclass
class Resultado:
    id: str = ""
    tipo: str = ""
    titulo: str = ""  # categoría, o "Origen → Destino"
    detalle: str = ""  # fecha · cuenta · notas
    importe: str = ""
    tono: str = ROJO  # VERDE | ROJO | GRIS
    icono: str = ""
    color: str = ""


def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos: 'Cafetería' → 'cafeteria'."""
    sin_acentos = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_acentos if not unicodedata.combining(c)).casefold()


def _importe_buscado(texto: str) -> tuple[Decimal, bool] | None:
    """('12,50' → (12.50, exacto)); ('12' → (12, por parte entera));
    None si no es un número."""
    t = texto.strip().replace(" ", "").replace("€", "")
    # "1.234,56" → "1234,56" (puntos de miles)
    if "," in t and "." in t:
        t = t.replace(".", "")
    if not _NUMERO.match(t):
        return None
    try:
        valor = abs(Decimal(t.replace(",", ".")))
    except InvalidOperation:
        return None
    return valor, ("," in t or "." in t)


def _coincide_importe(m: Movimiento, buscado: tuple[Decimal, bool]) -> bool:
    valor, exacto = buscado
    importe = abs(m.importe)
    if exacto:
        return importe == valor
    return int(importe) == int(valor)


def _coincide_texto(m: Movimiento, palabras: list[str]) -> bool:
    texto = _normalizar(f"{m.categoria} {m.notas}")
    return all(p in texto for p in palabras)


def _resultado(m: Movimiento, hoy: date) -> Resultado:
    fecha = periodos.fecha_corta(m.fecha, hoy)
    if m.tipo == TIPO_TRANSFERENCIA:
        return Resultado(
            id=str(m.id),
            tipo=m.tipo,
            titulo=f"{m.origen} → {m.destino}",
            detalle=" · ".join(p for p in (fecha, m.notas) if p),
            importe=euros(m.importe),
            tono=GRIS,
            icono=m.icono,
            color=m.color,
        )
    # Con signo, como en el listado por fechas: - gasto, + ingreso.
    efecto = m.efecto(None)
    return Resultado(
        id=str(m.id),
        tipo=m.tipo,
        titulo=m.categoria,
        detalle=" · ".join(p for p in (fecha, m.cuenta, m.notas) if p),
        importe=euros(efecto),
        tono=VERDE if efecto >= 0 else ROJO,
        icono=m.icono,
        color=m.color,
    )


def buscar(movs: list[Movimiento], consulta: str) -> list[Movimiento]:
    """Movimientos (ya ordenados del más reciente al más antiguo) que
    casan con `consulta`. Lista vacía si la consulta es demasiado corta."""
    consulta = consulta.strip()
    importe = _importe_buscado(consulta)
    palabras = _normalizar(consulta).split()
    if importe is None and len(consulta) < MIN_LETRAS:
        return []
    res = []
    for m in movs:
        if m.tipo not in (TIPO_GASTO, TIPO_INGRESO, TIPO_TRANSFERENCIA):
            continue
        # Un número vale como importe o como texto de las notas
        # (p.ej. "2024" en "Seguro 2024").
        if (importe is not None and _coincide_importe(m, importe)) or _coincide_texto(m, palabras):
            res.append(m)
    return res


class BuscadorState(rx.State):
    abierto: bool = False
    consulta: str = ""
    resultados: list[Resultado] = []
    total: int = 0  # coincidencias, aunque solo se muestren MAX_RESULTADOS
    buscado: bool = False  # para no decir "sin resultados" antes de buscar
    # Resultado tocado: al volver de editarlo se lleva a la vista.
    _ultimo: str = ""

    @rx.var
    def texto_total(self) -> str:
        if not self.buscado:
            return ""
        if self.total == 0:
            return "Sin resultados."
        n = "1 movimiento" if self.total == 1 else f"{self.total} movimientos"
        if self.total > MAX_RESULTADOS:
            return f"{n} · se muestran los {MAX_RESULTADOS} más recientes"
        return n

    async def _buscar(self):
        id_usuario = (await self.get_state(AuthState)).current_user["id"]
        consulta = self.consulta.strip()
        if not id_usuario or (
            len(consulta) < MIN_LETRAS and _importe_buscado(consulta) is None
        ):
            self.resultados, self.total, self.buscado = [], 0, False
            return
        encontrados = buscar(movimientos(id_usuario, None, None, None), consulta)
        hoy = date.today()
        self.total = len(encontrados)
        self.resultados = [_resultado(m, hoy) for m in encontrados[:MAX_RESULTADOS]]
        self.buscado = True

    @rx.event
    async def abrir(self):
        """Lupa de la cabecera: se conserva la última búsqueda (es lo
        cómodo si se cierra y se vuelve a buscar lo mismo)."""
        self._ultimo = ""
        await self._buscar()
        self.abierto = True

    @rx.event
    async def reabrir(self):
        """Al cerrar el formulario de edición: misma búsqueda repetida
        (el movimiento puede haber cambiado o desaparecido)."""
        await self._buscar()
        self.abierto = True
        if self._ultimo:
            return rx.call_script(
                "setTimeout(function () {"
                f" var r = document.getElementById('res-{self._ultimo}');"
                " if (r) r.scrollIntoView({block: 'center'}); }, 250)"
            )

    @rx.event
    def set_abierto(self, abierto: bool):
        self.abierto = abierto
        if not abierto:
            # No guardar la lista mientras no se ve (la consulta, sí).
            self.resultados = []

    @rx.event
    async def set_consulta(self, valor: str):
        self.consulta = valor
        await self._buscar()

    @rx.event
    def limpiar(self):
        self.consulta = ""
        self.resultados, self.total, self.buscado = [], 0, False

    @rx.event
    def editar(self, id_movimiento: str, tipo: str):
        """Tocar un resultado: cierra el buscador y abre su formulario."""
        # Import aquí: los formularios importan este state para volver.
        from bolsillo.states.alta_gasto_state import AltaGastoState
        from bolsillo.states.alta_transferencia_state import AltaTransferenciaState

        self._ultimo = id_movimiento
        self.abierto = False
        if tipo == TIPO_TRANSFERENCIA:
            return AltaTransferenciaState.editar(id_movimiento, ORIGEN_BUSCADOR)
        return AltaGastoState.editar(id_movimiento, ORIGEN_BUSCADOR)
