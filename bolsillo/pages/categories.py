"""Página de categorías y cuentas (/categorias), pensada para el móvil.

  ← Categorías
  [ Gastos | Ingresos | Cuentas ]
  (icono) Comida                    >
  (icono) Banco          1.234,56 € >
  (icono) Viejo banco  Archivada  0 € >   ← atenuada
  ...
  [ + Añadir categoría ]

Tocar una fila abre el diálogo; "Añadir" abre el mismo diálogo vacío.
Las vistas del diálogo y sus reglas están en states/categorias_state.py.
"""

import reflex as rx

from bolsillo.components.teclado import SIN_ZOOM, cabecera_dialogo
from bolsillo.iconos import ICONOS
from bolsillo.states.categorias_state import (
    PESTANA_CUENTAS,
    PESTANA_GASTOS,
    PESTANA_INGRESOS,
    VISTA_ARCHIVADA,
    VISTA_BORRAR,
    CategoriasState,
)

GRIS = "#64748b"


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


def _error() -> rx.Component:
    return rx.cond(
        CategoriasState.error != "",
        rx.callout(CategoriasState.error, color_scheme="red", size="1", width="100%"),
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
    archivada = e["archivada"] != ""
    return rx.flex(
        _circulo_icono(e["icono"].to(str), rx.cond(archivada, GRIS, e["color"].to(str))),
        rx.text(
            e["nombre"],
            size="3",
            flex="1",
            min_width="0",
            overflow="hidden",
            text_overflow="ellipsis",
            white_space="nowrap",
        ),
        rx.cond(archivada, rx.badge("Archivada", color_scheme="gray", variant="soft")),
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
        opacity=rx.cond(archivada, "0.5", "1"),
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


# --- Vista editar / crear ---------------------------------------------------


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
    """Icono elegido (con su color si ya lo tiene) y el nombre."""
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
                _circulo_icono(CategoriasState.icono, GRIS),
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


def _campo_saldo() -> rx.Component:
    """Cuentas: saldo inicial al crearla, saldo actual al editarla (su
    cambio anota un ajuste)."""
    return rx.cond(
        CategoriasState.es_cuenta,
        rx.flex(
            rx.flex(
                rx.text(
                    CategoriasState.etiqueta_saldo,
                    size="1",
                    weight="bold",
                    color_scheme="gray",
                    flex_shrink="0",
                    width="6.5em",
                ),
                rx.input(
                    value=CategoriasState.saldo,
                    on_change=CategoriasState.set_saldo,
                    placeholder="0,00",
                    input_mode="decimal",
                    auto_complete=False,
                    size="2",
                    flex="1",
                    text_align="right",
                ),
                rx.text("€", size="2"),
                rx.icon_button(
                    rx.icon(tag="diff", size=16),
                    on_click=CategoriasState.cambiar_signo_saldo,
                    type="button",
                    size="2",
                    variant="soft",
                    color_scheme="gray",
                    custom_attrs={"aria-label": "Cambiar signo"},
                    style=SIN_ZOOM,
                ),
                align="center",
                spacing="2",
                width="100%",
            ),
            rx.cond(
                CategoriasState.aviso_saldo != "",
                rx.text(CategoriasState.aviso_saldo, size="1", color_scheme="amber"),
            ),
            direction="column",
            spacing="1",
            width="100%",
        ),
    )


def _vista_editar() -> rx.Component:
    return rx.flex(
        _vista_previa(),
        _campo_saldo(),
        rx.text("Icono", size="1", weight="bold", color_scheme="gray"),
        rx.grid(
            *[_boton_icono(i) for i in ICONOS],
            columns="repeat(auto-fill, minmax(2.8em, 1fr))",
            spacing="2",
            width="100%",
            max_height="36dvh",
            overflow_y="auto",
            padding="0.25em",
        ),
        _error(),
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
        rx.cond(
            CategoriasState.es_edicion,
            rx.button(
                rx.icon(tag="trash-2", size=18),
                "Eliminar",
                on_click=CategoriasState.ver_borrar,
                type="button",
                size="2",
                width="100%",
                color_scheme="red",
                variant="soft",
                style=SIN_ZOOM,
            ),
        ),
        direction="column",
        spacing="3",
    )


# --- Vista cuenta archivada -------------------------------------------------


def _vista_archivada() -> rx.Component:
    e = CategoriasState.elemento
    return rx.flex(
        rx.flex(
            _circulo_icono(e["icono"].to(str), GRIS),
            rx.text(e["nombre"], size="4", weight="medium", flex="1", min_width="0"),
            rx.text(e["detalle"], size="2", color_scheme="gray", white_space="nowrap"),
            align="center",
            spacing="3",
            width="100%",
            opacity="0.6",
        ),
        rx.text(
            "Esta cuenta está archivada: no aparece en el resto de la app, pero "
            "sus movimientos se conservan. Restáurala para volver a usarla.",
            size="2",
            color_scheme="gray",
        ),
        _error(),
        rx.button(
            rx.icon(tag="archive-restore", size=20),
            "Restaurar cuenta",
            on_click=CategoriasState.restaurar,
            type="button",
            size="4",
            width="100%",
            style=SIN_ZOOM,
        ),
        rx.button(
            rx.icon(tag="trash-2", size=18),
            "Eliminar",
            on_click=CategoriasState.ver_borrar,
            type="button",
            size="2",
            width="100%",
            color_scheme="red",
            variant="soft",
            style=SIN_ZOOM,
        ),
        direction="column",
        spacing="3",
    )


# --- Vista eliminar ---------------------------------------------------------


def _fusion() -> rx.Component:
    """Categorías: elegir otra y pasarle los movimientos."""
    return rx.flex(
        rx.text("Fusionar con", size="1", weight="bold", color_scheme="gray"),
        rx.select.root(
            rx.select.trigger(placeholder="Elige una categoría", width="100%"),
            rx.select.content(
                rx.foreach(
                    CategoriasState.opciones_fusion,
                    lambda o: rx.select.item(o["nombre"], value=o["id"]),
                ),
            ),
            value=CategoriasState.id_fusion,
            on_change=CategoriasState.set_id_fusion,
            size="3",
        ),
        rx.button(
            rx.icon(tag="merge", size=20),
            "Fusionar y conservar movimientos",
            on_click=CategoriasState.fusionar,
            disabled=CategoriasState.id_fusion == "",
            type="button",
            size="3",
            width="100%",
            style=SIN_ZOOM,
        ),
        direction="column",
        spacing="2",
        width="100%",
    )


def _archivar() -> rx.Component:
    return rx.button(
        rx.icon(tag="archive", size=20),
        "Archivar y conservar movimientos",
        on_click=CategoriasState.archivar,
        type="button",
        size="3",
        width="100%",
        style=SIN_ZOOM,
    )


def _vista_borrar() -> rx.Component:
    return rx.flex(
        rx.flex(
            _circulo_icono(
                CategoriasState.icono,
                rx.cond(CategoriasState.color != "", CategoriasState.color, GRIS),
            ),
            rx.text(CategoriasState.elemento["nombre"], size="4", weight="medium"),
            align="center",
            spacing="3",
        ),
        rx.callout(
            CategoriasState.aviso_borrado,
            icon="triangle-alert",
            color_scheme=rx.cond(CategoriasState.n_movimientos > 0, "red", "gray"),
            size="1",
            width="100%",
        ),
        rx.cond(CategoriasState.puede_fusionar, _fusion()),
        rx.cond(CategoriasState.puede_archivar, _archivar()),
        _error(),
        rx.button(
            rx.icon(tag="trash-2", size=18),
            rx.cond(
                CategoriasState.n_movimientos > 0,
                "Eliminar definitivamente",
                "Eliminar",
            ),
            on_click=CategoriasState.borrar,
            type="button",
            size="3",
            width="100%",
            color_scheme="red",
            variant=rx.cond(CategoriasState.n_movimientos > 0, "outline", "solid"),
            style=SIN_ZOOM,
        ),
        rx.button(
            "Cancelar",
            on_click=CategoriasState.volver,
            type="button",
            size="2",
            width="100%",
            variant="ghost",
            color_scheme="gray",
        ),
        direction="column",
        spacing="3",
    )


# --- Diálogo y página -------------------------------------------------------


def _dialogo() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            cabecera_dialogo(CategoriasState.titulo),
            rx.match(
                CategoriasState.vista,
                (VISTA_BORRAR, _vista_borrar()),
                (VISTA_ARCHIVADA, _vista_archivada()),
                _vista_editar(),
            ),
            max_width="420px",
            max_height="96dvh",
            overflow_y="auto",
            padding="1em",
        ),
        open=CategoriasState.abierto,
        on_open_change=CategoriasState.set_abierto,
    )


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
