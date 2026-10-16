"""Diálogo de alta de un gasto o de un ingreso, pensado para el móvil.
Los dos son iguales; solo cambian el título, las categorías que se
ofrecen y que un ingreso no admite importes negativos (ver
AltaGastoState.tipo).

Vista "formulario", de arriba abajo:
  fecha (hoy) · cuenta · importe · notas · teclado numérico · botón final.
El botón final es "Elegir categoría" (abre la vista "categorias") o, si
la categoría ya está elegida, su icono y nombre con "Aceptar". En ambos
casos solo se activa con un importe distinto de 0.

Vista "categorias": rejilla con las categorías (de gasto o de
ingreso) y "Nueva".
Vista "nueva": nombre e icono de una categoría nueva.

Al editar un movimiento (desde el listado) el formulario es el mismo,
con el título "Editar ..." y un botón "Eliminar" al final.

Las tres comparten el mismo diálogo (rx.cond) en vez de abrir diálogos
encima de otros, que en el móvil se comportan mal.
"""

import reflex as rx

from bolsillo.components.teclado import (
    SIN_ZOOM as _SIN_ZOOM,
    boton_borrar,
    cabecera_dialogo,
    campo_importe,
    fila,
    teclado,
)
from bolsillo.iconos import ICONOS
from bolsillo.states.alta_gasto_state import (
    VISTA_CATEGORIAS,
    VISTA_NUEVA,
    AltaGastoState,
)


def _circulo_icono(icono: rx.Var, color: rx.Var) -> rx.Component:
    """Icono de categoría con el mismo aspecto que en el donut."""
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


# --- Vista formulario -------------------------------------------------------


def _selector_cuenta() -> rx.Component:
    return rx.cond(
        AltaGastoState.sin_cuentas,
        rx.callout("Primero tienes que crear una cuenta.", color_scheme="amber", size="1", width="100%"),
        rx.select.root(
            rx.select.trigger(placeholder="Elige cuenta", width="100%"),
            rx.select.content(
                rx.foreach(
                    AltaGastoState.cuentas,
                    lambda o: rx.select.item(o["nombre"], value=o["id"]),
                ),
            ),
            value=AltaGastoState.id_cuenta_alta,
            on_change=AltaGastoState.set_id_cuenta_alta,
            size="2",
        ),
    )


def _boton_final() -> rx.Component:
    """'Elegir categoría' o, con la categoría ya elegida, su icono y
    nombre para aceptar (y un botón al lado para cambiarla)."""
    categoria = AltaGastoState.categoria_elegida
    return rx.cond(
        AltaGastoState.hay_categoria,
        rx.flex(
            rx.button(
                rx.icon(tag=categoria["icono"].to(str), size=22),
                rx.text(
                    categoria["nombre"],
                    overflow="hidden",
                    text_overflow="ellipsis",
                    white_space="nowrap",
                ),
                rx.spacer(),
                rx.text("Aceptar", weight="bold"),
                rx.icon(tag="check", size=22),
                on_click=AltaGastoState.guardar,
                disabled=~AltaGastoState.importe_valido,
                type="button",
                size="4",
                flex="1",
                min_width="0",
                color="white",
                background_color=rx.cond(
                    AltaGastoState.importe_valido, categoria["color"].to(str), "var(--gray-a6)"
                ),
                style=_SIN_ZOOM,
            ),
            rx.icon_button(
                rx.icon(tag="layout-grid", size=22),
                on_click=AltaGastoState.ver_categorias,
                type="button",
                size="4",
                variant="soft",
                color_scheme="gray",
                custom_attrs={"aria-label": "Cambiar categoría"},
            ),
            spacing="2",
            width="100%",
        ),
        rx.button(
            rx.icon(tag="layout-grid", size=22),
            "Elegir categoría",
            on_click=AltaGastoState.ver_categorias,
            disabled=~AltaGastoState.importe_valido,
            type="button",
            size="4",
            width="100%",
            style=_SIN_ZOOM,
        ),
    )


def _vista_formulario() -> rx.Component:
    return rx.flex(
        fila(
            "Fecha",
            rx.input(
                type="date",
                value=AltaGastoState.fecha_alta,
                on_change=AltaGastoState.set_fecha_alta,
                size="2",
                flex="1",
            ),
        ),
        fila("Cuenta", rx.box(_selector_cuenta(), flex="1", min_width="0")),
        campo_importe(AltaGastoState),
        rx.input(
            value=AltaGastoState.notas,
            on_change=AltaGastoState.set_notas,
            placeholder="Notas (opcional)",
            auto_complete=False,
            size="2",
            width="100%",
        ),
        rx.cond(
            AltaGastoState.error != "",
            rx.callout(AltaGastoState.error, color_scheme="red", size="1", width="100%"),
        ),
        teclado(AltaGastoState),
        _boton_final(),
        boton_borrar(AltaGastoState),
        direction="column",
        spacing="2",
    )


# --- Vista selector de categorías -------------------------------------------


