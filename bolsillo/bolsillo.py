import reflex as rx

from rxconfig import config
from bolsillo.pages.index import index


class State(rx.State):
    """The app state."""





app = rx.App()
app.add_page(
    index,
    route="/",
    title="",
    description="",
    meta=[
        {"name": "robots", "content": "noindex, nofollow"}
    ],
)
