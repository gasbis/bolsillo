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
from bolsillo.sesiones_db import (
    cerrar_sesion,
    cerrar_sesiones_usuario,
    crear_sesion,
    usuario_de_token,
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

# Clave de localStorage donde el navegador guarda el token del
# dispositivo (ver sesiones_db.py).
CLAVE_TOKEN_DISPOSITIVO = "bolsillo_dispositivo"


class AuthState(rx.State):
    is_authenticated: bool = False
    # Si es True se muestra la pantalla de cambio de contraseña
    # obligatorio en vez del contenido (ver components/auth_guard.py).
    must_change_password: bool = False
    current_user: UsuarioActual = USUARIO_VACIO

    # Token de "sesión recordada" de este dispositivo. Vive en el
    # localStorage del navegador, así que sobrevive a cerrar la app o
    # reiniciar el móvil.
    token_dispositivo: str = rx.LocalStorage(name=CLAVE_TOKEN_DISPOSITIVO)
    # False hasta que `restaurar_sesion` ha mirado si este dispositivo
    # tiene una sesión recordada. Mientras tanto se muestra un spinner en
    # vez de la pantalla de login, para que no "parpadee" al abrir la app.
    sesion_comprobada: bool = False

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

    def _entrar(self, usuario) -> None:
        self.is_authenticated = True
        self.must_change_password = usuario.debe_cambiar_password
        self.current_user = UsuarioActual(id=usuario.id, email=usuario.email, nombre=usuario.nombre)

    def _olvidar_dispositivo(self):
        self.token_dispositivo = ""
        return rx.remove_local_storage(CLAVE_TOKEN_DISPOSITIVO)

    @rx.event
    def restaurar_sesion(self):
        """Primer evento del on_load de TODAS las páginas: si esta pestaña
        aún no tiene sesión pero el dispositivo tiene un token recordado
        y válido, entra sin pedir la contraseña."""
        if self.is_authenticated or not self.token_dispositivo:
            self.sesion_comprobada = True
            return
        usuario = usuario_de_token(self.token_dispositivo)
        self.sesion_comprobada = True
        if usuario is None:
            # Token caducado, revocado o de un usuario desactivado.
            return self._olvidar_dispositivo()
        self._entrar(usuario)

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

        self._entrar(usuario)
        self.sesion_comprobada = True

        # Casilla "Recordar este dispositivo" (marcada por defecto). Un
        # checkbox desmarcado no aparece en form_data.
        if form_data.get("recordar"):
            cerrar_sesion(self.token_dispositivo)  # por si había uno viejo
            self.token_dispositivo = crear_sesion(usuario.id, self._dispositivo())

        # El login se hace "in situ" (la página no cambia de URL), así que
        # el on_load de la página no se ha disparado con el usuario ya
        # autenticado. Redirigir a la misma ruta cuenta como navegación
        # nueva y vuelve a disparar el on_load.
        return rx.redirect(self.router.url.path)

    def _dispositivo(self) -> str:
        try:
            return self.router.headers.user_agent or ""
        except AttributeError:
            return ""

    @rx.event
    def logout(self):
        cerrar_sesion(self.token_dispositivo)
        self.is_authenticated = False
        self.must_change_password = False
        self.current_user = USUARIO_VACIO
        self.usuarios = []
        return [self._olvidar_dispositivo(), rx.redirect("/")]

    @rx.event
    def cerrar_otros_dispositivos(self):
        """Por si se pierde el móvil: cierra la sesión recordada en todos
        los dispositivos menos en este."""
        if not self.is_authenticated:
            return
        cerradas = cerrar_sesiones_usuario(self.current_user["id"], self.token_dispositivo)
        return rx.toast.success(
            "Sesión cerrada en los demás dispositivos."
            if cerradas
            else "No había sesiones abiertas en otros dispositivos."
        )

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
        # Quien tuviera la contraseña antigua deja de tener acceso desde
        # otros dispositivos; este sigue dentro.
        cerrar_sesiones_usuario(self.current_user["id"], self.token_dispositivo)
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
        if usuario.activo:  # se acaba de desactivar
            cerrar_sesiones_usuario(usuario.id)
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
        usuario = obtener_usuario_por_email(self.reset_password_email)
        if usuario is not None:
            cerrar_sesiones_usuario(usuario.id)

        self.reset_password_open = False