def _casilla(contenido: rx.Component, nombre, al_pulsar, resaltada=False) -> rx.Component:
    return rx.flex(
        contenido,
        rx.text(
            nombre,
            size="1",
            text_align="center",
            line_height="1.2",
            style={
                "display": "-webkit-box",
                "-webkit-line-clamp": "2",
                "-webkit-box-orient": "vertical",
                "overflow": "hidden",
                "word-break": "break-word",
            },
        ),
        on_click=al_pulsar,
        direction="column",
        align="center",
        spacing="1",
        padding="0.4em 0.1em",
        border_radius="var(--radius-3)",
        background_color=rx.cond(resaltada, "var(--accent-a4)", "transparent"),
        cursor="pointer",
        role="button",
        style=_SIN_ZOOM,
    )


def _casilla_categoria(c: rx.Var) -> rx.Component:
    return _casilla(
        _circulo_icono(c["icono"].to(str), c["color"].to(str)),
        c["nombre"],
        AltaGastoState.elegir_categoria(c["id"]),
        resaltada=c["id"] == AltaGastoState.id_categoria,
    )


def _casilla_nueva() -> rx.Component:
    return _casilla(
        rx.flex(
            rx.icon(tag="plus", size=20),
            width="2.6em",
            height="2.6em",
            align="center",
            justify="center",
            border_radius="50%",
            border="2px dashed var(--gray-8)",
            color="var(--gray-11)",
        ),
        "Nueva",
        AltaGastoState.ver_nueva,
    )


def _cabecera(titulo, volver, derecha=None) -> rx.Component:
    return rx.flex(
        rx.icon_button(
            rx.icon(tag="arrow-left", size=20),
            on_click=volver,
            type="button",
            variant="ghost",
            color_scheme="gray",
            custom_attrs={"aria-label": "Volver"},
        ),
        rx.dialog.title(titulo, size="4", margin="0"),
        rx.spacer(),
        derecha if derecha is not None else rx.fragment(),
        align="center",
        spacing="3",
        width="100%",
        padding_bottom="0.5em",
    )


def _vista_categorias() -> rx.Component:
    return rx.flex(
        _cabecera(
            "Elegir categoría",
            AltaGastoState.ver_formulario,
            rx.text(AltaGastoState.texto_importe, weight="bold"),
        ),
        rx.grid(
            rx.foreach(AltaGastoState.opciones_categorias, _casilla_categoria),
            _casilla_nueva(),
            columns="4",
            spacing="2",
            width="100%",
        ),
        direction="column",
        spacing="2",
    )


# --- Vista categoría nueva --------------------------------------------------


def _boton_icono(icono: str) -> rx.Component:
    return rx.icon_button(
        rx.icon(tag=icono, size=20),
        on_click=AltaGastoState.set_nuevo_icono(icono),
        type="button",
        size="3",
        variant=rx.cond(AltaGastoState.nuevo_icono == icono, "solid", "soft"),
        color_scheme=rx.cond(AltaGastoState.nuevo_icono == icono, "blue", "gray"),
        custom_attrs={"aria-label": icono},
        style=_SIN_ZOOM,
    )


def _vista_nueva() -> rx.Component:
    return rx.flex(
        _cabecera("Nueva categoría", AltaGastoState.ver_categorias),
        rx.flex(
            rx.flex(
                rx.cond(
                    AltaGastoState.nuevo_icono != "",
                    rx.icon(tag=AltaGastoState.nuevo_icono, size=22),
                    rx.icon(tag="image", size=22, color="var(--gray-8)"),
                ),
                width="2.6em",
                height="2.6em",
                flex_shrink="0",
                align="center",
                justify="center",
                border_radius="50%",
                border="2px solid var(--gray-7)",
            ),
            rx.input(
                value=AltaGastoState.nuevo_nombre,
                on_change=AltaGastoState.set_nuevo_nombre,
                placeholder="Nombre de la categoría",
                auto_complete=False,
                max_length=40,
                size="3",
                flex="1",
            ),
            align="center",
            spacing="2",
            width="100%",
        ),
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
            AltaGastoState.error_nueva != "",
            rx.callout(AltaGastoState.error_nueva, color_scheme="red", size="1", width="100%"),
        ),
        rx.button(
            rx.icon(tag="check", size=20),
            "Crear y elegir",
            on_click=AltaGastoState.crear_categoria,
            disabled=(AltaGastoState.nuevo_nombre.strip() == "") | (AltaGastoState.nuevo_icono == ""),
            type="button",
            size="4",
            width="100%",
        ),
        direction="column",
        spacing="3",
    )


# --- Diálogo ----------------------------------------------------------------


def dialogo_alta_gasto() -> rx.Component:
    """Diálogo único para gastos e ingresos."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.match(
                AltaGastoState.vista,
                (VISTA_CATEGORIAS, _vista_categorias()),
                (VISTA_NUEVA, _vista_nueva()),
                rx.flex(
                    cabecera_dialogo(AltaGastoState.titulo),
                    _vista_formulario(),
                    direction="column",
                ),
            ),
            max_width="420px",
            max_height="96dvh",
            overflow_y="auto",
            padding="1em",
        ),
        open=AltaGastoState.abierto,
        on_open_change=AltaGastoState.set_abierto,
    )
