"""Piezas comunes de los formularios de alta (gasto, ingreso y
transferencia): campo del importe con su resultado debajo, teclado
numérico de calculadora y filas "etiqueta + campo".

Reciben el state del formulario, que tiene que tener:
- `expresion` (str) y `texto_resultado` (var str),
- eventos `set_expresion(valor)` y `tecla(tecla)`.
La lógica de las teclas vive en calculadora.py.
"""

import reflex as rx

from bolsillo import calculadora

SIN_ZOOM = {
    # Que tocar rápido dos teclas no haga zoom ni seleccione texto.
    "touch_action": "manipulation",
    "user_select": "none",
    "-webkit-tap-highlight-color": "transparent",
}


def etiqueta(texto: str) -> rx.Component:
    return rx.text(texto, size="1", weight="bold", color_scheme="gray", width="4.5em", flex_shrink="0")


def fila(texto: str, campo: rx.Component) -> rx.Component:
    return rx.flex(etiqueta(texto), campo, align="center", spacing="2", width="100%")


def campo_importe(estado) -> rx.Component:
    return rx.box(
        rx.input(
            value=estado.expresion,
            on_change=estado.set_expresion,
            placeholder="0,00",
            type="text",
            # Sin teclado del sistema en el móvil: se usa el de abajo.
            # Con un teclado físico (ordenador) se puede escribir igual.
            input_mode="none",
            auto_complete=False,
            size="3",
            font_size="1.6em",
            font_weight="bold",
            text_align="right",
            width="100%",
            custom_attrs={"aria-label": "Importe"},
        ),
        rx.text(
            estado.texto_resultado,
            size="2",
            color_scheme="gray",
            text_align="right",
            min_height="1.4em",
            padding_top="0.15em",
        ),
        width="100%",
    )


def _tecla(estado, texto, tecla: str, tipo: str = "numero", **estilo) -> rx.Component:
    colores = {
        "numero": dict(variant="soft", color_scheme="gray"),
        "operador": dict(variant="soft", color_scheme="blue"),
        "accion": dict(variant="soft", color_scheme="orange"),
        "igual": dict(variant="solid", color_scheme="blue"),
    }[tipo]
    return rx.button(
        texto,
        on_click=estado.tecla(tecla),
        type="button",
        size="3",
        height="100%",
        min_height="2.9em",
        font_size="1.25em",
        font_weight="bold" if tipo != "numero" else "medium",
        style=SIN_ZOOM,
        **colores,
        **estilo,
    )


def teclado(estado) -> rx.Component:
    """C  ⌫  ÷  ×
       7  8  9  −
       4  5  6  +
       1  2  3  =
       0     ,  ="""
    c = calculadora
    t = lambda *a, **k: _tecla(estado, *a, **k)  # noqa: E731
    return rx.grid(
        t("C", c.LIMPIAR, "accion"),
        t(rx.icon(tag="delete", size=22), c.BORRAR, "accion", custom_attrs={"aria-label": "Borrar"}),
        t("÷", c.ENTRE, "operador"),
        t("×", c.POR, "operador"),
        *[t(n, n) for n in "789"],
        t("−", c.RESTA, "operador"),
        *[t(n, n) for n in "456"],
        t("+", c.SUMA, "operador"),
        *[t(n, n) for n in "123"],
        t("=", c.IGUAL, "igual", grid_row="span 2"),
        t("0", "0", grid_column="span 2"),
        t(",", c.COMA),
        columns="4",
        spacing="2",
        width="100%",
    )


def cabecera_dialogo(titulo) -> rx.Component:
    """Título del diálogo con la X de cerrar."""
    return rx.flex(
        rx.dialog.title(titulo, size="4", margin="0"),
        rx.spacer(),
        rx.dialog.close(
            rx.icon_button(
                rx.icon(tag="x", size=20),
                type="button",
                variant="ghost",
                color_scheme="gray",
                custom_attrs={"aria-label": "Cerrar"},
            )
        ),
        align="center",
        width="100%",
        padding_bottom="0.5em",
    )
