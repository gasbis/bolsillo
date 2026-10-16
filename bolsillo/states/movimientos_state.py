"""Listado de movimientos (gastos e ingresos) del periodo y la cuenta
que se están viendo en la pantalla principal.

Se abre con cualquiera de los dos botones que flanquean el SALDO. Tiene
dos agrupaciones (`agrupacion`):

- Por categoría (por defecto): una fila por categoría con su total, en
  verde si es de ingreso y en rojo si es de gasto. Al desplegarla salen
  sus movimientos (fecha, notas e importe), del más reciente al más
  antiguo.
- Por fecha: una fila por día con movimientos (del más reciente al más
  antiguo) con el saldo del día (ingresos - gastos) en verde o rojo. Al
  desplegarla salen sus movimientos (categoría, notas e importe).

Las dos listas se calculan a la vez al abrir, así que cambiar de
agrupación no vuelve a consultar la base de datos. Desplegar y plegar
es cosa del navegador (<details>, ver components/movimientos.py).

Es un substate de ResumenState para usar sus filtros tal cual.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import reflex as rx

from bolsillo import periodos
from bolsillo.models import TIPO_INGRESO
from bolsillo.resumen_db import CERO, Movimiento, movimientos
from bolsillo.states.auth_state import AuthState
from bolsillo.states.resumen_state import ResumenState, euros

AGRUPAR_CATEGORIA = "categoria"
AGRUPAR_FECHA = "fecha"


@dataclass
class Linea:
    """Un movimiento dentro de un grupo desplegado."""

    titulo: str = ""  # notas (por categoría) o categoría (por fecha)
    detalle: str = ""  # fecha (por categoría) o notas (por fecha)
    importe: str = ""
    icono: str = ""  # solo por fecha (vacío = sin icono)
    color: str = ""
    sin_notas: bool = False  # el título es el texto de relleno "Sin notas"


@dataclass
class Grupo:
    """Una fila plegable: una categoría o un día."""

    clave: str = ""
    titulo: str = ""
    detalle: str = ""  # nº de movimientos
    importe: str = ""
    positivo: bool = True  # verde (ingreso / día en positivo) o rojo
    icono: str = ""  # solo por categoría
    color: str = ""
    lineas: list[Linea] = field(default_factory=list)


def _n_movimientos(n: int) -> str:
    return "1 movimiento" if n == 1 else f"{n} movimientos"


def _con_signo(m: Movimiento) -> Decimal:
    """Efecto en el saldo: + ingreso, - gasto (una devolución suma)."""
    return m.importe if m.tipo == TIPO_INGRESO else -m.importe


def _por_categoria(movs: list[Movimiento], hoy: date) -> list[Grupo]:
    """Ingresos primero y luego gastos; dentro de cada tipo, de mayor a
    menor total."""
    grupos: dict[int, list[Movimiento]] = {}
    for m in movs:  # ya vienen de más reciente a más antiguo
        grupos.setdefault(m.id_categoria, []).append(m)

    def total(ms: list[Movimiento]) -> Decimal:
        return sum((m.importe for m in ms), CERO)

    orden = sorted(
        grupos.values(),
        key=lambda ms: (ms[0].tipo != TIPO_INGRESO, -abs(total(ms))),
    )
    res = []
    for ms in orden:
        m0 = ms[0]
        res.append(
            Grupo(
                clave=f"c{m0.id_categoria}",
                titulo=m0.categoria,
                detalle=_n_movimientos(len(ms)),
                importe=euros(total(ms)),
                positivo=m0.tipo == TIPO_INGRESO,
                icono=m0.icono,
                color=m0.color,
                lineas=[
                    Linea(
                        titulo=m.notas or "Sin notas",
                        sin_notas=not m.notas,
                        detalle=periodos.fecha_corta(m.fecha, hoy),
                        importe=euros(m.importe),
                    )
                    for m in ms
                ],
            )
        )
    return res


def _por_fecha(movs: list[Movimiento], hoy: date) -> list[Grupo]:
    dias: dict[date, list[Movimiento]] = {}
    for m in movs:  # ya vienen de más reciente a más antiguo
        dias.setdefault(m.fecha, []).append(m)
    res = []
    for dia, ms in dias.items():
        saldo = sum((_con_signo(m) for m in ms), CERO)
        res.append(
            Grupo(
                clave=f"d{dia.isoformat()}",
                titulo=periodos.fecha_dia(dia, hoy),
                detalle=_n_movimientos(len(ms)),
                importe=euros(saldo),
                positivo=saldo >= 0,
                lineas=[
                    Linea(
                        titulo=m.categoria,
                        detalle=m.notas,
                        # Con signo, para que las líneas sumen el saldo del día.
                        importe=euros(_con_signo(m)),
                        icono=m.icono,
                        color=m.color,
                    )
                    for m in ms
                ],
            )
        )
    return res


class MovimientosState(ResumenState):
    abierto: bool = False
    agrupacion: str = AGRUPAR_CATEGORIA
    por_categoria: list[Grupo] = []
    por_fecha: list[Grupo] = []

    @rx.var
    def agrupado_por_fecha(self) -> bool:
        return self.agrupacion == AGRUPAR_FECHA

    @rx.var
    def vacio(self) -> bool:
        return not self.por_categoria

    async def _cargar_movimientos(self):
        id_usuario = (await self.get_state(AuthState)).current_user["id"]
        if not id_usuario:
            self.por_categoria, self.por_fecha = [], []
            return
        inicio, fin = periodos.rango(
            self.periodo, self._fecha_referencia(), self.desde, self.hasta
        )
        movs = movimientos(id_usuario, inicio, fin, self._id_cuenta())
        hoy = date.today()
        self.por_categoria = _por_categoria(movs, hoy)
        self.por_fecha = _por_fecha(movs, hoy)

    @rx.event
    async def abrir(self):
        await self._cargar_movimientos()
        self.abierto = True

    @rx.event
    def set_abierto(self, abierto: bool):
        self.abierto = abierto
        if not abierto:
            # No guardar listas que pueden ser largas mientras no se ven.
            self.por_categoria, self.por_fecha = [], []

    @rx.event
    def set_agrupacion(self, valor: str | list[str]):
        # (El segmented control declara str | list[str]; aquí siempre es str.)
        if isinstance(valor, str) and valor in (AGRUPAR_CATEGORIA, AGRUPAR_FECHA):
            self.agrupacion = valor
