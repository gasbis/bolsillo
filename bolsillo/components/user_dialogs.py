"""Diálogos de cambio de contraseña y de nombre del propio usuario. Se
abren desde el menú del header (ver components/header.py)."""

import reflex as rx

from bolsillo.components.auth import campo_login
from bolsillo.states.auth_state import AuthState


def _botonera(texto_guardar: str) -> rx.Component:
    return rx.hstack(
        rx.dialog.close(
            rx.button("Cancelar", variant="soft", color_scheme="gray", type="button")
        ),
        rx.button(texto_guardar, type="submit"),
        spacing="3",
        justify="end",
        width="100%",
    )


def dialogo_cambiar_password() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Cambiar contraseña"),
            rx.form(
                rx.flex(
                    campo_login(
                        "Contraseña actual", "current_password", "password",
                        AuthState.change_password_current_error,
                    ),
                    campo_login(
                        "Nueva contraseña", "new_password", "password",
                        AuthState.change_password_new_error,
                    ),
                    campo_login("Confirmar nueva contraseña", "confirm_password", "password"),
                    rx.cond(
                        AuthState.change_password_error != "",
                        rx.callout(AuthState.change_password_error, color_scheme="red", size="1"),
                    ),
                    _botonera("Guardar contraseña"),
                    direction="column",
                    spacing="3",
                ),
                on_submit=AuthState.cambiar_password,
                reset_on_submit=True,
            ),
            max_width="400px",
        ),
        open=AuthState.cambiar_password_dialog_open,
        on_open_change=AuthState.set_cambiar_password_dialog_open,
    )


def dialogo_cambiar_nombre() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Cambiar nombre"),
            rx.form(
                rx.flex(
                    campo_login(
                        "Nombre", "nombre", "text", AuthState.nombre_error,
                        default_value=AuthState.current_user["nombre"],
                    ),
                    _botonera("Guardar nombre"),
                    direction="column",
                    spacing="3",
                ),
                on_submit=AuthState.cambiar_nombre,
                reset_on_submit=False,
            ),
            max_width="400px",
        ),
        open=AuthState.cambiar_nombre_dialog_open,
        on_open_change=AuthState.set_cambiar_nombre_dialog_open,
    )


def dialogos_usuario() -> rx.Component:
    return rx.fragment(dialogo_cambiar_password(), dialogo_cambiar_nombre())
