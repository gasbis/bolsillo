import reflex as rx
from bolsillo.pages.index import index
from bolsillo.pages.categories import categorias



app = rx.App(
    html_lang="es",
)
app.add_page(
    index,
    route="/",
    title="",
    description="",
    meta=[
        {"name": "robots", "content": "noindex, nofollow"}
    ],
)
app.add_page(
    categorias,
    route="/categorias",
    title="",
    description="",
    meta=[
        {"name": "robots", "content": "noindex, nofollow"}
    ],
)
