import reflex as rx

from bolsillo.states.alta_gasto_state import AltaGastoState


def footer() -> rx.Component:
    return rx.vstack(
        rx.divider(size="4"),
        rx.flex(
            rx.spacer(),
            rx.icon_button(
                rx.icon(tag="arrow-big-up", size=30),
                size="4",
                color_scheme="green",
                radius="full",
                # Alta de ingreso sin categoría elegida.
                on_click=AltaGastoState.abrir_ingreso(""),
            ),
            rx.spacer(),
            rx.icon_button(
                rx.icon(tag="arrow-big-down", size=30),
                size="4",
                color_scheme="red",
                radius="full",
                # Alta de gasto sin categoría elegida.
                on_click=AltaGastoState.abrir(""),
            ),
            rx.spacer(),
            width="100%",
            justify="between",
            align="center",
            # spacing="9",
        ),
    )