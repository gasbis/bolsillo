"""Página de categorías y cuentas (/categorias), pensada para el móvil.

  ← Categorías
  [ Gastos | Ingresos | Cuentas ]
  (icono) Comida                 >
  (icono) Casa                   >
  (icono) Banco        1.234,56 € >
  ...
  [ + Añadir categoría ]

Tocar una fila abre el diálogo para cambiar el nombre y el icono o
eliminarla; "Añadir" abre el mismo diálogo vacío. Ver
states/categorias_state.py.
"""

import reflex as rx

from bolsillo.components.teclado import SIN_ZOOM, boton_borrar, cabecera_dialogo
from bolsillo.iconos import ICONOS
from bolsillo.states.categorias_state import (
    PESTANA_CUENTAS,
    PESTANA_GASTOS,
    PESTANA_INGRESOS,
    CategoriasState,
)


def _circulo_icono(icono, color) -> rx.Component:
    """Icono con el mismo aspecto que en el donut y el formulario de alta."""
    return rx.flex(
        rx.icon(tag=icono, color=color, size=20),
        width="2.6em",
        height="2.6em",
        flex_shrink="0",
        align="center",
        justify="center",
        border_radius="50%",
        border=f"2px solid {color}",
        background_color=f"{color}1A",
    )


# --- Cabecera y pestañas ----------------------------------------------------


def _cabecera() -> rx.Component:
    return rx.flex(
        rx.icon_button(
            rx.icon(tag="arrow-left", size=20),
            on_click=rx.redirect("/"),
            variant="ghost",
            color_scheme="gray",
            custom_attrs={"aria-label": "Volver"},
        ),
        rx.heading("Categorías", size="4"),
        align="center",
        spacing="3",
        width="100%",
        padding_x="1em",
        padding_y="0.75em",
    )


def _pestanas() -> rx.Component:
    return rx.box(
        rx.segmented_control.root(
            rx.segmented_control.item("Gastos", value=PESTANA_GASTOS),
            rx.segmented_control.item("Ingresos", value=PESTANA_INGRESOS),
            rx.segmented_control.item("Cuentas", value=PESTANA_CUENTAS),
            value=CategoriasState.pestana,
            on_change=CategoriasState.set_pestana,
            size="2",
            width="100%",
        ),
        width="100%",
        padding_x="1em",
        padding_bottom="0.5em",
    )


# --- Lista ------------------------------------------------------------------


def _fila(e: rx.Var) -> rx.Component:
    return rx.flex(
        _circulo_icono(e["icono"].to(str), e["color"].to(str)),
        rx.text(
            e["nombre"],
            size="3",
            flex="1",
            min_width="0",
            overflow="hidden",
            text_overflow="ellipsis",
            white_space="nowrap",
        ),
        rx.cond(
            e["detalle"] != "",
            rx.text(
                e["detalle"],
                size="2",
                white_space="nowrap",
                color=rx.cond(e["negativo"] != "", "var(--red-11)", "var(--gray-11)"),
            ),
        ),
        rx.icon(tag="chevron-right", size=18, color="var(--gray-8)", flex_shrink="0"),
        on_click=CategoriasState.abrir_edicion(e["id"]),
        align="center",
        spacing="3",
        width="100%",
        padding_x="1em",
        padding_y="0.6em",
        border_bottom="1px solid var(--gray-a4)",
        cursor="pointer",
        role="button",
        _hover={"background_color": "var(--gray-a2)"},
        _active={"background_color": "var(--gray-a3)"},
        style=SIN_ZOOM,
    )


def _lista() -> rx.Component:
    return rx.cond(
        ~CategoriasState.cargado,
        rx.center(rx.spinner(size="3"), padding="3em", width="100%"),
        rx.cond(
            CategoriasState.lista.length() > 0,
            rx.flex(
                rx.foreach(CategoriasState.lista, _fila),
                direction="column",
                width="100%",
            ),
            rx.center(
                rx.text(CategoriasState.texto_vacio, size="2", color_scheme="gray"),
                padding="3em 1em",
                width="100%",
            ),
        ),
    )


def _boton_anadir() -> rx.Component:
    return rx.box(
        rx.button(
            rx.icon(tag="plus", size=20),
            CategoriasState.texto_anadir,
            on_click=CategoriasState.abrir_nueva,
            size="3",
            width="100%",
            style=SIN_ZOOM,
        ),
        width="100%",
        padding="0.75em 1em",
        border_top="1px solid var(--gray-a5)",
        flex_shrink="0",
    )


# --- Diálogo de alta / edición ----------------------------------------------


