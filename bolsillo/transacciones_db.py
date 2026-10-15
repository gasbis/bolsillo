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


def categorias_gasto(id_usuario: int) -> list[dict[str, str]]:
    """Categorías de gasto activas del usuario, en su orden, para el
    selector del formulario de alta."""
    with rx.session() as session:
        categorias = session.exec(
            sqlmodel.select(Categoria)
            .where(
                Categoria.id_usuario == id_usuario,
                Categoria.tipo == TIPO_GASTO,
                Categoria.activa == True,  # noqa: E712
            )
            .order_by(Categoria.orden, Categoria.id)
        ).all()
        return [{"id": str(c.id), "nombre": c.nombre} for c in categorias]


def crear_gasto(
    id_usuario: int,
    id_categoria: int,
    id_cuenta: int,
    fecha,
    importe: Decimal,
    notas: str = "",
) -> Decimal:
    """Anota un gasto (negativo = devolución). Comprueba que la categoría
    y la cuenta son del usuario y están activas; si no, ValueError.
    Devuelve el importe anotado, ya redondeado a 2 decimales."""
    importe = Decimal(importe).quantize(CERO)
    if importe == 0:
        raise ValueError("El importe no puede ser 0")
    with rx.session() as session:
        categoria = session.get(Categoria, id_categoria)
        if (
            categoria is None
            or categoria.id_usuario != id_usuario
            or categoria.tipo != TIPO_GASTO
            or not categoria.activa
        ):
            raise ValueError("La categoría no es válida")
        cuenta = session.get(Cuenta, id_cuenta)
        if cuenta is None or cuenta.id_usuario != id_usuario or not cuenta.activa:
            raise ValueError("La cuenta no es válida")
        session.add(
            Transaccion(
                id_usuario=id_usuario,
                tipo=TIPO_GASTO,
                fecha=fecha,
                importe=importe,
                id_cuenta=id_cuenta,
                id_categoria=id_categoria,
                notas=notas.strip(),
            )
        )
        session.commit()
    return importe
