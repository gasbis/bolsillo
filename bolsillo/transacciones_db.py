"""Operaciones de base de datos sobre CUENTAS y TRANSACCIONES: saldos,
ajuste de saldo, alta de gastos, ingresos y transferencias, cuentas
propuestas en el alta y categorías de gasto e ingreso (las que crea la
app y las que crea el usuario desde el formulario de alta).

Las funciones que reciben `session` no hacen commit: así se pueden
encadenar dentro de una misma transacción (p.ej. desde el importador).
Las que no la reciben abren y confirman la suya.
"""

from datetime import date, timedelta
from decimal import Decimal

import reflex as rx
import sqlmodel
from sqlalchemy import func

from bolsillo.iconos import COLOR_POR_DEFECTO, ICONOS, color_categoria
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

LARGO_MAXIMO_NOMBRE = 40

# Cuenta propuesta en el alta de un gasto o ingreso (ver `cuentas_por_defecto`).
DIAS_CUENTA_HABITUAL = 60
DIAS_CUENTA_FIJA = 365
MIN_GASTOS_CUENTA_FIJA = 2


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



_TIPOS_CATEGORIA = (TIPO_GASTO, TIPO_INGRESO)


def _comprobar_tipo(tipo: str):
    if tipo not in _TIPOS_CATEGORIA:
        raise ValueError(f"Tipo de categoría no válido: {tipo!r}")


def categorias(id_usuario: int, tipo: str) -> list[dict[str, str]]:
    """Categorías activas del usuario de un tipo (gasto o ingreso), en su
    orden, para el selector del formulario de alta: id, nombre, icono y
    color (ya resuelto con la paleta si el usuario no eligió uno)."""
    _comprobar_tipo(tipo)
    with rx.session() as session:
        filas = session.exec(
            sqlmodel.select(Categoria)
            .where(
                Categoria.id_usuario == id_usuario,
                Categoria.tipo == tipo,
                Categoria.activa == True,  # noqa: E712
            )
            .order_by(Categoria.orden, Categoria.id)
        ).all()
        return [
            {
                "id": str(c.id),
                "nombre": c.nombre,
                "icono": c.icono,
                "color": color_categoria(c.color, i),
            }
            for i, c in enumerate(filas)
        ]


def categorias_gasto(id_usuario: int) -> list[dict[str, str]]:
    return categorias(id_usuario, TIPO_GASTO)


def _normalizar_nombre(nombre: str) -> str:
    return " ".join((nombre or "").split())


def crear_categoria(id_usuario: int, tipo: str, nombre: str, icono: str) -> int:
    """Crea una categoría (de gasto o de ingreso) desde el formulario de
    alta y devuelve su id. Si ya existía archivada con ese nombre, la
    reactiva con el icono nuevo. ValueError si el nombre o el icono no
    valen o si ya hay una categoría activa de ese tipo con ese nombre
    (sin distinguir mayúsculas)."""
    _comprobar_tipo(tipo)
    nombre = _normalizar_nombre(nombre)
    if not nombre:
        raise ValueError("Escribe un nombre para la categoría.")
    if len(nombre) > LARGO_MAXIMO_NOMBRE:
        raise ValueError(f"El nombre no puede pasar de {LARGO_MAXIMO_NOMBRE} letras.")
    if icono not in ICONOS:
        raise ValueError("Elige un icono.")
    with rx.session() as session:
        existente = session.exec(
            sqlmodel.select(Categoria).where(
                Categoria.id_usuario == id_usuario,
                Categoria.tipo == tipo,
                func.lower(Categoria.nombre) == nombre.lower(),
            )
        ).first()
        if existente is not None and existente.activa:
            raise ValueError(f"Ya tienes la categoría «{existente.nombre}».")
        if existente is not None:
            existente.activa = True
            existente.icono = icono
            session.add(existente)
            categoria = existente
        else:
            categoria = obtener_o_crear_categoria(
                session, id_usuario, tipo, nombre, icono=icono, color=COLOR_POR_DEFECTO
            )
        session.commit()
        return categoria.id


def crear_categoria_gasto(id_usuario: int, nombre: str, icono: str) -> int:
    return crear_categoria(id_usuario, TIPO_GASTO, nombre, icono)


def _cuentas_activas(session: sqlmodel.Session, id_usuario: int) -> set[int]:
    return set(
        session.exec(
            sqlmodel.select(Cuenta.id).where(
                Cuenta.id_usuario == id_usuario, Cuenta.activa == True  # noqa: E712
            )
        ).all()
    )


