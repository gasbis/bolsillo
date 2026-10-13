"""Pantallas de login y de cambio de contraseña obligatorio, y el campo
de formulario que reutilizan los diálogos de usuario."""

import reflex as rx

from bolsillo.states.auth_state import AuthState


def campo_login(
    label: str,
    name: str,
    tipo: str,
    error: rx.Var[str] | None = None,
    default_value: rx.Var[str] | str | None = None,
    required: bool = True,
) -> rx.Component:
    hijos = [
        rx.text(label, size="2", weight="medium"),
        rx.input(
            name=name,
            type=tipo,
            required=required,
            width="100%",
            **({"default_value": default_value} if default_value is not None else {}),
        ),
    ]
    if error is not None:
        hijos.append(rx.cond(error != "", rx.text(error, size="1", color="red")))
    return rx.flex(*hijos, direction="column", spacing="1", width="100%")


def tarjeta_centrada(*hijos: rx.Component) -> rx.Component:
    return rx.center(
        rx.card(
            rx.flex(*hijos, direction="column", spacing="4"),
            width="100%",
            max_width="360px",
            padding="1.5em",
        ),
        min_height="100vh",
        width="100%",
        padding="1em",
    )


def login_screen() -> rx.Component:
    return tarjeta_centrada(
        rx.hstack(
            rx.icon(tag="wallet", size=32),
            rx.heading("Bolsillo", size="6"),
            spacing="3",
            align="center",
        ),
        rx.text("Inicia sesión para continuar", size="2", color_scheme="gray"),
        rx.form(
            rx.flex(
                campo_login("Correo electrónico", "email", "email", AuthState.email_error),
                campo_login("Contraseña", "password", "password", AuthState.password_error),
                rx.cond(
                    AuthState.auth_error != "",
                    rx.callout(AuthState.auth_error, color_scheme="red", size="1"),
                ),
                rx.button("Acceder", type="submit", width="100%"),
                direction="column",
                spacing="3",
            ),
            on_submit=AuthState.sign_in,
            reset_on_submit=False,
            width="100%",
        ),
        rx.text(
            "Aplicación de uso privado accesible solo a usuarios autorizados.",
            size="1",
            color_scheme="gray",
        ),
        rx.link(
            rx.button(
                "Solicitar acceso",
                variant="soft",
                color_scheme="gray",
                width="100%",
                type="button",
            ),
            # mailto: la app no tiene servidor de correo; se abre el cliente
            # de correo del usuario con el mensaje ya preparado.
            href=(
                "mailto:gasbis@hotmail.com"
                "?subject=Solicitud%20de%20acceso%20a%20Bolsillo"
                "&body=Hola%2C%20me%20gustar%C3%ADa%20solicitar%20acceso%20a%20Bolsillo."
            ),
            width="100%",
            underline="none",
        ),
    )


def cambio_password_obligatorio() -> rx.Component:
    """Pantalla completa (no descartable): no se puede seguir hasta
    cambiar la contraseña inicial o temporal."""
    return tarjeta_centrada(
        rx.heading("Cambia tu contraseña", size="5"),
        rx.text(
            "Por seguridad, debes establecer una contraseña nueva antes de continuar.",
            size="2",
            color_scheme="gray",
        ),
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
                rx.button("Guardar contraseña", type="submit", width="100%"),
                direction="column",
                spacing="3",
            ),
            on_submit=AuthState.cambiar_password,
            reset_on_submit=True,
            width="100%",
        ),
        rx.button(
            "Cerrar sesión", on_click=AuthState.logout,
            variant="ghost", color_scheme="gray", size="1",
        ),
    )
