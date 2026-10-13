import reflex as rx



ICONOS = ["utensils", "chef_hat", "fish", "cooking-pot", "cookie", "banana", "soup", "salad", "beef", "pizza", "carrot", "bean", "egg-fried", "ice-cream-cone", "candy", "croissant", "drumstick", "cherry", "ham", "grape", "dessert", "sandwich", "broccoli", "candy-cane", "bean-off", "blender", "nut", "ice-cream-bowl", "candy-off", "popsicle", "lollipop", "nut-off", "beef-off", "armchair", "bed-double", "bed", "shelving-unit", "sofa", "shopping-cart", "shopping-basket", "phone", "home", "store", "fuel", "droplet", "utility-pole", "zap", "monitor-play", "clapperboard", "tv", "luggage", "briefcase", "shirt", "train-front", "plane", "wallet-cards", "coins", "piggy-bank", "user-round", "wallet", "landmark", "hand_coins", "euro", "piggy_bank", "gift"] 

CATEGORIA = ("Cuenta", "Ingresos", "Gastos")

class Iconos(rx.State):
    dibujos: list[str] = ICONOS
    selected: str = ""
    cat_name: str = ""
    cat_tipo: str = ""
    categories: dict[str, list[str]] = {}

    @rx.event
    def toggle(self, dibujo: str):
        self.selected = "" if dibujo == self.selected else dibujo

    @rx.event
    def set_cat_name(self, value: str):
        self.cat_name = value

    @rx.event
    def set_cat_tipo(self, value: str):
        self.cat_tipo = value

    @rx.event
    def add_category(self):
        nombre = self.cat_name.strip()
        if nombre and self.selected and self.cat_tipo:
            self.categories[nombre] = [self.selected, self.cat_tipo]
            self.cat_name = ""
            self.cat_tipo = ""
            self.selected = ""

def lista_por_tipo(tipo: str) -> rx.Component:
    return rx.foreach(
        Iconos.categories,
        lambda item: rx.cond(item[1][1] == tipo, show_categoria(item)),
    )

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
        show_dibujo(item[1][0]),  # Mostrar el icono de la categoría
        rx.text(item[0]),
        rx.badge(item[1][1]),  # Mostrar el tipo de categoría
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
            rx.cond(Iconos.selected != "", show_dibujo(Iconos.selected),),
            rx.input(
                placeholder="Escribe una categoría",
                value=Iconos.cat_name,
                on_change=Iconos.set_cat_name,
            ),
            rx.select(
                CATEGORIA,
                value=Iconos.cat_tipo,
                on_change=Iconos.set_cat_tipo,
            ),
            rx.button(
                "Agregar categoría",
                on_click=Iconos.add_category,
                disabled=(Iconos.selected == "") | (Iconos.cat_name == "") | (Iconos.cat_tipo == ""),
            ),
            spacing="2",
            align="center",
        ),
        rx.divider(size="4", margin_y="1em"),
        rx.text("Categorías:"),
        rx.vstack(
            rx.text("Cuenta:"),
            lista_por_tipo("Cuenta"),
            rx.text("Gastos:"),
            lista_por_tipo("Gastos"),
            rx.text("Ingresos:"),
            lista_por_tipo("Ingresos"),
        ),
        size="1",
    )