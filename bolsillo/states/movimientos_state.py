"""Listado de movimientos (gastos, ingresos y transferencias) del periodo
y la cuenta que se están viendo en la pantalla principal.

Se abre con cualquiera de los dos botones que flanquean el SALDO. Tiene
dos agrupaciones (`agrupacion`):

- Por categoría (por defecto): una fila por categoría con su total, en
  verde si es de ingreso y en rojo si es de gasto, y al final una fila
  "Transferencias". Al desplegarla salen sus movimientos (notas, fecha
  e importe), del más reciente al más antiguo.
- Por fecha: una fila por día con movimientos (del más reciente al más
  antiguo) con el saldo del día en verde o rojo. Al desplegarla salen
  sus movimientos (categoría, notas e importe).

Transferencias: con una cuenta elegida en el filtro, la que sale de
ella resta y la que entra suma, igual que en el SALDO. Con todas las
cuentas se anulan entre sí: no cambian ni el saldo del día ni el SALDO,
y su fila sale en gris con el total movido, solo para poder revisarlas.

Tocar un movimiento lo abre en su formulario para editarlo o borrarlo.
Como en el móvil los diálogos uno encima de otro se comportan mal, el
listado se cierra y, al terminar con el formulario, se vuelve a abrir
(`reabrir`) recargado, con el mismo grupo desplegado.

Las dos agrupaciones se calculan a la vez al abrir, así que cambiar de
una a otra no vuelve a consultar la base de datos. Desplegar y plegar
es cosa del navegador (<details>, ver components/movimientos.py).

Es un substate de ResumenState para usar sus filtros tal cual.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

import reflex as rx

from bolsillo import periodos
from bolsillo.models import TIPO_INGRESO, TIPO_TRANSFERENCIA
from bolsillo.resumen_db import (
    CATEGORIA_TRANSFERENCIAS,
    CERO,
    COLOR_TRANSFERENCIA,
    ICONO_TRANSFERENCIA,
    Movimiento,
    movimientos,
)
from bolsillo.states.auth_state import AuthState
from bolsillo.states.resumen_state import ResumenState, euros

AGRUPAR_CATEGORIA = "categoria"
AGRUPAR_FECHA = "fecha"

# Color del importe de un grupo.
VERDE, ROJO, GRIS = "green", "red", "gray"

_CLAVE_TRANSFERENCIAS = "t"


@dataclass
class Linea:
    """Un movimiento dentro de un grupo desplegado."""

    id: str = ""
    tipo: str = ""
    clave_grupo: str = ""  # para volver a desplegarlo tras editar
    titulo: str = ""
    detalle: str = ""
    importe: str = ""
    icono: str = ""  # solo por fecha (vacío = sin icono)
    color: str = ""


@dataclass
class Grupo:
    """Una fila plegable: una categoría (o las transferencias) o un día."""

    clave: str = ""
    titulo: str = ""
    detalle: str = ""  # nº de movimientos
    importe: str = ""
    tono: str = VERDE  # VERDE | ROJO | GRIS
    icono: str = ""  # solo por categoría
    color: str = ""
    lineas: list[Linea] = field(default_factory=list)


def _n_movimientos(n: int) -> str:
    return "1 movimiento" if n == 1 else f"{n} movimientos"


def _tono(valor: Decimal) -> str:
    return VERDE if valor >= 0 else ROJO


def _trayecto(m: Movimiento) -> str:
    return f"{m.origen} → {m.destino}"


def _importe_transferencia(m: Movimiento, id_cuenta: Optional[int]) -> str:
    """Con una cuenta elegida, con signo (sale o entra); con todas, el
    importe tal cual (no suma ni resta)."""
    return euros(m.importe if id_cuenta is None else m.efecto(id_cuenta))


def _con_detalle(*partes: str) -> str:
    return " · ".join(p for p in partes if p)


def _grupo_transferencias(
    ms: list[Movimiento], id_cuenta: Optional[int], hoy: date
) -> Grupo:
    if id_cuenta is None:
        total, tono = sum((m.importe for m in ms), CERO), GRIS
    else:
        total = sum((m.efecto(id_cuenta) for m in ms), CERO)
        tono = _tono(total)
    return Grupo(
        clave=_CLAVE_TRANSFERENCIAS,
        titulo=CATEGORIA_TRANSFERENCIAS,
        detalle=_n_movimientos(len(ms)),
        importe=euros(total),
        tono=tono,
        icono=ICONO_TRANSFERENCIA,
        color=COLOR_TRANSFERENCIA,
        lineas=[
            Linea(
                id=str(m.id),
                tipo=m.tipo,
                clave_grupo=_CLAVE_TRANSFERENCIAS,
                titulo=_trayecto(m),
                detalle=_con_detalle(periodos.fecha_corta(m.fecha, hoy), m.notas),
                importe=_importe_transferencia(m, id_cuenta),
            )
            for m in ms
        ],
    )


def _por_categoria(movs: list[Movimiento], id_cuenta: Optional[int], hoy: date) -> list[Grupo]:
    """Ingresos primero y luego gastos; dentro de cada tipo, de mayor a
    menor total. Las transferencias, al final."""
    grupos: dict[int, list[Movimiento]] = {}
    transferencias: list[Movimiento] = []
    for m in movs:  # ya vienen de más reciente a más antiguo
        if m.tipo == TIPO_TRANSFERENCIA:
            transferencias.append(m)
        else:
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
        clave = f"c{m0.id_categoria}"
        res.append(
            Grupo(
                clave=clave,
                titulo=m0.categoria,
                detalle=_n_movimientos(len(ms)),
                importe=euros(total(ms)),
                tono=VERDE if m0.tipo == TIPO_INGRESO else ROJO,
                icono=m0.icono,
                color=m0.color,
                lineas=[
                    Linea(
                        id=str(m.id),
                        tipo=m.tipo,
                        clave_grupo=clave,
                        # Sin notas, la fecha pasa a ser el texto principal.
                        titulo=m.notas or periodos.fecha_corta(m.fecha, hoy),
                        detalle=periodos.fecha_corta(m.fecha, hoy) if m.notas else "",
                        importe=euros(m.importe),
                    )
                    for m in ms
                ],
            )
        )
    if transferencias:
        res.append(_grupo_transferencias(transferencias, id_cuenta, hoy))
    return res


def _por_fecha(movs: list[Movimiento], id_cuenta: Optional[int], hoy: date) -> list[Grupo]:
    dias: dict[date, list[Movimiento]] = {}
    for m in movs:  # ya vienen de más reciente a más antiguo
        dias.setdefault(m.fecha, []).append(m)
    res = []
    for dia, ms in dias.items():
        clave = f"d{dia.isoformat()}"
        saldo = sum((m.efecto(id_cuenta) for m in ms), CERO)
        lineas = []
        for m in ms:
            es_transf = m.tipo == TIPO_TRANSFERENCIA
            lineas.append(
                Linea(
                    id=str(m.id),
                    tipo=m.tipo,
                    clave_grupo=clave,
                    titulo=_trayecto(m) if es_transf else m.categoria,
                    detalle=m.notas,
                    # Con signo, para que las líneas sumen el saldo del día.
                    importe=(
                        _importe_transferencia(m, id_cuenta)
                        if es_transf
                        else euros(m.efecto(id_cuenta))
                    ),
                    icono=m.icono,
                    color=m.color,
                )
            )
        res.append(
            Grupo(
                clave=clave,
                titulo=periodos.fecha_dia(dia, hoy),
                detalle=_n_movimientos(len(ms)),
                importe=euros(saldo),
                # Gris si queda a 0 (p.ej. solo transferencias con todas
                # las cuentas, que se anulan).
                tono=GRIS if saldo == 0 else _tono(saldo),
                lineas=lineas,
            )
        )
    return res


class MovimientosState(ResumenState):
    abierto: bool = False
    agrupacion: str = AGRUPAR_CATEGORIA
    por_categoria: list[Grupo] = []
    por_fecha: list[Grupo] = []
    # Grupo que se abre ya desplegado al volver de editar un movimiento.
    desplegado: str = ""

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
        id_cuenta = self._id_cuenta()
        movs = movimientos(id_usuario, inicio, fin, id_cuenta)
        hoy = date.today()
        self.por_categoria = _por_categoria(movs, id_cuenta, hoy)
        self.por_fecha = _por_fecha(movs, id_cuenta, hoy)

    @rx.event
    async def abrir(self):
        """Botones junto al SALDO: todo plegado."""
        self.desplegado = ""
        await self._cargar_movimientos()
        self.abierto = True

    @rx.event
    async def reabrir(self):
        """Al cerrar el formulario de edición: el listado recargado, con
        el grupo del movimiento editado desplegado y a la vista."""
        await self._cargar_movimientos()
        self.abierto = True
        if self.desplegado:
            # Espera a que el diálogo termine de abrirse.
            return rx.call_script(
                "setTimeout(function () {"
                f" var g = document.getElementById('grupo-{self.desplegado}');"
                " if (g) g.scrollIntoView({block: 'start'}); }, 250)"
            )

    @rx.event
    def set_abierto(self, abierto: bool):
        self.abierto = abierto
        if not abierto:
            # No guardar listas que pueden ser largas mientras no se ven.
            self.por_categoria, self.por_fecha = [], []
            self.desplegado = ""

    @rx.event
    def set_agrupacion(self, valor: str | list[str]):
        # (El segmented control declara str | list[str]; aquí siempre es str.)
        if isinstance(valor, str) and valor in (AGRUPAR_CATEGORIA, AGRUPAR_FECHA):
            self.agrupacion = valor

    @rx.event
    def editar(self, id_movimiento: str, tipo: str, clave_grupo: str):
        """Tocar un movimiento: cierra el listado y abre su formulario."""
        # Import aquí: los formularios importan este state para volver.
        from bolsillo.states.alta_gasto_state import AltaGastoState
        from bolsillo.states.alta_transferencia_state import AltaTransferenciaState

        self.desplegado = clave_grupo
        self.abierto = False
        if tipo == TIPO_TRANSFERENCIA:
            return AltaTransferenciaState.editar(id_movimiento)
        return AltaGastoState.editar(id_movimiento)
