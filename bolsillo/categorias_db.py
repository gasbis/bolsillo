"""Operaciones de base de datos de la página de CATEGORÍAS Y CUENTAS.

Categorías (gasto e ingreso):
- Se crean, renombran y cambian de icono.
- Eliminar una categoría borra DEFINITIVAMENTE sus movimientos (no hay
  papelera). Como alternativa se puede FUSIONAR con otra del mismo tipo:
  sus movimientos pasan a la otra y la categoría desaparece.
- La categoría "Ajuste" no se muestra en la edición: la gestiona la app
  (ver transacciones_db.categoria_ajuste).

Cuentas:
- Se crean, renombran, cambian de icono y se les corrige el saldo. El
  saldo no se toca directamente: se anota un gasto en "Ajuste" por la
  diferencia (transacciones_db.ajustar_saldo).
- Se pueden ARCHIVAR: dejan de salir en toda la app salvo en la lista de
  edición, desde donde se restauran. Sus movimientos se conservan.
- Eliminar una cuenta borra DEFINITIVAMENTE sus movimientos, también las
  transferencias con otras cuentas (lo que cambia el saldo de estas).

La creación de categorías ya vive en transacciones_db.crear_categoria
(la usa también el formulario de alta) y aquí se reutiliza.
"""

from decimal import Decimal

import reflex as rx
import sqlmodel
from sqlalchemy import delete, func, or_, update

