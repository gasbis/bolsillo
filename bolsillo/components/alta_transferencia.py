"""Diálogo de alta de una transferencia, pensado para el móvil.

De arriba abajo:
  fecha (hoy) · importe · cuenta de origen · flecha ↓ · cuenta de destino
  · teclado numérico · Aceptar.

La flecha entre las cuentas se puede tocar para intercambiarlas.
"""

import reflex as rx

from bolsillo.components.teclado import (
    SIN_ZOOM,
    cabecera_dialogo,
    campo_importe,
    fila,
    teclado,
)
from bolsillo.states.alta_transferencia_state import AltaTransferenciaState as S


def _selector_cuenta(valor, al_cambiar, texto_vacio: str) -> rx.Component:
    return rx.select.root(
        rx.select.trigger(placeholder=texto_vacio, width="100%"),
        rx.select.content(
            rx.foreach(
                S.cuentas,
                lambda o: rx.select.item(o["nombre"], value=o["id"]),
            ),
        ),
        value=valor,
        on_change=al_cambiar,
        size="3",
    )


def _flecha() -> rx.Component:
    return rx.flex(
        rx.icon_button(
            rx.icon(tag="arrow-down", size=24),
            on_click=S.intercambiar,
            type="button",
            size="3",
            variant="soft",
            color_scheme="gray",
            radius="full",
            custom_attrs={"aria-label": "Intercambiar cuentas"},
            style=SIN_ZOOM,
        ),
        justify="center",
        width="100%",
    )


def _cuentas() -> rx.Component:
    return rx.cond(
        S.pocas_cuentas,
        rx.callout(
            "Necesitas al menos dos cuentas para hacer una transferencia.",
            color_scheme="amber",
            size="1",
            width="100%",
        ),
        rx.flex(
            fila("Origen", rx.box(_selector_cuenta(S.id_origen, S.set_id_origen, "Cuenta de origen"), flex="1", min_width="0")),
            _flecha(),
            fila("Destino", rx.box(_selector_cuenta(S.id_destino, S.set_id_destino, "Cuenta de destino"), flex="1", min_width="0")),
            rx.cond(
                S.misma_cuenta,
                rx.text(
                    "El origen y el destino tienen que ser distintos.",
                    size="1",
                    color_scheme="red",
                    text_align="center",
                    width="100%",
                ),
            ),
            direction="column",
            spacing="1",
            width="100%",
        ),
    )


def _vista_formulario() -> rx.Component:
    return rx.flex(
        fila(
            "Fecha",
            rx.input(
                type="date",
                value=S.fecha_alta,
                on_change=S.set_fecha_alta,
                size="2",
                flex="1",
            ),
        ),
        campo_importe(S),
        _cuentas(),
        rx.cond(
            S.error != "",
            rx.callout(S.error, color_scheme="red", size="1", width="100%"),
        ),
        teclado(S),
        rx.button(
            rx.icon(tag="arrow-left-right", size=22),
            "Aceptar",
            on_click=S.guardar,
            disabled=~S.se_puede_guardar,
            type="button",
            size="4",
            width="100%",
            style=SIN_ZOOM,
        ),
        direction="column",
        spacing="2",
    )


def dialogo_alta_transferencia() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.flex(
                cabecera_dialogo("Nueva transferencia"),
                _vista_formulario(),
                direction="column",
            ),
            max_width="420px",
            max_height="96dvh",
            overflow_y="auto",
            padding="1em",
        ),
        open=S.abierto,
        on_open_change=S.set_abierto,
    )
