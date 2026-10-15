"""Operaciones de base de datos sobre CUENTAS y TRANSACCIONES: saldos,
ajuste de saldo y categorías que la app crea por su cuenta.

Las funciones que reciben `session` no hacen commit: así se pueden
encadenar dentro de una misma transacción (p.ej. desde el importador).
Las que no la reciben abren y confirman la suya.
"""

from decimal import Decimal

import reflex as rx
import sqlmodel
from sqlalchemy import func

from bolsillo.models import (
    CATEGORIA_AJUSTE,
    TIPO_GASTO,
    TIPO_INGRESO,
    TIPO_TRANSFERENCIA,
    Categoria,
    Cuenta,
    Transaccion,
)

CERO = Decimal("0.00")


def _suma(session: sqlmodel.Session, *condiciones) -> Decimal:
    total = session.exec(
        sqlmodel.select(func.coalesce(func.sum(Transaccion.importe), 0)).where(*condiciones)
    ).one()
    return Decimal(total).quantize(CERO)


def saldo_cuenta(session: sqlmodel.Session, id_usuario: int, id_cuenta: int) -> Decimal:
    """Saldo actual = saldo_inicial + ingresos - gastos
    - transferencias salientes + transferencias entrantes.

    Los gastos negativos (devoluciones) suman solos, por el signo."""
    cuenta = session.get(Cuenta, id_cuenta)
    if cuenta is None or cuenta.id_usuario != id_usuario:
        raise ValueError(f"La cuenta {id_cuenta} no existe o no es del usuario")
    de_usuario = Transaccion.id_usuario == id_usuario
    ingresos = _suma(session, de_usuario, Transaccion.id_cuenta == id_cuenta,
                     Transaccion.tipo == TIPO_INGRESO)
    gastos = _suma(session, de_usuario, Transaccion.id_cuenta == id_cuenta,
                   Transaccion.tipo == TIPO_GASTO)
    salientes = _suma(session, de_usuario, Transaccion.id_cuenta == id_cuenta,
                      Transaccion.tipo == TIPO_TRANSFERENCIA)
    entrantes = _suma(session, de_usuario, Transaccion.id_cuenta_destino == id_cuenta,
                      Transaccion.tipo == TIPO_TRANSFERENCIA)
    return (Decimal(cuenta.saldo_inicial) + ingresos - gastos - salientes + entrantes).quantize(CERO)


def obtener_o_crear_categoria(
    session: sqlmodel.Session,
    id_usuario: int,
    tipo: str,
    nombre: str,
    icono: str = "coins",
    color: str = "#64748b",
) -> Categoria:
    """Devuelve la categoría (tipo, nombre) del usuario; si no existe la
    crea, y si estaba archivada la reactiva."""
    categoria = session.exec(
        sqlmodel.select(Categoria).where(
            Categoria.id_usuario == id_usuario,
            Categoria.tipo == tipo,
            Categoria.nombre == nombre,
        )
    ).first()
    if categoria is None:
        orden = session.exec(
            sqlmodel.select(func.coalesce(func.max(Categoria.orden), -1)).where(
                Categoria.id_usuario == id_usuario, Categoria.tipo == tipo
            )
        ).one() + 1
        categoria = Categoria(
            id_usuario=id_usuario, tipo=tipo, nombre=nombre,
            icono=icono, color=color, orden=orden,
        )
        session.add(categoria)
        session.flush()
    elif not categoria.activa:
        categoria.activa = True
        session.add(categoria)
    return categoria


def categoria_ajuste(session: sqlmodel.Session, id_usuario: int) -> Categoria:
    return obtener_o_crear_categoria(
        session, id_usuario, TIPO_GASTO, CATEGORIA_AJUSTE, icono="euro", color="#94a3b8"
    )


def ajustar_saldo(id_usuario: int, id_cuenta: int, saldo_nuevo: Decimal, fecha) -> Decimal:
    """'Editar' el saldo actual de una cuenta: anota automáticamente un
    gasto en la categoría Ajuste por la diferencia (negativo si el saldo
    sube). Devuelve el importe anotado (0 si no hacía falta ajustar)."""
    saldo_nuevo = Decimal(saldo_nuevo).quantize(CERO)
    with rx.session() as session:
        diferencia = saldo_cuenta(session, id_usuario, id_cuenta) - saldo_nuevo
        if diferencia == 0:
            return CERO
        session.add(
            Transaccion(
                id_usuario=id_usuario,
                tipo=TIPO_GASTO,
                fecha=fecha,
                importe=diferencia,
                id_cuenta=id_cuenta,
                id_categoria=categoria_ajuste(session, id_usuario).id,
                notas="Ajuste de saldo",
            )
        )
        session.commit()
        return diferencia
