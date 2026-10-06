import reflex as rx

def footer() -> rx.Component:
    return rx.vstack(
        rx.divider(size="4"),
        rx.flex(
            rx.spacer(),
            rx.icon_button(
                rx.icon(tag="arrow-big-up", size=30),
                size="4",
                color_scheme="green",
                radius="full",
            ),
            rx.spacer(),
            rx.icon_button(
                rx.icon(tag="arrow-big-down", size=30),
                size="4",
                color_scheme="red",
                radius="full",
            ),
            rx.spacer(),
            width="100%",
            justify="between",
            align="center",
            # spacing="9",
        ),
    )