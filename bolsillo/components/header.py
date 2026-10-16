import reflex as rx

from bolsillo import periodos
from bolsillo.components.selector_cuenta import selector_cuenta
from bolsillo.components.user_dialogs import dialogos_usuario
from bolsillo.states.alta_transferencia_state import AltaTransferenciaState
from bolsillo.states.auth_state import AuthState
from bolsillo.states.buscador_state import BuscadorState
from bolsillo.states.resumen_state import ResumenState

_NAV_ITEMS = [
    ("Inicio", "/", "house"),
    ("Categorias", "/categorias", "briefcase"),
]

def _campo_fecha(etiqueta: str, valor, al_cambiar) -> rx.Component:
    return rx.flex(
        rx.text(etiqueta, size="2", width="3.5em"),
        rx.input(type="date", value=valor, on_change=al_cambiar, flex="1"),
        align="center",
        spacing="2",
        width="100%",
    )


def filtros() -> rx.Component:
    """Contenido del popover del embudo: cuenta y periodo. Cada cambio
    recalcula al momento los datos de la pantalla principal."""
    return rx.flex(
        rx.text("Cuenta", size="1", weight="bold", color_scheme="gray"),
        selector_cuenta(
            ResumenState.opciones_filtro_cuenta,
            ResumenState.cuenta,
            ResumenState.set_cuenta,
            clave="nombre",
        ),
        rx.divider(),
        rx.text("Fecha", size="1", weight="bold", color_scheme="gray"),
        rx.radio(
            periodos.PERIODOS,
            value=ResumenState.periodo,
            on_change=ResumenState.set_periodo,
            direction="column",
        ),
        rx.cond(
            ResumenState.es_intervalo,
            rx.flex(
                _campo_fecha("Desde", ResumenState.desde, ResumenState.set_desde),
                _campo_fecha("Hasta", ResumenState.hasta, ResumenState.set_hasta),
                direction="column",
                spacing="2",
                width="100%",
            ),
        ),
        rx.cond(
            ResumenState.es_elegir_dia,
            _campo_fecha("Día", ResumenState.referencia, ResumenState.set_referencia),
        ),
        rx.divider(),
        rx.flex(
            rx.button(
                rx.icon(tag="rotate-ccw", size=14),
                "Restablecer",
                variant="soft",
                color_scheme="gray",
                size="1",
                on_click=ResumenState.restablecer,
            ),
            rx.popover.close(rx.button("Cerrar", size="1")),
            justify="between",
            width="100%",
        ),
        direction="column",
        spacing="2",
        min_width="14em",
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
                            # Relleno si hay un filtro distinto del de partida.
                            variant=rx.cond(ResumenState.filtro_activo, "solid", "soft"),
                        ),
                    ),
                    rx.popover.content(filtros(), side="bottom", align="start"),
                ),
            ),
            rx.flex(
                rx.vstack(
                    rx.text("Bolsillo", font_size="1em", font_weight="bold"),
                    rx.text(ResumenState.cuenta, size="1", color_scheme="red"),
                    spacing="1",
                ),
                
            ),
            rx.flex(
                rx.icon_button(
                    rx.icon(tag="search", size=20),
                    size="1",
                    # Buscador de movimientos (components/buscador.py).
                    on_click=BuscadorState.abrir,
                    custom_attrs={"aria-label": "Buscar"},
                ),
            ),
            rx.flex(
                rx.icon_button(
                    rx.icon(tag="arrow-left-right", size=20),
                    size="1",
                    # Alta de una transferencia entre cuentas.
                    on_click=AltaTransferenciaState.abrir,
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
                            rx.hstack(rx.icon(tag="smartphone", size=16), rx.text("Cerrar sesión en otros dispositivos"), spacing="2", align="center"),
                            on_select=AuthState.cerrar_otros_dispositivos,
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