"""Consultas para la pantalla principal: totales de un periodo y una
cuenta (o todas), gasto por categoría y saldo.

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
    saldo: Decimal  # al final del periodo (o actual si no tiene fin)


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

        return Resumen(
            gastos=gastos,
            total_gastos=sum(por_categoria.values(), CERO),
            total_ingresos=_suma(session, *condiciones, Transaccion.tipo == TIPO_INGRESO),
            saldo=_saldo(session, id_usuario, id_cuenta, fin),
        )
