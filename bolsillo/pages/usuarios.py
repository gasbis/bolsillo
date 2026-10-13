"""Alta y gestión de usuarios (solo admin). Adaptado de Gestión Cartera."""

import reflex as rx

from bolsillo.components.auth import campo_login
from bolsillo.components.auth_guard import requiere_admin
from bolsillo.components.header import header
from bolsillo.states.auth_state import AuthState


def tarjeta_usuario(item: dict) -> rx.Component:
    # Tarjetas en vez de tabla: la app se usa sobre todo en el móvil.
    return rx.card(
        rx.flex(
            rx.flex(
                rx.text(item["nombre"], weight="bold"),
                rx.text(item["email"], size="1", color_scheme="gray"),
                direction="column",
                min_width="0",
            ),
            rx.spacer(),
            rx.badge(
                rx.cond(item["activo"], "Activo", "Inactivo"),
                color_scheme=rx.cond(item["activo"], "green", "gray"),
            ),
            align="center",
            spacing="2",
            width="100%",
        ),
        rx.hstack(
            rx.button(
                "Restablecer contraseña",
                on_click=AuthState.abrir_reset_password(item["email"], item["nombre"]),
                size="1",
                variant="soft",
                color_scheme="gray",
            ),
            rx.button(
                rx.cond(item["activo"], "Desactivar", "Activar"),
                on_click=AuthState.alternar_activo(item["email"]),
                disabled=AuthState.current_user["email"] == item["email"],
                size="1",
                variant="soft",
            ),
            spacing="2",
            margin_top="0.5em",
            wrap="wrap",
        ),
        width="100%",
    )


def _botonera(texto_ok: str) -> rx.Component:
    return rx.hstack(
        rx.dialog.close(
            rx.button("Cancelar", variant="soft", color_scheme="gray", type="button")
        ),
        rx.button(texto_ok, type="submit"),
        spacing="3",
        justify="end",
        width="100%",
    )


def dialogo_reset_password() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Restablecer contraseña"),
            rx.dialog.description(
                f"Vas a poner una contraseña temporal para {AuthState.reset_password_nombre}. "
                "Tendrá que cambiarla por una propia en su próximo inicio de sesión.",
                size="2",
                color_scheme="gray",
            ),
            rx.form(
                rx.flex(
                    campo_login("Contraseña temporal", "password", "password"),
                    rx.cond(
                        AuthState.reset_password_error != "",
                        rx.callout(AuthState.reset_password_error, color_scheme="red", size="1"),
                    ),
                    _botonera("Restablecer"),
                    direction="column",
                    spacing="3",
                    padding_top="0.5em",
                ),
                on_submit=AuthState.restablecer_password_usuario,
                reset_on_submit=True,
            ),
            max_width="400px",
        ),
        open=AuthState.reset_password_open,
        on_open_change=AuthState.set_reset_password_open,
    )


def dialogo_nuevo_usuario() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Nuevo usuario"),
            rx.form(
                rx.flex(
                    campo_login(
                        "Correo electrónico", "email", "email", AuthState.nuevo_usuario_email_error
                    ),
                    campo_login("Nombre", "nombre", "text"),
                    campo_login("Contraseña inicial", "password", "password"),
                    rx.cond(
                        AuthState.nuevo_usuario_error != "",
                        rx.callout(AuthState.nuevo_usuario_error, color_scheme="red", size="1"),
                    ),
                    _botonera("Crear usuario"),
                    direction="column",
                    spacing="3",
                ),
                on_submit=AuthState.crear_usuario_nuevo,
                reset_on_submit=True,
            ),
            max_width="400px",
        ),
        open=AuthState.nuevo_usuario_open,
        on_open_change=AuthState.set_nuevo_usuario_open,
    )


def pagina_usuarios() -> rx.Component:
    return rx.container(
        header(),
        rx.flex(
            rx.hstack(
                rx.heading("Usuarios", size="5"),
                rx.spacer(),
                rx.button(
                    rx.icon(tag="user-plus", size=16), "Nuevo",
                    on_click=AuthState.abrir_nuevo_usuario,
                ),
                width="100%",
                align="center",
            ),
            rx.foreach(AuthState.usuarios, tarjeta_usuario),
            dialogo_nuevo_usuario(),
            dialogo_reset_password(),
            direction="column",
            spacing="3",
            padding="1em",
        ),
        size="2",
    )


def usuarios() -> rx.Component:
    return requiere_admin(pagina_usuarios())
