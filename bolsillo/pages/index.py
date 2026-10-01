import reflex as rx

ICONOS = ["hand_coins", "circle_dollar_sign", "wallet", "landmark", "euro",
          "piggy_bank", "coins", "utensils", "chef_hat", "salad", "fish"]  # etc.


class Iconos(rx.State):
    dibujos: list[str] = ICONOS
    selected: str = ""
    text_categ: str = ""
    categories: dict[str, str] = {}

    @rx.event
    def toggle(self, dibujo: str):
        if dibujo == self.selected:
            self.selected = ""
        else:
            self.selected = dibujo
            
    @rx.event
    def add_category(self):
        if self.text_categ and self.selected:
            self.categories[self.text_categ] = self.selected
            self.text_categ = ""
            self.selected = ""

    @rx.event
    def set_text_categ(self, value: str):
        self.text_categ = value

def show_dibujo(dibujo: str) -> rx.Component:
    return rx.icon(tag=dibujo, size=20)


def boton_dibujo(dibujo: str) -> rx.Component:
    return rx.button(
        show_dibujo(dibujo),
        size="1",
        variant=rx.cond(Iconos.selected == dibujo, "solid", "outline"),
        on_click=Iconos.toggle(dibujo),
    )


def index() -> rx.Component:
    return rx.container(
        rx.flex(
            rx.foreach(Iconos.dibujos, boton_dibujo),
            wrap="wrap",
            spacing="2",
        ),
        rx.divider(size="4", margin_y="1em"),
        rx.text("Seleccionado: "),
        rx.flex(
            rx.cond(Iconos.selected != "", show_dibujo(Iconos.selected)),
            rx.input(
                placeholder="Escribe una categoría",
                value=Iconos.text_categ,
                on_change=Iconos.set_text_categ,
            ),
            rx.button(
                "Agregar categoría",
                on_click=Iconos.add_category,
            ),
            spacing="2",
        ),
        rx.divider(size="4", margin_y="1em"),
        rx.foreach(Iconos.categories.items(), lambda item: rx.flex(show_dibujo(item[1]), rx.text(f"{item[0]}"), spacing="2")),
        size="1",
    )
