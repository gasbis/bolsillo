import reflex as rx

from bolsillo.components.donut import grafico_categorias
from bolsillo.components.footer import footer
from bolsillo.components.header import FilterState, header


def _fila_saldo() -> rx.Component:
    return rx.flex(
        rx.icon_button(
            rx.icon(tag="menu", size=24),
            variant="soft",
            color_scheme="gray",
        ),
        rx.box(
            "SALDO: 12.000 €",
            background_color="orange",
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


def index() -> rx.Component:
    """Pantalla principal pensada para móvil: ocupa exactamente el alto
    visible (100dvh) sin scroll. Cabecera, fecha, saldo y pie tienen su
    alto natural y el gráfico se queda con todo el hueco que sobra."""
    return rx.flex(
        header(),
        rx.text(
            FilterState.date_item,
            size="2",
            text_align="center",
            width="100%",
            padding_top="0.25em",
            flex_shrink="0",
        ),
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
        direction="column",
        height="100dvh",
        width="100%",
        max_width="40em",
        margin_x="auto",
        overflow="hidden",
    )