def cuentas_por_defecto(
    id_usuario: int, hoy: date | None = None, tipo: str = TIPO_GASTO
) -> tuple[int | None, dict[int, int]]:
    """Datos para proponer la cuenta en el alta de un gasto o un ingreso
    (`tipo`); solo se miran los movimientos de ese tipo.

    Devuelve `(habitual, fijas)`:
    - `habitual`: la cuenta activa con más movimientos en los últimos
      DIAS_CUENTA_HABITUAL días (a igualdad, la usada más recientemente).
      Si no hay movimientos recientes, la del último anotado. None si el
      usuario no tiene ninguno en una cuenta activa.
    - `fijas`: {id_categoria: id_cuenta} para las categorías que en los
      últimos DIAS_CUENTA_FIJA días SIEMPRE han usado la misma cuenta
      (al menos MIN_GASTOS_CUENTA_FIJA movimientos), si esa cuenta sigue
      activa. Para esas categorías se propone esa cuenta.
    """
    _comprobar_tipo(tipo)
    hoy = hoy or date.today()
    with rx.session() as session:
        activas = _cuentas_activas(session, id_usuario)
        del_tipo = [Transaccion.id_usuario == id_usuario, Transaccion.tipo == tipo]

        habitual = session.exec(
            sqlmodel.select(Transaccion.id_cuenta)
            .where(
                *del_tipo,
                Transaccion.fecha >= hoy - timedelta(days=DIAS_CUENTA_HABITUAL),
                Transaccion.id_cuenta.in_(activas),
            )
            .group_by(Transaccion.id_cuenta)
            .order_by(
                func.count().desc(),
                func.max(Transaccion.fecha).desc(),
                func.max(Transaccion.creado_en).desc(),
            )
            .limit(1)
        ).first()
        if habitual is None:
            habitual = session.exec(
                sqlmodel.select(Transaccion.id_cuenta)
                .where(*del_tipo, Transaccion.id_cuenta.in_(activas))
                .order_by(Transaccion.fecha.desc(), Transaccion.creado_en.desc())
                .limit(1)
            ).first()

        fijas = {
            id_categoria: id_cuenta
            for id_categoria, id_cuenta in session.exec(
                sqlmodel.select(Transaccion.id_categoria, func.min(Transaccion.id_cuenta))
                .where(
                    *del_tipo,
                    Transaccion.id_categoria.is_not(None),
                    Transaccion.fecha >= hoy - timedelta(days=DIAS_CUENTA_FIJA),
                )
                .group_by(Transaccion.id_categoria)
                .having(
                    (func.count(Transaccion.id_cuenta.distinct()) == 1)
                    & (func.count() >= MIN_GASTOS_CUENTA_FIJA)
                )
            ).all()
            if id_cuenta in activas
        }
        return habitual, fijas


def _cuenta_valida(session: sqlmodel.Session, id_usuario: int, id_cuenta: int) -> Cuenta:
    cuenta = session.get(Cuenta, id_cuenta)
    if cuenta is None or cuenta.id_usuario != id_usuario or not cuenta.activa:
        raise ValueError("La cuenta no es válida")
    return cuenta


def crear_movimiento(
    id_usuario: int,
    tipo: str,
    id_categoria: int,
    id_cuenta: int,
    fecha,
    importe: Decimal,
    notas: str = "",
) -> Decimal:
    """Anota un gasto o un ingreso. Un gasto puede ser negativo
    (devolución); un ingreso tiene que ser positivo. Comprueba que la
    categoría (del mismo tipo) y la cuenta son del usuario y están
    activas; si no, ValueError. Devuelve el importe anotado, ya
    redondeado a 2 decimales."""
    _comprobar_tipo(tipo)
    importe = Decimal(importe).quantize(CERO)
    if importe == 0:
        raise ValueError("El importe no puede ser 0")
    if tipo == TIPO_INGRESO and importe < 0:
        raise ValueError("Un ingreso no puede ser negativo")
    with rx.session() as session:
        categoria = session.get(Categoria, id_categoria)
        if (
            categoria is None
            or categoria.id_usuario != id_usuario
            or categoria.tipo != tipo
            or not categoria.activa
        ):
            raise ValueError("La categoría no es válida")
        _cuenta_valida(session, id_usuario, id_cuenta)
        session.add(
            Transaccion(
                id_usuario=id_usuario,
                tipo=tipo,
                fecha=fecha,
                importe=importe,
                id_cuenta=id_cuenta,
                id_categoria=id_categoria,
                notas=notas.strip(),
            )
        )
        session.commit()
    return importe


def crear_gasto(
    id_usuario: int,
    id_categoria: int,
    id_cuenta: int,
    fecha,
    importe: Decimal,
    notas: str = "",
) -> Decimal:
    return crear_movimiento(id_usuario, TIPO_GASTO, id_categoria, id_cuenta, fecha, importe, notas)


# --- Transferencias ---------------------------------------------------------


def cuentas_transferencia_por_defecto(id_usuario: int) -> tuple[int | None, int | None]:
    """Origen y destino de la última transferencia anotada cuyas dos
    cuentas siguen activas, para proponerlos en el alta. (None, None) si
    no hay ninguna."""
    with rx.session() as session:
        activas = _cuentas_activas(session, id_usuario)
        ultima = session.exec(
            sqlmodel.select(Transaccion.id_cuenta, Transaccion.id_cuenta_destino)
            .where(
                Transaccion.id_usuario == id_usuario,
                Transaccion.tipo == TIPO_TRANSFERENCIA,
                Transaccion.id_cuenta.in_(activas),
                Transaccion.id_cuenta_destino.in_(activas),
            )
            .order_by(Transaccion.fecha.desc(), Transaccion.creado_en.desc())
            .limit(1)
        ).first()
        return (ultima[0], ultima[1]) if ultima else (None, None)


def crear_transferencia(
    id_usuario: int,
    id_origen: int,
    id_destino: int,
    fecha,
    importe: Decimal,
    notas: str = "",
) -> Decimal:
    """Anota una transferencia de `id_origen` a `id_destino`. El importe
    tiene que ser positivo y las cuentas distintas, del usuario y
    activas; si no, ValueError. Devuelve el importe anotado, ya
    redondeado a 2 decimales."""
    importe = Decimal(importe).quantize(CERO)
    if importe <= 0:
        raise ValueError("El importe tiene que ser mayor que 0")
    if id_origen == id_destino:
        raise ValueError("La cuenta de origen y la de destino tienen que ser distintas")
    with rx.session() as session:
        _cuenta_valida(session, id_usuario, id_origen)
        _cuenta_valida(session, id_usuario, id_destino)
        session.add(
            Transaccion(
                id_usuario=id_usuario,
                tipo=TIPO_TRANSFERENCIA,
                fecha=fecha,
                importe=importe,
                id_cuenta=id_origen,
                id_cuenta_destino=id_destino,
                notas=notas.strip(),
            )
        )
        session.commit()
    return importe
