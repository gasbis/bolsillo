import reflex as rx

from bolsillo.components.alta_gasto import dialogo_alta_gasto
from bolsillo.components.donut import grafico_categorias
from bolsillo.components.footer import footer
from bolsillo.components.header import header
from bolsillo.states.resumen_state import ResumenState


def _fila_saldo() -> rx.Component:
    return rx.flex(
        rx.icon_button(
            rx.icon(tag="menu", size=24),
            variant="soft",
            color_scheme="gray",
        ),
        rx.box(
            "SALDO: ",
            ResumenState.texto_saldo,
            background_color=rx.cond(ResumenState.saldo_negativo, "tomato", "orange"),
            border_radius="5px",
            padding_x="15px",
            padding_y="6px",
            font_weight="bold",
        ),
        rx.icon_button(
            rx.icon(tag="menu", size=24),
            variant="soft",
            color_scheme="gray",
        ),
        width="100%",
        justify="center",
        align="center",
        spacing="6",
        padding_y="0.5em",
        flex_shrink="0",
    )


def _flecha(tag: str, pasos: int) -> rx.Component:
    # Oculta (no quitada) en Todas/Intervalo para que el texto no se mueva.
    return rx.icon_button(
        rx.icon(tag=tag, size=18),
        size="1",
        variant="ghost",
        color_scheme="gray",
        on_click=ResumenState.mover(pasos),
        visibility=rx.cond(ResumenState.navegable, "visible", "hidden"),
    )


def _fila_periodo() -> rx.Component:
    """Periodo que se está viendo, con flechas para ir al anterior o al
    siguiente (día, semana, mes y año). Tocar el texto vuelve a hoy."""
    return rx.flex(
        _flecha("chevron-left", -1),
        rx.text(
            ResumenState.texto_periodo,
            size="2",
            weight="medium",
            text_align="center",
            min_width="10em",
            cursor="pointer",
            on_click=ResumenState.ir_a_hoy,
        ),
        _flecha("chevron-right", 1),
        width="100%",
        justify="center",
        align="center",
        spacing="3",
        padding_top="0.25em",
        flex_shrink="0",
    )


def index() -> rx.Component:
    """Pantalla principal pensada para móvil: ocupa exactamente el alto
    visible (100dvh) sin scroll. Cabecera, fecha, saldo y pie tienen su
    alto natural y el gráfico se queda con todo el hueco que sobra."""
    return rx.flex(
        header(),
        _fila_periodo(),
        # Zona del gráfico: crece para llenar el hueco y es un "container"
        # de tamaño, para que el gráfico pueda medirse con cqw/cqh y ser un
        # cuadrado tan grande como quepa.
        rx.flex(
            grafico_categorias(),
            flex="1",
            min_height="0",
            width="100%",
            padding_x="0.5em",
            align="center",
            justify="center",
            container_type="size",
        ),
        _fila_saldo(),
        rx.box(footer(), width="100%", padding_bottom="0.5em", flex_shrink="0"),
        dialogo_alta_gasto(),
        direction="column",
        height="100dvh",
        width="100%",
        max_width="40em",
        margin_x="auto",
        overflow="hidden",
        # Se monta al entrar ya identificado y también justo tras iniciar
        # sesión (requiere_login cambia de pantalla), así que los datos se
        # cargan en ambos casos sin tocar AuthState.
        on_mount=ResumenState.cargar,
    )
