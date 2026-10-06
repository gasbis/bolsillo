import reflex as rx
from bolsillo.components.header import header
from bolsillo.pages.categories import ICONOS_GASTOS as iconos
from bolsillo.components.header import FilterState
from bolsillo.components.footer import footer


# datos ficticios para el gráfico modelo
data = [
    {"browser": "Chrome", "visitors": 275},
    {"browser": "Firefox", "visitors": 150},
    {"browser": "Safari", "visitors": 100},
    {"browser": "Opera", "visitors": 130},
    {"browser": "Edge", "visitors": 140},
]

colors = ["#6366F1", "#8B5CF6", "#A855F7", "#D946EF", "#EC4899"]

# gráfico no válido. Solo modelo.
def example_graph() -> rx.Component:
    return rx.vstack(
        rx.recharts.pie_chart(
            rx.recharts.pie(
                rx.foreach(
                    data,
                    lambda item, index: rx.recharts.cell(
                        fill=rx.Var.create(colors)[index % len(colors)],
                    ),
                ),
                data=data,
                data_key="visitors",
                name_key="browser",
                inner_radius="60%",
                outer_radius="90%",
                padding_angle=2,
                stroke="#fff",
                custom_attrs={"strokeWidth": 2},
            ),
            rx.recharts.graphing_tooltip(),
            width="40%",
            height=300,
        ),
        justify="center",
        align="center",  
    )
    
def index() -> rx.Component:
    return rx.container(
        header(),
        rx.vstack(
            rx.flex(
                rx.text(FilterState.date_item, font_size="1em"),
                width="100%",
                justify="center",
            ),
            rx.flex(
                rx.icon(tag=iconos[0], size=30),
                rx.icon(tag=iconos[1], size=30),
                rx.icon(tag=iconos[2], size=30),
                rx.icon(tag=iconos[3], size=30),
                width="100%",
                justify="between",
            ),
            rx.flex(
                rx.flex(
                    rx.icon(tag=iconos[4], size=30),
                    rx.icon(tag=iconos[5], size=30),
                    rx.icon(tag=iconos[6], size=30),
                    direction="column",
                    justify="between",
                ),
                rx.box(
                    rx.vstack(
                        rx.fragment(
                            rx.text("35,56 €", font_size="1em", font_weight="bold", color_scheme="green"),
                            rx.text("19,78 €", font_size="1em", font_weight="bold", color_scheme="red"),
                        ),
                    align="center",
                    spacing="1",
                    position="absolute",
                    top="50%",
                    left="50%",
                    transform="translate(-50%, -50%)",
                    ),
                    example_graph(),
                    position="relative",
                    width="100%",
                ),                             
                rx.flex(
                    rx.icon(tag=iconos[7], size=30),
                    rx.icon(tag=iconos[8], size=30),
                    rx.icon(tag=iconos[9], size=30),
                    direction="column",
                    justify="between",
                ),
                width="100%",
                direction="row",
                justify="between",                            
            ),
            rx.flex(
                rx.icon(tag=iconos[10], size=30),
                rx.icon(tag=iconos[11], size=30),
                rx.icon(tag=iconos[12], size=30),
                rx.icon(tag=iconos[13], size=30),
                width="100%",
                justify="between",
            ),
            rx.flex(
                rx.icon_button(
                    rx.icon(tag="menu", size=30),
                    variant="soft",
                    color_scheme="gray",
                ),
                rx.box(
                    "SALDO: 12.000€",
                    background_color="orange",
                    border_radius="5px",
                    # width="30%",
                    margin="8px",
                    padding_x="15px",
                    padding_y="8px",
                    align="center",
                ),
                rx.icon_button(
                    rx.icon(tag="menu", size=30),
                    variant="soft",
                    color_scheme="gray",
                ),
                width="100%",
                justify="center",
                align="center",
                spacing="6",
            ),         
            justify="center",
            width="100%",
            padding="1em",
            spacing="9",            
        ),        
        footer(),   
    )
