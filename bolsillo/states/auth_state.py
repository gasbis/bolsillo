"""Sesión, login y gestión de usuarios. Adaptado de Gestión Cartera
(sin la parte de teléfono/avisos, que aquí no aplica)."""

import os
from typing import TypedDict

import reflex as rx

from bolsillo.auth_db import (
    crear_usuario,
    email_existe,
    establecer_activo,
    establecer_nombre,
    establecer_password,
    establecer_password_temporal,
    listar_usuarios,
    obtener_usuario_por_email,
    verify_password,
)


class UsuarioActual(TypedDict):
    id: int
    email: str
    nombre: str


class UsuarioDirectorio(TypedDict):
    email: str
    nombre: str
    activo: bool


USUARIO_VACIO: UsuarioActual = UsuarioActual(id=0, email="", nombre="")

# Único usuario con acceso a la página de gestión de usuarios. Se puede
# cambiar con la variable de entorno ADMIN_EMAIL sin tocar código.
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "gasbis@hotmail.com").strip().lower()

LONGITUD_MINIMA_PASSWORD = 8


class AuthState(rx.State):
    is_authenticated: bool = False
    # Si es True se muestra la pantalla de cambio de contraseña
    # obligatorio en vez del contenido (ver components/auth_guard.py).
    must_change_password: bool = False
    current_user: UsuarioActual = USUARIO_VACIO

    usuarios: list[UsuarioDirectorio] = []

    email_error: str = ""
    password_error: str = ""
    auth_error: str = ""

    nuevo_usuario_open: bool = False
    nuevo_usuario_email_error: str = ""
    nuevo_usuario_error: str = ""

    reset_password_open: bool = False
    reset_password_email: str = ""
    reset_password_nombre: str = ""
    reset_password_error: str = ""

    change_password_current_error: str = ""
    change_password_new_error: str = ""
    change_password_error: str = ""
    cambiar_password_dialog_open: bool = False

    nombre_error: str = ""
    cambiar_nombre_dialog_open: bool = False

    @rx.var
    def es_admin(self) -> bool:
        return self.current_user["email"] == ADMIN_EMAIL

    @rx.var
    def id_usuario(self) -> int:
        """Atajo para los demás states: `(await self.get_state(AuthState)).id_usuario`."""
        return self.current_user["id"]

    def _es_admin_autenticado(self) -> bool:
        # Ocultar un botón no basta: un event handler se puede invocar
        # desde el cliente igualmente, así que se comprueba también aquí.
        return self.is_authenticated and self.es_admin

    # --- Login / logout ---------------------------------------------------

    @rx.event
    def sign_in(self, form_data: dict):
        self.email_error = ""
        self.password_error = ""
        self.auth_error = ""

        email = form_data.get("email", "").strip().lower()
        password = form_data.get("password", "")

        if not email:
            self.email_error = "Introduce tu correo electrónico."
        if not password:
            self.password_error = "Introduce tu contraseña."
        if self.email_error or self.password_error:
            return

        usuario = obtener_usuario_por_email(email)
        if (
            usuario is None
            or not usuario.activo
            or not verify_password(password, usuario.password_hash)
        ):
            self.auth_error = "No hemos podido verificar tus credenciales."
            return

        self.is_authenticated = True
        self.must_change_password = usuario.debe_cambiar_password
        self.current_user = UsuarioActual(id=usuario.id, email=usuario.email, nombre=usuario.nombre)

        # El login se hace "in situ" (la página no cambia de URL), así que
        # el on_load de la página no se ha disparado con el usuario ya
        # autenticado. Redirigir a la misma ruta cuenta como navegación
        # nueva y vuelve a disparar el on_load.
        return rx.redirect(self.router.url.path)

    @rx.event
    def logout(self):
        self.reset()
        return rx.redirect("/")

    # --- Cambio de contraseña / nombre del propio usuario -----------------

    @rx.event
    def abrir_cambiar_password(self):
        self.change_password_current_error = ""
        self.change_password_new_error = ""
        self.change_password_error = ""
        self.cambiar_password_dialog_open = True

    @rx.event
    def set_cambiar_password_dialog_open(self, value: bool):
        self.cambiar_password_dialog_open = value

    @rx.event
    def cambiar_password(self, form_data: dict):
        self.change_password_current_error = ""
        self.change_password_new_error = ""
        self.change_password_error = ""

        if not self.is_authenticated:
            return

        actual = obtener_usuario_por_email(self.current_user["email"])
        if actual is None or not verify_password(
            form_data.get("current_password", ""), actual.password_hash
        ):
            self.change_password_current_error = "La contraseña actual no es correcta."
            return

        nueva = form_data.get("new_password", "")
        confirmar = form_data.get("confirm_password", "")
        if len(nueva) < LONGITUD_MINIMA_PASSWORD:
            self.change_password_new_error = (
                f"La nueva contraseña debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres."
            )
            return
        if nueva != confirmar:
            self.change_password_new_error = "Las contraseñas no coinciden."
            return

        establecer_password(self.current_user["email"], nueva)
        self.must_change_password = False
        self.cambiar_password_dialog_open = False

    @rx.event
    def abrir_cambiar_nombre(self):
        self.nombre_error = ""
        self.cambiar_nombre_dialog_open = True

    @rx.event
    def set_cambiar_nombre_dialog_open(self, value: bool):
        self.cambiar_nombre_dialog_open = value

    @rx.event
    def cambiar_nombre(self, form_data: dict):
        self.nombre_error = ""
        if not self.is_authenticated:
            return
        nuevo_nombre = form_data.get("nombre", "").strip()
        if not nuevo_nombre:
            self.nombre_error = "Introduce un nombre."
            return

        establecer_nombre(self.current_user["email"], nuevo_nombre)
        self.current_user = UsuarioActual(
            id=self.current_user["id"], email=self.current_user["email"], nombre=nuevo_nombre
        )
        self.cambiar_nombre_dialog_open = False

    # --- Gestión de usuarios (solo admin) -------------------------------

    @rx.event
    def cargar_usuarios(self):
        if self._es_admin_autenticado():
            self._recargar_usuarios()

    def _recargar_usuarios(self):
        self.usuarios = [
            UsuarioDirectorio(email=u.email, nombre=u.nombre, activo=u.activo)
            for u in listar_usuarios()
        ]

    @rx.event
    def set_nuevo_usuario_open(self, value: bool):
        self.nuevo_usuario_open = value

    @rx.event
    def abrir_nuevo_usuario(self):
        self.nuevo_usuario_email_error = ""
        self.nuevo_usuario_error = ""
        self.nuevo_usuario_open = True

    @rx.event
    def crear_usuario_nuevo(self, form_data: dict):
        self.nuevo_usuario_email_error = ""
        self.nuevo_usuario_error = ""
        if not self._es_admin_autenticado():
            return

        email = form_data.get("email", "").strip().lower()
        nombre = form_data.get("nombre", "").strip()
        password = form_data.get("password", "")

        if not email or "@" not in email:
            self.nuevo_usuario_email_error = "Introduce un correo válido."
            return
        if email_existe(email):
            self.nuevo_usuario_email_error = "Ya existe un usuario con ese correo."
            return
        if len(password) < LONGITUD_MINIMA_PASSWORD:
            self.nuevo_usuario_error = (
                f"La contraseña inicial debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres."
            )
            return
        if not crear_usuario(email, nombre or email, password):
            self.nuevo_usuario_error = "No se ha podido crear el usuario."
            return

        self._recargar_usuarios()
        self.nuevo_usuario_open = False

    @rx.event
    def alternar_activo(self, email: str):
        if not self._es_admin_autenticado():
            return
        if email == self.current_user["email"]:
            return  # no te puedes desactivar a ti mismo
        usuario = obtener_usuario_por_email(email)
        if usuario is None:
            return
        establecer_activo(email, not usuario.activo)
        self._recargar_usuarios()

    @rx.event
    def abrir_reset_password(self, email: str, nombre: str):
        if not self._es_admin_autenticado():
            return
        self.reset_password_email = email
        self.reset_password_nombre = nombre
        self.reset_password_error = ""
        self.reset_password_open = True

    @rx.event
    def set_reset_password_open(self, value: bool):
        self.reset_password_open = value

    @rx.event
    def restablecer_password_usuario(self, form_data: dict):
        self.reset_password_error = ""
        if not self._es_admin_autenticado():
            return

        password_temporal = form_data.get("password", "")
        if len(password_temporal) < LONGITUD_MINIMA_PASSWORD:
            self.reset_password_error = (
                f"La contraseña temporal debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres."
            )
            return
        if not establecer_password_temporal(self.reset_password_email, password_temporal):
            self.reset_password_error = "No se ha podido restablecer la contraseña."
            return

        self.reset_password_open = False
