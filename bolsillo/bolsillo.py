import reflex as rx
from bolsillo.pages.index import index



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