def _boton_icono(icono: str) -> rx.Component:
    elegido = CategoriasState.icono == icono
    return rx.icon_button(
        rx.icon(tag=icono, size=20),
        on_click=CategoriasState.set_icono(icono),
        type="button",
        size="3",
        variant=rx.cond(elegido, "solid", "soft"),
        color_scheme=rx.cond(elegido, "blue", "gray"),
        custom_attrs={"aria-label": icono},
        style=SIN_ZOOM,
    )


def _vista_previa() -> rx.Component:
    """Icono elegido (con el color de la categoría si ya lo tiene) y el
    nombre."""
    return rx.flex(
        rx.cond(
            CategoriasState.icono == "",
            rx.flex(
                rx.icon(tag="image", size=22, color="var(--gray-8)"),
                width="2.6em",
                height="2.6em",
                flex_shrink="0",
                align="center",
                justify="center",
                border_radius="50%",
                border="2px dashed var(--gray-7)",
            ),
            rx.cond(
                CategoriasState.color != "",
                _circulo_icono(CategoriasState.icono, CategoriasState.color),
                _circulo_icono(CategoriasState.icono, "#64748b"),
            ),
        ),
        rx.input(
            value=CategoriasState.nombre,
            on_change=CategoriasState.set_nombre,
            placeholder=rx.cond(CategoriasState.es_cuenta, "Nombre de la cuenta", "Nombre de la categoría"),
            auto_complete=False,
            max_length=40,
            size="3",
            flex="1",
        ),
        align="center",
        spacing="2",
        width="100%",
    )


def _campo_saldo_inicial() -> rx.Component:
    """Solo al crear una cuenta: después el saldo se corrige con
    "ajustar saldo" (que deja el movimiento anotado)."""
    return rx.cond(
        CategoriasState.es_cuenta & ~CategoriasState.es_edicion,
        rx.flex(
            rx.text("Saldo inicial", size="1", weight="bold", color_scheme="gray", flex_shrink="0"),
            rx.input(
                value=CategoriasState.saldo_inicial,
                on_change=CategoriasState.set_saldo_inicial,
                placeholder="0,00",
                input_mode="decimal",
                auto_complete=False,
                size="2",
                flex="1",
                text_align="right",
            ),
            rx.text("€", size="2"),
            align="center",
            spacing="2",
            width="100%",
        ),
    )


def _dialogo() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            cabecera_dialogo(CategoriasState.titulo),
            rx.flex(
                _vista_previa(),
                _campo_saldo_inicial(),
                rx.text("Icono", size="1", weight="bold", color_scheme="gray"),
                rx.grid(
                    *[_boton_icono(i) for i in ICONOS],
                    columns="repeat(auto-fill, minmax(2.8em, 1fr))",
                    spacing="2",
                    width="100%",
                    max_height="40dvh",
                    overflow_y="auto",
                    padding="0.25em",
                ),
                rx.cond(
                    CategoriasState.error != "",
                    rx.callout(CategoriasState.error, color_scheme="red", size="1", width="100%"),
                ),
                rx.button(
                    rx.icon(tag="check", size=20),
                    rx.cond(CategoriasState.es_edicion, "Guardar", "Crear"),
                    on_click=CategoriasState.guardar,
                    disabled=~CategoriasState.puede_guardar,
                    type="button",
                    size="4",
                    width="100%",
                    style=SIN_ZOOM,
                ),
                boton_borrar(CategoriasState),
                rx.cond(
                    CategoriasState.confirmar_borrado,
                    rx.text(
                        "Si tiene movimientos no se borra: se archiva y sus movimientos se conservan.",
                        size="1",
                        color_scheme="gray",
                        text_align="center",
                    ),
                ),
                direction="column",
                spacing="3",
            ),
            max_width="420px",
            max_height="96dvh",
            overflow_y="auto",
            padding="1em",
        ),
        open=CategoriasState.abierto,
        on_open_change=CategoriasState.set_abierto,
    )


# --- Página -----------------------------------------------------------------


def categorias() -> rx.Component:
    """Ocupa el alto visible (100dvh): cabecera y pestañas arriba, botón
    de añadir abajo y la lista con scroll propio en medio."""
    return rx.flex(
        _cabecera(),
        _pestanas(),
        rx.divider(size="4"),
        rx.box(_lista(), flex="1", min_height="0", overflow_y="auto", width="100%"),
        _boton_anadir(),
        _dialogo(),
        direction="column",
        height="100dvh",
        width="100%",
        max_width="600px",
        margin_x="auto",
        on_mount=CategoriasState.cargar,
    )
