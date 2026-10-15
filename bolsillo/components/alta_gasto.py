"""Diálogo de alta rápida de un gasto. Se abre con una pulsación corta
sobre el icono de una categoría (ver components/donut.py)."""

import reflex as rx

from bolsillo.states.alta_gasto_state import AltaGastoState


def _etiqueta(texto: str) -> rx.Component:
    return rx.text(texto, size="1", weight="bold", color_scheme="gray")


def _selector(opciones, valor, al_cambiar, marcador: str) -> rx.Component:
    return rx.select.root(
        rx.select.trigger(placeholder=marcador, width="100%"),
        rx.select.content(
            rx.foreach(
                opciones,
                lambda o: rx.select.item(o["nombre"], value=o["id"]),
            ),
        ),
        value=valor,
        on_change=al_cambiar,
        size="3",
    )


def dialogo_alta_gasto() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Nuevo gasto"),
            rx.form(
                rx.flex(
                    _etiqueta("Importe"),
                    rx.input(
                        name="importe",
                        placeholder="0,00",
                        # Teclado numérico con coma decimal en el móvil.
                        type="text",
                        input_mode="decimal",
                        auto_complete=False,
                        auto_focus=True,
                        size="3",
                        font_size="1.4em",
                    ),
                    rx.text("Negativo si es una devolución.", size="1", color_scheme="gray"),
                    _etiqueta("Categoría"),
                    _selector(
                        AltaGastoState.opciones_categorias,
                        AltaGastoState.id_categoria,
                        AltaGastoState.set_id_categoria,
                        "Elige categoría",
                    ),
                    _etiqueta("Cuenta"),
                    rx.cond(
                        AltaGastoState.sin_cuentas,
                        rx.callout("Primero tienes que crear una cuenta.", color_scheme="amber", size="1"),
                        _selector(
                            AltaGastoState.cuentas,
                            AltaGastoState.id_cuenta_alta,
                            AltaGastoState.set_id_cuenta_alta,
                            "Elige cuenta",
                        ),
                    ),
                    _etiqueta("Fecha"),
                    rx.input(
                        name="fecha",
                        type="date",
                        default_value=AltaGastoState.fecha_alta,
                        size="3",
                    ),
                    _etiqueta("Notas"),
                    rx.input(name="notas", placeholder="Opcional", auto_complete=False, size="3"),
                    rx.cond(
                        AltaGastoState.error != "",
                        rx.callout(AltaGastoState.error, color_scheme="red", size="1"),
                    ),
                    rx.hstack(
                        rx.dialog.close(
                            rx.button("Cancelar", variant="soft", color_scheme="gray", type="button", size="3")
                        ),
                        rx.button("Guardar", type="submit", size="3"),
                        spacing="3",
                        justify="end",
                        width="100%",
                        padding_top="0.5em",
                    ),
                    direction="column",
                    spacing="2",
                ),
                on_submit=AltaGastoState.guardar,
                reset_on_submit=False,
            ),
            max_width="400px",
        ),
        open=AltaGastoState.abierto,
        on_open_change=AltaGastoState.set_abierto,
    )
