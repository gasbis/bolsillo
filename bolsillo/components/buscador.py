"""Diálogo del buscador de movimientos (lupa de la cabecera; ver
states/buscador_state.py).

Arriba, fijos, el campo de búsqueda y el número de coincidencias;
debajo, la lista de resultados con su propio scroll, del más reciente al
más antiguo. Tocar un resultado lo abre para editarlo o borrarlo.
"""

import reflex as rx

from bolsillo.components.teclado import cabecera_dialogo
from bolsillo.states.buscador_state import GRIS, VERDE, BuscadorState

_CSS = """
.res-busq { cursor: pointer; -webkit-tap-highlight-color: transparent;
  user-select: none; border-radius: 0.4em; transition: background 120ms; }
.res-busq:active { background: var(--gray-a3); }
@media (hover: hover) { .res-busq:hover { background: var(--gray-a2); } }
.res-busq + .res-busq { border-top: 1px solid var(--gray-a3); }
"""


def _circulo_icono(icono, color) -> rx.Component:
    """Mismo aspecto que los iconos del listado de movimientos."""
    return rx.flex(
        rx.icon(tag=icono, color=color, size=16),
        width="2.2em",
        height="2.2em",
        flex_shrink="0",
        align="center",
        justify="center",
        border_radius="50%",
        border=f"2px solid {color}",
        background_color=f"{color}1A",
    )


def _resultado(r) -> rx.Component:
    return rx.flex(
        _circulo_icono(r.icono, r.color),
        rx.flex(
            rx.text(
                r.titulo,
                size="2",
                weight="medium",
                white_space="nowrap",
                overflow="hidden",
                text_overflow="ellipsis",
            ),
            rx.text(
                r.detalle,
                size="1",
                color_scheme="gray",
                white_space="nowrap",
                overflow="hidden",
                text_overflow="ellipsis",
            ),
            direction="column",
            spacing="1",
            flex="1",
            min_width="0",
        ),
        rx.text(
            r.importe,
            size="2",
            weight="bold",
            white_space="nowrap",
            flex_shrink="0",
            color_scheme=rx.match(r.tono, (VERDE, "green"), (GRIS, "gray"), "red"),
        ),
        rx.icon(tag="pencil", size=13, color="var(--gray-8)", flex_shrink="0"),
        on_click=BuscadorState.editar(r.id, r.tipo),
        class_name="res-busq",
        id="res-" + r.id,
        key=r.id,
        role="button",
        align="center",
        spacing="3",
        padding_y="0.5em",
        padding_x="0.4em",
    )


def _campo_busqueda() -> rx.Component:
    return rx.input(
        rx.input.slot(rx.icon(tag="search", size=16)),
        rx.cond(
            BuscadorState.consulta != "",
            rx.input.slot(
                rx.icon_button(
                    rx.icon(tag="x", size=14),
                    type="button",
                    size="1",
                    variant="ghost",
                    color_scheme="gray",
                    on_click=BuscadorState.limpiar,
                    custom_attrs={"aria-label": "Borrar búsqueda"},
                ),
            ),
        ),
        value=BuscadorState.consulta,
        on_change=BuscadorState.set_consulta,
        # Busca al dejar de escribir, no con cada letra.
        debounce_timeout=350,
        placeholder="Categoría, notas o importe",
        type="search",
        auto_focus=True,
        auto_complete=False,
        # 16px: por debajo, Safari en iPhone hace zoom al enfocar.
        size="3",
        font_size="16px",
        width="100%",
        custom_attrs={"aria-label": "Buscar movimientos", "enterKeyHint": "search"},
    )


def _ayuda() -> rx.Component:
    return rx.flex(
        rx.text("Busca en todos los movimientos, de cualquier fecha y cuenta.", size="2"),
        rx.text(
            "Por categoría o notas (sin importar acentos ni mayúsculas; con varias "
            "palabras tienen que salir todas) o por importe: «12,50» exacto, "
            "«12» de 12,00 a 12,99 €.",
            size="1",
            color_scheme="gray",
        ),
        direction="column",
        spacing="2",
        padding_y="1.5em",
        padding_x="0.5em",
        text_align="center",
        align="center",
    )


def _lista() -> rx.Component:
    return rx.cond(
        BuscadorState.buscado,
        rx.box(rx.foreach(BuscadorState.resultados, _resultado)),
        _ayuda(),
    )


def dialogo_buscador() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.el.style(_CSS),
            cabecera_dialogo("Buscar"),
            _campo_busqueda(),
            rx.text(
                BuscadorState.texto_total,
                size="1",
                color_scheme="gray",
                min_height="1.2em",
                padding_top="0.4em",
            ),
            # Solo la lista hace scroll; el campo se queda fijo.
            rx.box(
                _lista(),
                flex="1 1 auto",
                min_height="0",
                overflow_y="auto",
                margin_top="0.3em",
                padding_right="0.25em",
                style={"overscroll_behavior": "contain", "-webkit-overflow-scrolling": "touch"},
            ),
            display="flex",
            flex_direction="column",
            max_width="420px",
            # Alto fijo (no máximo): que no salte al cambiar los resultados
            # ni al abrirse el teclado del móvil.
            height="85dvh",
            padding="1em",
        ),
        open=BuscadorState.abierto,
        on_open_change=BuscadorState.set_abierto,
    )
