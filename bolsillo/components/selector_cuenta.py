"""Selector de cuenta común al filtro de la pantalla principal y a los
formularios de gasto, ingreso y transferencia.

Al desplegarlo, cada cuenta sale con su icono, su nombre y su saldo
actual (en rojo si es negativo). Ya elegida, en el selector solo se ve
el nombre.

Cómo: Radix pinta en el selector una copia del contenido de la opción
elegida, así que el icono y el saldo llevan la clase `solo-lista` y el
CSS del trigger los oculta ahí.
"""

import reflex as rx

from bolsillo.states.categorias_state import COLOR_CUENTA

_SOLO_LISTA = "solo-lista"


def _icono(tag: rx.Var) -> rx.Component:
    """Mismo aspecto que en la página de cuentas, algo más pequeño."""
    return rx.flex(
        rx.icon(tag=tag, color=COLOR_CUENTA, size=16),
        width="2em",
        height="2em",
        flex_shrink="0",
        align="center",
        justify="center",
        border_radius="50%",
        border=f"2px solid {COLOR_CUENTA}",
        background_color=f"{COLOR_CUENTA}1A",
        class_name=_SOLO_LISTA,
    )


def _opcion(o: rx.Var, clave: str) -> rx.Component:
    return rx.select.item(
        rx.flex(
            _icono(o["icono"].to(str)),
            rx.text(
                o["nombre"],
                flex="1",
                min_width="0",
                overflow="hidden",
                text_overflow="ellipsis",
                white_space="nowrap",
            ),
            rx.text(
                o["saldo"],
                size="2",
                white_space="nowrap",
                color=rx.cond(o["negativo"] != "", "var(--red-11)", "var(--gray-11)"),
                class_name=_SOLO_LISTA,
            ),
            align="center",
            spacing="3",
            width="100%",
        ),
        value=o[clave].to(str),
        # Más alto que una opción normal para que quepa el icono y el dedo.
        height="auto",
        padding_y="0.35em",
    )


def selector_cuenta(
    opciones,
    valor,
    al_cambiar,
    placeholder: str = "Elige cuenta",
    clave: str = "id",
    size: str = "2",
) -> rx.Component:
    """`opciones`: lista de {"id", "nombre", "icono", "saldo", "negativo"}
    (ver ResumenState.cuentas). `clave` es el campo que se usa como valor
    del selector ("id" en los formularios, "nombre" en el filtro)."""
    return rx.select.root(
        rx.select.trigger(
            placeholder=placeholder,
            width="100%",
            style={f"& .{_SOLO_LISTA}": {"display": "none"}},
        ),
        rx.select.content(
            rx.foreach(opciones, lambda o: _opcion(o, clave)),
            position="popper",
            # Que la lista sea al menos tan ancha como el selector y quepa
            # el saldo al lado del nombre.
            min_width="var(--radix-select-trigger-width)",
        ),
        value=valor,
        on_change=al_cambiar,
        size=size,
    )
