"""Consultas para la pantalla principal: totales de un periodo y una
cuenta (o todas), gasto por categoría, saldo del periodo y listado de
movimientos.

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


@dataclass
class GastoCategoria:
    id: int
    nombre: str
    icono: str
    color: str
    importe: Decimal  # neto del periodo: puede ser 0 o negativo (devoluciones)


@dataclass
class Resumen:
    gastos: list[GastoCategoria]  # categorías de gasto, en su orden
    total_gastos: Decimal
    total_ingresos: Decimal
    saldo: Decimal  # del periodo: total_ingresos - total_gastos


@dataclass
class Movimiento:
    """Un gasto o ingreso para el listado de movimientos."""

    fecha: date
    tipo: str  # TIPO_GASTO | TIPO_INGRESO
    importe: Decimal  # tal cual está guardado (un gasto puede ser negativo)
    notas: str
    id_categoria: int
    categoria: str
    icono: str
    color: str  # ya resuelto con la paleta, igual que en el formulario


def _dec(valor) -> Decimal:
    return Decimal(valor or 0).quantize(CERO)


def cuentas_usuario(id_usuario: int) -> list[dict[str, str]]:
    """Cuentas activas del usuario para el selector del filtro."""
    with rx.session() as session:
        cuentas = session.exec(
            sqlmodel.select(Cuenta)
            .where(Cuenta.id_usuario == id_usuario, Cuenta.activa == True)  # noqa: E712
            .order_by(Cuenta.orden, Cuenta.nombre)
        ).all()
        return [{"id": str(c.id), "nombre": c.nombre} for c in cuentas]


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


def _saldo(session, id_usuario: int, id_cuenta: Optional[int], hasta: Optional[date]) -> Decimal:
    """Saldo a fecha `hasta` (incluida) de una cuenta o, con None, de todas.

    Ya no se usa en la pantalla principal (allí el saldo es el del
    periodo); se deja para cuando haya un listado de cuentas con su saldo.

    saldo = saldo_inicial + ingresos - gastos - transf. salientes + entrantes.
    Los gastos negativos (devoluciones) suman solos por el signo. Con
    todas las cuentas las transferencias se anulan entre sí y no hace
    falta sumarlas.
    """
    de_usuario = Transaccion.id_usuario == id_usuario
    fechas = _condiciones_fecha(None, hasta)

    if id_cuenta is None:
        inicial = _dec(
            session.exec(
                sqlmodel.select(func.coalesce(func.sum(Cuenta.saldo_inicial), 0)).where(
                    Cuenta.id_usuario == id_usuario
                )
            ).one()
        )
        ingresos = _suma(session, de_usuario, Transaccion.tipo == TIPO_INGRESO, *fechas)
        gastos = _suma(session, de_usuario, Transaccion.tipo == TIPO_GASTO, *fechas)
        return inicial + ingresos - gastos

    cuenta = session.get(Cuenta, id_cuenta)
    if cuenta is None or cuenta.id_usuario != id_usuario:
        return CERO
    en_cuenta = Transaccion.id_cuenta == id_cuenta
    ingresos = _suma(session, de_usuario, en_cuenta, Transaccion.tipo == TIPO_INGRESO, *fechas)
    gastos = _suma(session, de_usuario, en_cuenta, Transaccion.tipo == TIPO_GASTO, *fechas)
    salientes = _suma(
        session, de_usuario, en_cuenta, Transaccion.tipo == TIPO_TRANSFERENCIA, *fechas
    )
    entrantes = _suma(
        session,
        de_usuario,
        Transaccion.id_cuenta_destino == id_cuenta,
        Transaccion.tipo == TIPO_TRANSFERENCIA,
        *fechas,
    )
    return _dec(cuenta.saldo_inicial) + ingresos - gastos - salientes + entrantes


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
    """Gastos e ingresos del periodo [inicio, fin] (None = sin límite) de
    una cuenta o de todas, del más reciente al más antiguo.

    Las transferencias no salen: no tienen categoría y no cuentan ni como
    gasto ni como ingreso (no cambian el saldo del periodo)."""
    condiciones = [
        Transaccion.id_usuario == id_usuario,
        Transaccion.tipo.in_((TIPO_GASTO, TIPO_INGRESO)),
        *_condiciones_fecha(inicio, fin),
    ]
    if id_cuenta is not None:
        condiciones.append(Transaccion.id_cuenta == id_cuenta)

    with rx.session() as session:
        colores = _colores_categorias(session, id_usuario)
        filas = session.exec(
            sqlmodel.select(Transaccion, Categoria)
            .join(Categoria, Categoria.id == Transaccion.id_categoria)
            .where(*condiciones)
            .order_by(Transaccion.fecha.desc(), Transaccion.creado_en.desc(), Transaccion.id.desc())
        ).all()
        return [
            Movimiento(
                fecha=t.fecha,
                tipo=t.tipo,
                importe=_dec(t.importe),
                notas=t.notas or "",
                id_categoria=c.id,
                categoria=c.nombre,
                icono=c.icono,
                color=colores.get(c.id, color_categoria(c.color, 0)),
            )
            for t, c in filas
        ]
