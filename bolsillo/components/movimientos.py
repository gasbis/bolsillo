"""Diálogo con el listado de movimientos del periodo (ver
states/movimientos_state.py).

Cada grupo (categoría o día) es un <details>: desplegar y plegar lo
hace el propio navegador, al instante y sin ir al servidor, y se pueden
tener varios abiertos a la vez. La lista tiene su propio scroll; la
cabecera (título, periodo y selector de agrupación) se queda fija.

Tocar un movimiento abre su formulario para editarlo o borrarlo (ver
MovimientosState.editar).
"""

import reflex as rx

from bolsillo.components.teclado import cabecera_dialogo
from bolsillo.states.movimientos_state import (
    AGRUPAR_CATEGORIA,
    AGRUPAR_FECHA,
    GRIS,
    VERDE,
    MovimientosState,
)

_CSS = """
.grupo-mov > summary { list-style: none; cursor: pointer;
  -webkit-tap-highlight-color: transparent; user-select: none; }
.grupo-mov > summary::-webkit-details-marker { display: none; }
.grupo-mov > summary .chevron-mov { transition: transform 150ms; }
.grupo-mov[open] > summary .chevron-mov { transform: rotate(90deg); }
.grupo-mov + .grupo-mov { border-top: 1px solid var(--gray-a4); }
.linea-mov { cursor: pointer; -webkit-tap-highlight-color: transparent;
  user-select: none; border-radius: 0.4em; transition: background 120ms; }
.linea-mov:active { background: var(--gray-a3); }
@media (hover: hover) { .linea-mov:hover { background: var(--gray-a2); } }
"""


def _circulo_icono(icono, color, tam: str = "2.4em", px: int = 18) -> rx.Component:
    """Mismo aspecto que los iconos del donut y del formulario de alta."""
    return rx.flex(
        rx.icon(tag=icono, color=color, size=px),
        width=tam,
        height=tam,
        flex_shrink="0",
        align="center",
        justify="center",
        border_radius="50%",
        border=f"2px solid {color}",
        background_color=f"{color}1A",
    )


def _textos(titulo, detalle) -> rx.Component:
    return rx.flex(
        rx.text(
            titulo,
            size="2",
            weight="medium",
            trim="both",
            white_space="nowrap",
            overflow="hidden",
            text_overflow="ellipsis",
        ),
        rx.cond(
            detalle != "",
            rx.text(
                detalle,
                size="1",
                color_scheme="gray",
                white_space="nowrap",
                overflow="hidden",
                text_overflow="ellipsis",
            ),
        ),
        direction="column",
        spacing="1",
        flex="1",
        min_width="0",
    )


def _linea(linea) -> rx.Component:
    """Un movimiento dentro de un grupo desplegado (sin colores en el
    importe). Tocarlo lo abre para editarlo."""
    return rx.flex(
        rx.cond(
            linea.icono != "",
            _circulo_icono(linea.icono, linea.color, tam="1.9em", px=14),
        ),
        _textos(linea.titulo, linea.detalle),
        rx.text(linea.importe, size="2", white_space="nowrap", flex_shrink="0"),
        rx.icon(tag="pencil", size=13, color="var(--gray-8)", flex_shrink="0"),
        on_click=MovimientosState.editar(linea.id, linea.tipo, linea.clave_grupo),
        class_name="linea-mov",
        role="button",
        align="center",
        spacing="3",
        padding_y="0.45em",
        padding_x="0.5em",
        border_top="1px solid var(--gray-a3)",
    )


def _grupo(grupo) -> rx.Component:
    """Fila plegable de una categoría o de un día."""
    return rx.el.details(
        rx.el.summary(
            rx.flex(
                rx.icon(tag="chevron-right", size=16, color="var(--gray-9)", class_name="chevron-mov"),
                rx.cond(grupo.icono != "", _circulo_icono(grupo.icono, grupo.color)),
                _textos(grupo.titulo, grupo.detalle),
                rx.text(
                    grupo.importe,
                    size="3",
                    weight="bold",
                    white_space="nowrap",
                    flex_shrink="0",
                    # Verde/rojo; gris para las transferencias con todas
                    # las cuentas (se anulan y no suman ni restan).
                    color_scheme=rx.match(grupo.tono, (VERDE, "green"), (GRIS, "gray"), "red"),
                ),
                align="center",
                spacing="2",
                padding_y="0.6em",
            ),
        ),
        rx.box(
            rx.foreach(grupo.lineas, _linea),
            padding_left="1.6em",
            padding_bottom="0.4em",
        ),
        class_name="grupo-mov",
        # Al volver de editar un movimiento, su grupo sale desplegado.
        open=grupo.clave == MovimientosState.desplegado,
        id="grupo-" + grupo.clave,
        # Al cambiar de agrupación los <details> son otros: no heredan
        # los desplegados de la otra vista.
        key=grupo.clave,
    )


def _selector_agrupacion() -> rx.Component:
    return rx.segmented_control.root(
        rx.segmented_control.item(
            rx.flex(rx.icon(tag="layout-grid", size=14), "Categorías", align="center", spacing="1"),
            value=AGRUPAR_CATEGORIA,
        ),
        rx.segmented_control.item(
            rx.flex(rx.icon(tag="calendar-days", size=14), "Fechas", align="center", spacing="1"),
            value=AGRUPAR_FECHA,
        ),
        value=MovimientosState.agrupacion,
        on_change=MovimientosState.set_agrupacion,
        size="2",
        width="100%",
    )


def _lista() -> rx.Component:
    return rx.cond(
        MovimientosState.vacio,
        rx.text(
            "No hay movimientos en este periodo.",
            size="2",
            color_scheme="gray",
            text_align="center",
            padding_y="2em",
        ),
        rx.cond(
            MovimientosState.agrupado_por_fecha,
            rx.box(rx.foreach(MovimientosState.por_fecha, _grupo)),
            rx.box(rx.foreach(MovimientosState.por_categoria, _grupo)),
        ),
    )


def dialogo_movimientos() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.el.style(_CSS),
            cabecera_dialogo("Movimientos"),
            rx.text(
                MovimientosState.texto_periodo,
                " · ",
                MovimientosState.cuenta,
                size="2",
                color_scheme="gray",
                padding_bottom="0.6em",
            ),
            _selector_agrupacion(),
            # Solo la lista hace scroll; la cabecera se queda fija.
            rx.box(
                _lista(),
                flex="1 1 auto",
                min_height="0",
                overflow_y="auto",
                margin_top="0.6em",
                padding_right="0.25em",
                style={"overscroll_behavior": "contain", "-webkit-overflow-scrolling": "touch"},
            ),
            display="flex",
            flex_direction="column",
            max_width="420px",
            max_height="90dvh",
            padding="1em",
        ),
        open=MovimientosState.abierto,
        on_open_change=MovimientosState.set_abierto,
    )
