import reflex as rx



ICONOS_CARTERAS = ["wallet-cards", "coins", "piggy-bank", "user-round", "wallet", "landmark"]

ICONOS_INGRESOS = ["hand_coins", "euro", "piggy_bank", "coins", "gift"] 


ICONOS_GASTOS = ["utensils", "chef_hat", "salad", "fish", "cooking-pot", "cookie", "banana", "soup", "salad", "beef", "pizza", "carrot", "bean", "egg-fried", "ice-cream-cone", "candy", "croissant", "drumstick", "cherry", "ham", "grape", "dessert", "sandwich", "broccoli", "candy-cane", "bean-off", "blender", "nut", "ice-cream-bowl", "candy-off", "popsicle", "lollipop", "nut-off", "beef-off", "armchair", "bed-double", "bed", "shelving-unit", "sofa", "shopping-cart", "shopping-basket", "phone", "home", "store", "fuel", "droplet", "utility-pole", "zap", "monitor-play", "clapperboard", "tv", "luggage", "briefcase", "shirt", "train-front", "plane"] 

CATEGORIA = ("carteras", "ingresos", "gastos")

class Iconos(rx.State):
    dibujos: list[str] = ICONOS_GASTOS
    selected: str = ""
    text_categ: str = ""
    categories: dict[str, str] = {}

    @rx.event
    def toggle(self, dibujo: str):
        self.selected = "" if dibujo == self.selected else dibujo

    @rx.event
    def set_text_categ(self, value: str):
        self.text_categ = value

    @rx.event
    def add_category(self):
        nombre = self.text_categ.strip()
        if nombre and self.selected:
            self.categories[nombre] = self.selected
            self.text_categ = ""
            self.selected = ""


def show_dibujo(dibujo: str) -> rx.Component:
    return rx.icon(tag=dibujo, size=20)


def boton_dibujo(dibujo: str) -> rx.Component:
    return rx.button(
        show_dibujo(dibujo),
        size="1",
        variant=rx.cond(Iconos.selected == dibujo, "solid", "outline"),
        on_click=Iconos.toggle(dibujo),
    )


def show_categoria(item: list) -> rx.Component:
    # item[0] = nombre de la categoría, item[1] = icono
    return rx.hstack(
        show_dibujo(item[1]),
        rx.text(item[0]),
        align="center",
    )


def categorias() -> rx.Component:
    return rx.container(
        rx.flex(
            rx.link(
                rx.hstack(
                    rx.text("Inicio"),
                    spacing="1",
                ),
                href="/",
            ),
        ),
        rx.divider(size="4", margin_y="1em"),
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
                disabled=(Iconos.selected == "") | (Iconos.text_categ == ""),
            ),
            spacing="2",
            align="center",
        ),
        rx.divider(size="4", margin_y="1em"),
        rx.text("Categorías:"),
        rx.vstack(
            rx.foreach(Iconos.categories, show_categoria),
        ),
        size="1",
    )