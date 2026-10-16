"""Consultas para la pantalla principal: totales de un periodo y una
cuenta (o todas), gasto por categoría, saldo del periodo, listado de
movimientos y cuentas con su saldo actual.

Todo filtra por `id_usuario`. Los importes salen como `Decimal`; el
state los pasa a texto/float solo para mostrarlos.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

import reflex as rx
import sqlmodel
from sqlalchemy import func

from bolsillo.iconos import color_categoria
from bolsillo.models import (
    TIPO_GASTO,
    TIPO_INGRESO,
    TIPO_TRANSFERENCIA,
    Categoria,
    Cuenta,
    Transaccion,
)

CERO = Decimal("0.00")


# Cómo se ven las transferencias en el listado de movimientos y en el
# donut (no tienen categoría; se agrupan todas juntas).
CATEGORIA_TRANSFERENCIAS = "Transferencias"
ICONO_TRANSFERENCIA = "arrow-left-right"
COLOR_TRANSFERENCIA = "#94a3b8"


@dataclass
class GastoCategoria:
    id: int  # 0 en la porción de transferencias salientes
    nombre: str
    icono: str
    color: str
    importe: Decimal  # neto del periodo: puede ser 0 o negativo (devoluciones)
    es_transferencia: bool = False


@dataclass
class Resumen:
    # Categorías de gasto en su orden y, con una cuenta elegida, al final
    # las transferencias que salen de ella (si las hay).
    gastos: list[GastoCategoria]
    # Con una cuenta elegida incluyen sus transferencias: las entrantes
    # son ingresos de la cuenta y las salientes, gastos. Si no, una cuenta
    # que solo se nutre de transferencias (p.ej. "Bolsa") saldría sin
    # ingresos. Con todas las cuentas se anulan entre sí y no se suman.
    total_gastos: Decimal
    total_ingresos: Decimal
    saldo: Decimal  # del periodo: ingresos - gastos


@dataclass
class Movimiento:
    """Un gasto, ingreso o transferencia para el listado de movimientos."""

    id: int
    fecha: date
    tipo: str  # TIPO_GASTO | TIPO_INGRESO | TIPO_TRANSFERENCIA
    importe: Decimal  # tal cual está guardado (un gasto puede ser negativo)
    notas: str
    id_categoria: int  # 0 en las transferencias
    categoria: str  # CATEGORIA_TRANSFERENCIAS en las transferencias
    icono: str
    color: str  # ya resuelto con la paleta, igual que en el formulario
    # Solo transferencias: cuentas de origen y destino.
    id_origen: int = 0
    id_destino: int = 0
    origen: str = ""
    destino: str = ""
    # Solo gastos e ingresos: nombre de su cuenta (para el buscador).
    cuenta: str = ""

    def efecto(self, id_cuenta: Optional[int]) -> Decimal:
        """Lo que suma o resta al saldo del periodo: + ingreso, - gasto
        (una devolución suma). Una transferencia resta en la cuenta de
        origen y suma en la de destino; con todas las cuentas (None) se
        anula: 0."""
        if self.tipo == TIPO_INGRESO:
            return self.importe
        if self.tipo == TIPO_GASTO:
            return -self.importe
        if id_cuenta is None:
            return CERO
        if id_cuenta == self.id_origen:
            return -self.importe
        if id_cuenta == self.id_destino:
            return self.importe
        return CERO


def _dec(valor) -> Decimal:
    return Decimal(valor or 0).quantize(CERO)


def cuentas_usuario(id_usuario: int) -> list[dict]:
    """Cuentas activas del usuario (filtro y selectores de cuenta) con su
    icono y su saldo actual (Decimal)."""
    with rx.session() as session:
        cuentas = session.exec(
            sqlmodel.select(Cuenta)
            .where(Cuenta.id_usuario == id_usuario, Cuenta.activa == True)  # noqa: E712
            .order_by(Cuenta.orden, Cuenta.nombre)
        ).all()
        saldos = _saldos(session, id_usuario)
        return [
            {"id": str(c.id), "nombre": c.nombre, "icono": c.icono, "saldo": saldos.get(c.id, CERO)}
            for c in cuentas
        ]


def _condiciones_fecha(inicio: Optional[date], fin: Optional[date]) -> list:
    condiciones = []
    if inicio is not None:
        condiciones.append(Transaccion.fecha >= inicio)
    if fin is not None:
        condiciones.append(Transaccion.fecha <= fin)
    return condiciones


def _suma(session, *condiciones) -> Decimal:
    return _dec(
        session.exec(
            sqlmodel.select(func.coalesce(func.sum(Transaccion.importe), 0)).where(*condiciones)
        ).one()
    )


def _saldos(session, id_usuario: int) -> dict[int, Decimal]:
    """{id_cuenta: saldo actual} de todas las cuentas del usuario, con
    cuatro consultas en total (no cuatro por cuenta).

    saldo = saldo_inicial + ingresos - gastos - transf. salientes + entrantes.
    Los gastos negativos (devoluciones) suman solos por el signo. Mismo
    cálculo que transacciones_db.saldo_cuenta.
    """
    saldos: dict[int, Decimal] = {
        id_c: _dec(inicial)
        for id_c, inicial in session.exec(
            sqlmodel.select(Cuenta.id, Cuenta.saldo_inicial).where(Cuenta.id_usuario == id_usuario)
        ).all()
    }
    signo = {TIPO_INGRESO: 1, TIPO_GASTO: -1, TIPO_TRANSFERENCIA: -1}
    for id_c, tipo, total in session.exec(
        sqlmodel.select(Transaccion.id_cuenta, Transaccion.tipo, func.sum(Transaccion.importe))
        .where(Transaccion.id_usuario == id_usuario)
        .group_by(Transaccion.id_cuenta, Transaccion.tipo)
    ).all():
        if id_c in saldos:
            saldos[id_c] += signo.get(tipo, 0) * _dec(total)
    for id_c, total in session.exec(
        sqlmodel.select(Transaccion.id_cuenta_destino, func.sum(Transaccion.importe))
        .where(
            Transaccion.id_usuario == id_usuario,
            Transaccion.tipo == TIPO_TRANSFERENCIA,
        )
        .group_by(Transaccion.id_cuenta_destino)
    ).all():
        if id_c in saldos:
            saldos[id_c] += _dec(total)
    return saldos


def resumen(
    id_usuario: int,
    inicio: Optional[date],
    fin: Optional[date],
    id_cuenta: Optional[int] = None,
) -> Resumen:
    """Totales del periodo [inicio, fin] (None = sin límite) para una
    cuenta o, si `id_cuenta` es None, para todas."""
    condiciones = [Transaccion.id_usuario == id_usuario, *_condiciones_fecha(inicio, fin)]
    if id_cuenta is not None:
        condiciones.append(Transaccion.id_cuenta == id_cuenta)

    with rx.session() as session:
        por_categoria: dict[int, Decimal] = {
            id_cat: _dec(total)
            for id_cat, total in session.exec(
                sqlmodel.select(Transaccion.id_categoria, func.sum(Transaccion.importe))
                .where(*condiciones, Transaccion.tipo == TIPO_GASTO)
                .group_by(Transaccion.id_categoria)
            ).all()
        }

        categorias = session.exec(
            sqlmodel.select(Categoria)
            .where(Categoria.id_usuario == id_usuario, Categoria.tipo == TIPO_GASTO)
            .order_by(Categoria.orden, Categoria.id)
        ).all()

        gastos = [
            GastoCategoria(
                id=c.id,
                nombre=c.nombre,
                icono=c.icono,
                color=c.color,
                importe=por_categoria.get(c.id, CERO),
            )
            for c in categorias
            # Las archivadas solo aparecen si tienen movimientos en el periodo.
            if c.activa or por_categoria.get(c.id, CERO) != 0
        ]

        total_gastos = sum(por_categoria.values(), CERO)
        total_ingresos = _suma(session, *condiciones, Transaccion.tipo == TIPO_INGRESO)
        if id_cuenta is not None:
            transferencias = [
                Transaccion.id_usuario == id_usuario,
                Transaccion.tipo == TIPO_TRANSFERENCIA,
                *_condiciones_fecha(inicio, fin),
            ]
            entrantes = _suma(session, *transferencias, Transaccion.id_cuenta_destino == id_cuenta)
            salientes = _suma(session, *transferencias, Transaccion.id_cuenta == id_cuenta)
            total_ingresos += entrantes
            total_gastos += salientes
            if salientes != 0:
                # Porción propia en el donut para que sus % cuadren con
                # el total de gastos.
                gastos.append(
                    GastoCategoria(
                        id=0,
                        nombre=CATEGORIA_TRANSFERENCIAS,
                        icono=ICONO_TRANSFERENCIA,
                        color=COLOR_TRANSFERENCIA,
                        importe=salientes,
                        es_transferencia=True,
                    )
                )
        return Resumen(
            gastos=gastos,
            total_gastos=total_gastos,
            total_ingresos=total_ingresos,
            saldo=total_ingresos - total_gastos,
        )


def _colores_categorias(session, id_usuario: int) -> dict[int, str]:
    """{id_categoria: color} con la paleta aplicada igual que en el
    formulario de alta (posición entre las activas de su tipo). Las
    archivadas toman la posición que tendrían en la lista completa."""
    filas = session.exec(
        sqlmodel.select(Categoria)
        .where(Categoria.id_usuario == id_usuario)
        .order_by(Categoria.tipo, Categoria.orden, Categoria.id)
    ).all()
    colores: dict[int, str] = {}
    activas: dict[str, int] = {}
    todas: dict[str, int] = {}
    for c in filas:
        if c.activa:
            pos = activas.get(c.tipo, 0)
            activas[c.tipo] = pos + 1
        else:
            pos = todas.get(c.tipo, 0)
        todas[c.tipo] = todas.get(c.tipo, 0) + 1
        colores[c.id] = color_categoria(c.color, pos)
    return colores


def movimientos(
    id_usuario: int,
    inicio: Optional[date],
    fin: Optional[date],
    id_cuenta: Optional[int] = None,
) -> list[Movimiento]:
    """Gastos, ingresos y transferencias del periodo [inicio, fin]
    (None = sin límite) de una cuenta o de todas, del más reciente al
    más antiguo. Con una cuenta elegida salen las transferencias que
    salen de ella y las que llegan a ella."""
    condiciones = [Transaccion.id_usuario == id_usuario, *_condiciones_fecha(inicio, fin)]
    if id_cuenta is not None:
        condiciones.append(
            (Transaccion.id_cuenta == id_cuenta)
            | (
                (Transaccion.tipo == TIPO_TRANSFERENCIA)
                & (Transaccion.id_cuenta_destino == id_cuenta)
            )
        )

    with rx.session() as session:
        colores = _colores_categorias(session, id_usuario)
        nombres_cuentas = dict(
            session.exec(
                sqlmodel.select(Cuenta.id, Cuenta.nombre).where(Cuenta.id_usuario == id_usuario)
            ).all()
        )
        filas = session.exec(
            sqlmodel.select(Transaccion, Categoria)
            .join(Categoria, Categoria.id == Transaccion.id_categoria, isouter=True)
            .where(*condiciones)
            .order_by(Transaccion.fecha.desc(), Transaccion.creado_en.desc(), Transaccion.id.desc())
        ).all()

        res = []
        for t, c in filas:
            comunes = dict(id=t.id, fecha=t.fecha, tipo=t.tipo, importe=_dec(t.importe), notas=t.notas or "")
            if t.tipo == TIPO_TRANSFERENCIA:
                res.append(
                    Movimiento(
                        **comunes,
                        id_categoria=0,
                        categoria=CATEGORIA_TRANSFERENCIAS,
                        icono=ICONO_TRANSFERENCIA,
                        color=COLOR_TRANSFERENCIA,
                        id_origen=t.id_cuenta,
                        id_destino=t.id_cuenta_destino or 0,
                        origen=nombres_cuentas.get(t.id_cuenta, "?"),
                        destino=nombres_cuentas.get(t.id_cuenta_destino, "?"),
                    )
                )
            elif c is not None:
                res.append(
                    Movimiento(
                        **comunes,
                        id_categoria=c.id,
                        categoria=c.nombre,
                        icono=c.icono,
                        color=colores.get(c.id, color_categoria(c.color, 0)),
                        cuenta=nombres_cuentas.get(t.id_cuenta, ""),
                    )
                )
        return res
