import reflex as rx

from bolsillo.components.auth import cambio_password_obligatorio, login_screen
from bolsillo.states.auth_state import AuthState


def requiere_login(contenido: rx.Component) -> rx.Component:
    """Envuelve una página: sin sesión → login; con contraseña inicial o
    temporal pendiente → cambio obligatorio; si no, el contenido real."""
    return rx.cond(
        AuthState.is_authenticated,
        rx.cond(AuthState.must_change_password, cambio_password_obligatorio(), contenido),
        login_screen(),
    )


def acceso_denegado() -> rx.Component:
    return rx.center(
        rx.flex(
            rx.heading("Acceso restringido", size="5"),
            rx.text("No tienes permiso para acceder a esta página.", size="2", color_scheme="gray"),
            rx.link(rx.button("Volver a Inicio"), href="/"),
            direction="column",
            spacing="3",
            align="center",
        ),
        padding="4em",
        width="100%",
    )


def requiere_admin(contenido: rx.Component) -> rx.Component:
    """Como requiere_login, pero además exige ser el administrador."""
    return requiere_login(rx.cond(AuthState.es_admin, contenido, acceso_denegado()))
