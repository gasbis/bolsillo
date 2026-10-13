import reflex as rx

from bolsillo.components.user_dialogs import dialogos_usuario
from bolsillo.states.auth_state import AuthState

_NAV_ITEMS = [
    ("Inicio", "/", "house"),
    ("Categorias", "/categorias", "briefcase"),
]

_CUENTAS_ITEMS = [
    "Todas", "Banco1", "Banco2", "Cartera", "Tarjeta"
]

_FECHAS_ITEMS = [
    "Día", "Semana", "Mes", "Año", "Todas", "Intervalo", "Elegir día"
]
class FilterState(rx.State):
    date_item: str = "Todas"
    cuenta_item: str = "Todas"

    @rx.event
    def set_date_item(self, item: str):
        self.date_item = item

    @rx.event
    def set_cuenta_item(self, item: str):
        self.cuenta_item = item


def date_selector():
    return rx.vstack(  
        rx.radio(
            _FECHAS_ITEMS,
            value=FilterState.date_item,
            on_change=FilterState.set_date_item,
            direction="column"
        ),
    )

def _nav_menu_item(label: str, href: str, icon_tag: str) -> rx.Component:
    """Igual que `_nav_link` pero como entrada de `rx.menu` -- para el
    menú de navegación móvil (ver `_nav_mobile_menu`)."""
    return rx.menu.item(
        rx.hstack(
            rx.icon(tag=icon_tag, size=16),
            rx.text(label),
            spacing="2",
            align="center",
        ),
        on_select=rx.redirect(href),
    )


def header() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.flex(
                rx.popover.root(
                    rx.popover.trigger(
                        rx.icon_button(
                            rx.icon(tag="funnel", size=20),
                            size="1",
                        ),  
                    ),
                    rx.popover.content(
                        rx.flex(
                            rx.select(
                                _CUENTAS_ITEMS,
                                on_change=FilterState.set_cuenta_item,
                                value=FilterState.cuenta_item
                            ),
                            rx.divider(size="3"),
                            date_selector(),
                            direction="column",
                        ),
                    ),
                ),
                
            ),
            rx.flex(
                rx.vstack(
                    rx.text("Bolsillo", font_size="1em", font_weight="bold"),
                    rx.text(FilterState.cuenta_item, size="1", color_scheme="red"),
                    spacing="1",
                ),
                
            ),
            rx.flex(
                rx.icon_button(
                    rx.icon(tag="search", size=20),
                    size="1",
                ),        
            ),
            rx.flex(
                rx.icon_button(
                    rx.icon(tag="arrow-left-right", size=20),
                    size="1",
                ),                
            ),
            rx.flex(
                rx.menu.root(
                    rx.menu.trigger(
                        rx.icon_button(
                            rx.icon(tag="menu", size=20),
                            variant="soft",
                            color_scheme="gray",
                        ),
                    ),
                    rx.menu.content(
                        *[_nav_menu_item(label, href, icon) for label, href, icon in _NAV_ITEMS],
                        rx.cond(
                            AuthState.es_admin,
                            _nav_menu_item("Usuarios", "/usuarios", "users"),
                        ),
                        rx.menu.separator(),
                        rx.text(
                            AuthState.current_user["nombre"],
                            size="1", color_scheme="gray", padding_x="0.75em", padding_y="0.25em",
                        ),
                        rx.menu.item(
                            rx.hstack(rx.icon(tag="key-round", size=16), rx.text("Cambiar contraseña"), spacing="2", align="center"),
                            on_select=AuthState.abrir_cambiar_password,
                        ),
                        rx.menu.item(
                            rx.hstack(rx.icon(tag="user-pen", size=16), rx.text("Cambiar nombre"), spacing="2", align="center"),
                            on_select=AuthState.abrir_cambiar_nombre,
                        ),
                        rx.menu.item(
                            rx.hstack(rx.icon(tag="log-out", size=16), rx.text("Cerrar sesión"), spacing="2", align="center"),
                            on_select=AuthState.logout,
                            color="red",
                        ),
                    ),
                ),
                dialogos_usuario(),
            ),
            align="center",
            justify="between",
            width="100%",
            padding_y="0.5em",
            padding_x="1em",         
        ),                       
        rx.divider(size="4"),
        position="sticky",
        top="0",   
        z_index="10",
    )