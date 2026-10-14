"""Sesiones recordadas por dispositivo ("no volver a pedir la contraseña
en este móvil").

Flujo:
1. Al iniciar sesión se crea un token aleatorio. El navegador lo guarda
   en localStorage (AuthState.token_dispositivo) y aquí se guarda solo
   su hash.
2. Al abrir la app sin sesión activa, AuthState.restaurar_sesion manda
   el token; si el hash existe, no ha caducado y el usuario sigue
   activo, se entra directamente.
3. Cerrar sesión borra la sesión de ese dispositivo. Cambiar la
   contraseña cierra las de los DEMÁS dispositivos. Que el admin
   restablezca la contraseña o desactive al usuario las cierra TODAS.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import reflex as rx
import sqlmodel

from bolsillo.models import SesionDispositivo, Usuario

# Días sin abrir la app tras los que el dispositivo vuelve a pedir la
# contraseña. Cada uso renueva el plazo.
DIAS_CADUCIDAD = 180
# Para no escribir en la BD en cada apertura de la app.
_RENOVAR_CADA = timedelta(hours=12)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _utc(momento: datetime) -> datetime:
    # SQLite devuelve las fechas sin zona horaria; se guardaron en UTC.
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def crear_sesion(id_usuario: int, dispositivo: str = "") -> str:
    """Devuelve el token en claro, que solo debe ir al navegador."""
    token = secrets.token_urlsafe(32)
    with rx.session() as session:
        session.add(
            SesionDispositivo(
                id_usuario=id_usuario,
                token_hash=_hash(token),
                dispositivo=dispositivo[:250],
            )
        )
        session.commit()
    return token


def usuario_de_token(token: str) -> Usuario | None:
    """Usuario activo dueño del token, o None si el token no existe, ha
    caducado o el usuario está desactivado (en esos casos la sesión
    se borra)."""
    if not token:
        return None
    with rx.session() as session:
        sesion = session.exec(
            sqlmodel.select(SesionDispositivo).where(SesionDispositivo.token_hash == _hash(token))
        ).first()
        if sesion is None:
            return None

        ahora = _ahora()
        ultimo_uso = _utc(sesion.ultimo_uso)
        usuario = session.get(Usuario, sesion.id_usuario)
        if (
            usuario is None
            or not usuario.activo
            or ahora - ultimo_uso > timedelta(days=DIAS_CADUCIDAD)
        ):
            session.delete(sesion)
            session.commit()
            return None

        if ahora - ultimo_uso > _RENOVAR_CADA:
            sesion.ultimo_uso = ahora
            session.add(sesion)
            session.commit()
        session.refresh(usuario)
        return usuario


def cerrar_sesion(token: str) -> None:
    if not token:
        return
    with rx.session() as session:
        sesion = session.exec(
            sqlmodel.select(SesionDispositivo).where(SesionDispositivo.token_hash == _hash(token))
        ).first()
        if sesion is not None:
            session.delete(sesion)
            session.commit()


def cerrar_sesiones_usuario(id_usuario: int, excepto_token: str = "") -> int:
    """Cierra todas las sesiones recordadas del usuario, salvo la del
    token indicado (el dispositivo desde el que se hace). Devuelve
    cuántas ha cerrado."""
    excepto = _hash(excepto_token) if excepto_token else None
    with rx.session() as session:
        sesiones = session.exec(
            sqlmodel.select(SesionDispositivo).where(SesionDispositivo.id_usuario == id_usuario)
        ).all()
        cerradas = 0
        for sesion in sesiones:
            if sesion.token_hash != excepto:
                session.delete(sesion)
                cerradas += 1
        session.commit()
    return cerradas
