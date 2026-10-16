"""Operaciones de base de datos de la página de CATEGORÍAS Y CUENTAS:
listar, crear, renombrar, cambiar el icono y eliminar.

Eliminar:
- Si la categoría o la cuenta no tiene movimientos, se borra de verdad.
- Si los tiene, se ARCHIVA (`activa = False`): desaparece de la lista y
  de los formularios de alta, pero sus movimientos siguen intactos y con
  su nombre. Crear otra vez una con el mismo nombre la reactiva.

La creación de categorías ya vive en transacciones_db.crear_categoria
(la usa también el formulario de alta) y aquí se reutiliza.
"""

from decimal import Decimal

import reflex as rx
import sqlmodel
from sqlalchemy import func, or_

from bolsillo import calculadora
from bolsillo.iconos import ICONOS
from bolsillo.models import CATEGORIA_AJUSTE, TIPO_GASTO, Categoria, Cuenta, Transaccion
from bolsillo.transacciones_db import (
    CERO,
    LARGO_MAXIMO_NOMBRE,
    _normalizar_nombre,
    saldo_cuenta,
)


def _validar(nombre: str, icono: str, icono_actual: str = "") -> str:
    """Devuelve el nombre normalizado o ValueError. Se admite dejar el
    icono que ya tenía aunque no esté en ICONOS (p.ej. uno importado)."""
    nombre = _normalizar_nombre(nombre)
    if not nombre:
        raise ValueError("Escribe un nombre.")
    if len(nombre) > LARGO_MAXIMO_NOMBRE:
        raise ValueError(f"El nombre no puede pasar de {LARGO_MAXIMO_NOMBRE} letras.")
    if icono not in ICONOS and not (icono and icono == icono_actual):
        raise ValueError("Elige un icono.")
    return nombre


# --- Categorías -------------------------------------------------------------


def _categoria_del_usuario(session, id_usuario: int, id_categoria: int) -> Categoria:
    c = session.get(Categoria, id_categoria)
    if c is None or c.id_usuario != id_usuario:
        raise ValueError("La categoría ya no existe.")
    return c


def editar_categoria(id_usuario: int, id_categoria: int, nombre: str, icono: str) -> None:
    """Cambia el nombre y el icono de una categoría. ValueError si el
    nombre ya lo usa otra categoría del mismo tipo (sin distinguir
    mayúsculas, archivadas incluidas: la base de datos no admite dos
    iguales)."""
    with rx.session() as session:
        c = _categoria_del_usuario(session, id_usuario, id_categoria)
        nombre = _validar(nombre, icono, c.icono)
        if c.tipo == TIPO_GASTO and c.nombre == CATEGORIA_AJUSTE and nombre != c.nombre:
            # El "ajustar saldo" de las cuentas la busca por su nombre.
            raise ValueError(f"La categoría «{CATEGORIA_AJUSTE}» no se puede renombrar.")
        otra = session.exec(
            sqlmodel.select(Categoria).where(
                Categoria.id_usuario == id_usuario,
                Categoria.tipo == c.tipo,
                Categoria.id != c.id,
                func.lower(Categoria.nombre) == nombre.lower(),
            )
        ).first()
        if otra is not None:
            if otra.activa:
                raise ValueError(f"Ya tienes la categoría «{otra.nombre}».")
            raise ValueError(
                f"Ya hay una categoría archivada «{otra.nombre}». "
                "Créala de nuevo desde «Añadir» para recuperarla."
            )
        c.nombre = nombre
        c.icono = icono
        session.add(c)
        session.commit()


def borrar_categoria(id_usuario: int, id_categoria: int) -> bool:
    """Borra la categoría o, si tiene movimientos, la archiva. Devuelve
    True si se ha archivado y False si se ha borrado."""
    with rx.session() as session:
        c = _categoria_del_usuario(session, id_usuario, id_categoria)
        usos = session.exec(
            sqlmodel.select(func.count()).where(
                Transaccion.id_usuario == id_usuario,
                Transaccion.id_categoria == c.id,
            )
        ).one()
        if usos:
            c.activa = False
            session.add(c)
            archivada = True
        else:
            session.delete(c)
            archivada = False
        session.commit()
        return archivada


# --- Cuentas ----------------------------------------------------------------


