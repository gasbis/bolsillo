"""Iconos y colores disponibles para las categorías.

Módulo sin dependencias de Reflex ni de los states para poder importarlo
desde cualquier sitio (donut, formulario de alta, página de categorías)
sin crear importaciones circulares.
"""

# Nombres de iconos Lucide (https://lucide.dev/icons) que se ofrecen al
# crear una categoría. Con guion, que es como los nombra Lucide.
ICONOS = [
    # Comida
    "utensils", "chef-hat", "fish", "cooking-pot", "cookie", "banana", "soup",
    "salad", "beef", "pizza", "carrot", "bean", "egg-fried", "ice-cream-cone",
    "candy", "croissant", "drumstick", "cherry", "ham", "grape", "dessert",
    "sandwich", "broccoli", "coffee", "wine", "beer",
    # Casa
    "home", "armchair", "bed-double", "sofa", "shelving-unit", "blender",
    "zap", "droplet", "flame", "utility-pole", "wifi", "phone", "wrench",
    "hammer", "paint-roller", "trees", "flower-2", "dog", "cat",
    # Compras
    "shopping-cart", "shopping-basket", "store", "shirt", "gift", "package",
    # Transporte y viajes
    "car", "fuel", "bus", "train-front", "plane", "bike", "luggage", "ship",
    # Ocio
    "monitor-play", "clapperboard", "tv", "gamepad-2", "music", "book-open",
    "dumbbell", "ticket", "party-popper",
    # Salud y personal
    "heart-pulse", "pill", "stethoscope", "scissors", "baby", "graduation-cap",
    # Dinero
    "briefcase", "wallet", "wallet-cards", "credit-card", "coins", "euro",
    "piggy-bank", "hand-coins", "landmark", "receipt", "percent", "user-round",
]

# Paleta del anillo: una por hueco del donut (14).
COLORES = [
    "#6366F1", "#8B5CF6", "#A855F7", "#D946EF", "#EC4899", "#F43F5E", "#F97316",
    "#EAB308", "#84CC16", "#22C55E", "#14B8A6", "#06B6D4", "#0EA5E9", "#3B82F6",
]

# Valor por defecto de `Categoria.color` (ver models.py): significa "sin
# color elegido" y entonces se usa el de la paleta según su posición.
COLOR_POR_DEFECTO = "#64748b"


def color_categoria(color: str, posicion: int) -> str:
    """Color con el que se pinta una categoría que ocupa `posicion` en la
    lista ordenada de categorías de gasto."""
    if not color or color.lower() == COLOR_POR_DEFECTO:
        return COLORES[posicion % len(COLORES)]
    return color