from bolsillo import calculadora
from bolsillo.iconos import ICONOS
from bolsillo.models import CATEGORIA_AJUSTE, TIPO_GASTO, Categoria, Cuenta, Transaccion
from bolsillo.transacciones_db import (
    CERO,
    LARGO_MAXIMO_NOMBRE,
    _normalizar_nombre,
    categorias,
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


def _es_ajuste(c: Categoria) -> bool:
    return c.tipo == TIPO_GASTO and c.nombre == CATEGORIA_AJUSTE


# --- Categorías -------------------------------------------------------------


def categorias_editables(id_usuario: int, tipo: str) -> list[dict[str, str]]:
    """Categorías activas de un tipo para la página de edición: las del
    formulario de alta, salvo "Ajuste"."""
    return [
        c
        for c in categorias(id_usuario, tipo)
        if not (tipo == TIPO_GASTO and c["nombre"] == CATEGORIA_AJUSTE)
    ]


def _categoria_del_usuario(session, id_usuario: int, id_categoria: int) -> Categoria:
    c = session.get(Categoria, id_categoria)
    if c is None or c.id_usuario != id_usuario:
        raise ValueError("La categoría ya no existe.")
    if _es_ajuste(c):
        raise ValueError(f"La categoría «{CATEGORIA_AJUSTE}» no se puede modificar.")
    return c


def editar_categoria(id_usuario: int, id_categoria: int, nombre: str, icono: str) -> None:
    """Cambia el nombre y el icono de una categoría. ValueError si el
    nombre ya lo usa otra categoría del mismo tipo (sin distinguir
    mayúsculas, archivadas incluidas: la base de datos no admite dos
    iguales)."""
    with rx.session() as session:
        c = _categoria_del_usuario(session, id_usuario, id_categoria)
        nombre = _validar(nombre, icono, c.icono)
        if c.tipo == TIPO_GASTO and nombre.lower() == CATEGORIA_AJUSTE.lower():
            raise ValueError(f"«{CATEGORIA_AJUSTE}» es un nombre reservado.")
        otra = session.exec(
            sqlmodel.select(Categoria).where(
                Categoria.id_usuario == id_usuario,
                Categoria.tipo == c.tipo,
                Categoria.id != c.id,
                func.lower(Categoria.nombre) == nombre.lower(),
            )
        ).first()
        if otra is not None:
            raise ValueError(f"Ya existe la categoría «{otra.nombre}».")
        c.nombre = nombre
        c.icono = icono
        session.add(c)
        session.commit()


def movimientos_categoria(id_usuario: int, id_categoria: int) -> int:
    """Cuántos movimientos tiene la categoría (para el aviso de borrado)."""
    with rx.session() as session:
        return session.exec(
            sqlmodel.select(func.count()).where(
                Transaccion.id_usuario == id_usuario,
                Transaccion.id_categoria == id_categoria,
            )
        ).one()


def borrar_categoria(id_usuario: int, id_categoria: int) -> int:
    """Borra la categoría Y TODOS SUS MOVIMIENTOS. Devuelve cuántos
    movimientos se han borrado."""
    with rx.session() as session:
        c = _categoria_del_usuario(session, id_usuario, id_categoria)
        borrados = session.exec(
            delete(Transaccion).where(
                Transaccion.id_usuario == id_usuario,
                Transaccion.id_categoria == c.id,
            )
        ).rowcount
        session.delete(c)
        session.commit()
        return borrados


def fusionar_categoria(id_usuario: int, id_origen: int, id_destino: int) -> int:
    """Pasa todos los movimientos de `id_origen` a `id_destino` (del mismo
    tipo, activa) y borra `id_origen`. Devuelve cuántos se han movido."""
    if id_origen == id_destino:
        raise ValueError("Elige otra categoría.")
    with rx.session() as session:
        origen = _categoria_del_usuario(session, id_usuario, id_origen)
        destino = session.get(Categoria, id_destino)
        if (
            destino is None
            or destino.id_usuario != id_usuario
            or destino.tipo != origen.tipo
            or not destino.activa
        ):
            raise ValueError("La categoría de destino no es válida.")
        movidos = session.exec(
            update(Transaccion)
            .where(
                Transaccion.id_usuario == id_usuario,
                Transaccion.id_categoria == origen.id,
            )
            .values(id_categoria=destino.id)
        ).rowcount
        session.delete(origen)
        session.commit()
        return movidos


# --- Cuentas ----------------------------------------------------------------


def listar_cuentas(id_usuario: int) -> list[dict]:
    """Todas las cuentas del usuario con su saldo actual: primero las
    activas y después las archivadas, cada grupo en su orden."""
    with rx.session() as session:
        filas = session.exec(
            sqlmodel.select(Cuenta)
            .where(Cuenta.id_usuario == id_usuario)
            .order_by(Cuenta.activa.desc(), Cuenta.orden, Cuenta.nombre)
        ).all()
        return [
            {
                "id": c.id,
                "nombre": c.nombre,
                "icono": c.icono,
                "activa": c.activa,
                "saldo": saldo_cuenta(session, id_usuario, c.id),
            }
            for c in filas
        ]


def _cuenta_del_usuario(session, id_usuario: int, id_cuenta: int) -> Cuenta:
    c = session.get(Cuenta, id_cuenta)
    if c is None or c.id_usuario != id_usuario:
        raise ValueError("La cuenta ya no existe.")
    return c


def _comprobar_nombre_cuenta(session, id_usuario: int, nombre: str, excepto: int | None):
    condiciones = [
        Cuenta.id_usuario == id_usuario,
        func.lower(Cuenta.nombre) == nombre.lower(),
    ]
    if excepto is not None:
        condiciones.append(Cuenta.id != excepto)
    otra = session.exec(sqlmodel.select(Cuenta).where(*condiciones)).first()
    if otra is None:
        return
    if otra.activa:
        raise ValueError(f"Ya tienes la cuenta «{otra.nombre}».")
    raise ValueError(f"Ya tienes la cuenta «{otra.nombre}» archivada: restáurala desde la lista.")


def crear_cuenta(id_usuario: int, nombre: str, icono: str, saldo_inicial: Decimal) -> int:
    """Crea una cuenta y devuelve su id. ValueError si ya hay otra con ese
    nombre (activa o archivada)."""
    nombre = _validar(nombre, icono)
    saldo_inicial = Decimal(saldo_inicial or 0).quantize(CERO)
    if abs(saldo_inicial) > calculadora.MAXIMO:
        raise ValueError("El saldo inicial es demasiado grande.")
    with rx.session() as session:
        _comprobar_nombre_cuenta(session, id_usuario, nombre, None)
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
    """Cambia el nombre y el icono de una cuenta activa. El saldo se
    corrige aparte con transacciones_db.ajustar_saldo."""
    with rx.session() as session:
        c = _cuenta_del_usuario(session, id_usuario, id_cuenta)
        if not c.activa:
            raise ValueError("La cuenta está archivada: restáurala para editarla.")
        nombre = _validar(nombre, icono, c.icono)
        _comprobar_nombre_cuenta(session, id_usuario, nombre, c.id)
        c.nombre = nombre
        c.icono = icono
        session.add(c)
        session.commit()


def archivar_cuenta(id_usuario: int, id_cuenta: int, archivar: bool = True) -> None:
    """Archiva (o restaura, con `archivar=False`) una cuenta."""
    with rx.session() as session:
        c = _cuenta_del_usuario(session, id_usuario, id_cuenta)
        c.activa = not archivar
        session.add(c)
        session.commit()


def _de_la_cuenta(id_usuario: int, id_cuenta: int):
    return (
        Transaccion.id_usuario == id_usuario,
        or_(Transaccion.id_cuenta == id_cuenta, Transaccion.id_cuenta_destino == id_cuenta),
    )


def movimientos_cuenta(id_usuario: int, id_cuenta: int) -> int:
    """Cuántos movimientos tiene la cuenta, transferencias incluidas (para
    el aviso de borrado)."""
    with rx.session() as session:
        return session.exec(
            sqlmodel.select(func.count()).where(*_de_la_cuenta(id_usuario, id_cuenta))
        ).one()


def borrar_cuenta(id_usuario: int, id_cuenta: int) -> int:
    """Borra la cuenta Y TODOS SUS MOVIMIENTOS, también las transferencias
    desde o hacia ella. Devuelve cuántos movimientos se han borrado."""
    with rx.session() as session:
        c = _cuenta_del_usuario(session, id_usuario, id_cuenta)
        borrados = session.exec(
            delete(Transaccion).where(*_de_la_cuenta(id_usuario, c.id))
        ).rowcount
        session.delete(c)
        session.commit()
        return borrados