def listar_cuentas(id_usuario: int) -> list[dict]:
    """Cuentas activas del usuario, en su orden, con su saldo actual."""
    with rx.session() as session:
        filas = session.exec(
            sqlmodel.select(Cuenta)
            .where(Cuenta.id_usuario == id_usuario, Cuenta.activa == True)  # noqa: E712
            .order_by(Cuenta.orden, Cuenta.nombre)
        ).all()
        return [
            {
                "id": c.id,
                "nombre": c.nombre,
                "icono": c.icono,
                "saldo": saldo_cuenta(session, id_usuario, c.id),
            }
            for c in filas
        ]


def _cuenta_del_usuario(session, id_usuario: int, id_cuenta: int) -> Cuenta:
    c = session.get(Cuenta, id_cuenta)
    if c is None or c.id_usuario != id_usuario:
        raise ValueError("La cuenta ya no existe.")
    return c


def _otra_cuenta_con_nombre(session, id_usuario: int, nombre: str, excepto: int | None):
    condiciones = [
        Cuenta.id_usuario == id_usuario,
        func.lower(Cuenta.nombre) == nombre.lower(),
    ]
    if excepto is not None:
        condiciones.append(Cuenta.id != excepto)
    return session.exec(sqlmodel.select(Cuenta).where(*condiciones)).first()


def crear_cuenta(id_usuario: int, nombre: str, icono: str, saldo_inicial: Decimal) -> int:
    """Crea una cuenta y devuelve su id. Si había una archivada con ese
    nombre, la reactiva con el icono nuevo y CONSERVA su saldo inicial
    (sus movimientos antiguos dependen de él). ValueError si ya hay una
    activa con ese nombre."""
    nombre = _validar(nombre, icono)
    saldo_inicial = Decimal(saldo_inicial or 0).quantize(CERO)
    if abs(saldo_inicial) > calculadora.MAXIMO:
        raise ValueError("El saldo inicial es demasiado grande.")
    with rx.session() as session:
        existente = _otra_cuenta_con_nombre(session, id_usuario, nombre, None)
        if existente is not None and existente.activa:
            raise ValueError(f"Ya tienes la cuenta «{existente.nombre}».")
        if existente is not None:
            existente.activa = True
            existente.icono = icono
            session.add(existente)
            session.commit()
            return existente.id
        orden = session.exec(
            sqlmodel.select(func.coalesce(func.max(Cuenta.orden), -1)).where(
                Cuenta.id_usuario == id_usuario
            )
        ).one() + 1
        cuenta = Cuenta(
            id_usuario=id_usuario,
            nombre=nombre,
            icono=icono,
            saldo_inicial=saldo_inicial,
            orden=orden,
        )
        session.add(cuenta)
        session.commit()
        return cuenta.id


def editar_cuenta(id_usuario: int, id_cuenta: int, nombre: str, icono: str) -> None:
    """Cambia el nombre y el icono de una cuenta (el saldo se corrige
    con "ajustar saldo", no aquí)."""
    with rx.session() as session:
        c = _cuenta_del_usuario(session, id_usuario, id_cuenta)
        nombre = _validar(nombre, icono, c.icono)
        otra = _otra_cuenta_con_nombre(session, id_usuario, nombre, c.id)
        if otra is not None:
            if otra.activa:
                raise ValueError(f"Ya tienes la cuenta «{otra.nombre}».")
            raise ValueError(
                f"Ya hay una cuenta archivada «{otra.nombre}». "
                "Créala de nuevo desde «Añadir» para recuperarla."
            )
        c.nombre = nombre
        c.icono = icono
        session.add(c)
        session.commit()


def borrar_cuenta(id_usuario: int, id_cuenta: int) -> bool:
    """Borra la cuenta o, si tiene movimientos (también transferencias
    que llegan a ella), la archiva. Devuelve True si se ha archivado."""
    with rx.session() as session:
        c = _cuenta_del_usuario(session, id_usuario, id_cuenta)
        usos = session.exec(
            sqlmodel.select(func.count()).where(
                Transaccion.id_usuario == id_usuario,
                or_(Transaccion.id_cuenta == c.id, Transaccion.id_cuenta_destino == c.id),
            )
        ).one()
        if usos:
            c.activa = False
            session.add(c)
            archivada = True
        else:
            session.delete(c)
            archivada = False
        session.commit()
        return archivada

