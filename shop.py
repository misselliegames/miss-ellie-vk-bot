from __future__ import annotations

from pathlib import Path
from PIL import Image

SHOP_CATEGORIES = ["house", "garden", "pet", "decor"]

SHOP_ITEMS = {
    "house": [
        {"id": "house_08_small", "title": "🏠 Маленький дом", "price": 8, "file": "house_08_small.png"},
        {"id": "house_12_cottage", "title": "🏡 Уютный коттедж", "price": 12, "file": "house_12_cottage.png"},
        {"id": "house_16_castle", "title": "🏰 Изумрудный замок", "price": 16, "file": "house_16_castle.png"},
    ],
    "garden": [
        {"id": "garden_04_flowers", "title": "🌷 Клумба", "price": 4, "file": "garden_04_flowers.png"},
        {"id": "garden_06_tree", "title": "🌳 Дерево и цветы", "price": 6, "file": "garden_06_tree.png"},
        {"id": "garden_08_fountain", "title": "⛲ Сад с фонтаном", "price": 8, "file": "garden_08_fountain.png"},
    ],
    "pet": [
        {"id": "pet_04_pig", "title": "🐷 Свинка", "price": 4, "file": "pet_04_pig.png"},
        {"id": "pet_06_dog", "title": "🐶 Пёс", "price": 6, "file": "pet_06_dog.png"},
        {"id": "pet_08_horse", "title": "🐴 Конь", "price": 8, "file": "pet_08_horse.png"},
    ],
    "decor": [
        {"id": "decor_04_lantern", "title": "🏮 Фонарь", "price": 4, "file": "decor_04_lantern.png"},
        {"id": "decor_06_chest", "title": "🧰 Сундук с изумрудами", "price": 6, "file": "decor_06_chest.png"},
        {"id": "decor_08_crystal", "title": "💚 Изумрудный кристалл", "price": 8, "file": "decor_08_crystal.png"},
    ],
}

CATEGORY_TITLES = {
    "house": "Выбери дом",
    "garden": "Теперь укрась участок",
    "pet": "Выбери питомца",
    "decor": "И последнее — выбери сокровище",
}

# We deliberately render pet LAST so it is always in the foreground.
RENDER_ORDER = ["house", "garden", "decor", "pet"]

# Target boxes on a 1080x1080 scene. Objects are cropped to non-transparent bbox,
# scaled proportionally, then bottom-centered in their box.
TARGET_BOXES = {
    "house": (190, 120, 890, 600),
    "garden": (20, 380, 450, 870),
    "decor": (350, 650, 730, 1040),
    "pet": (650, 500, 1060, 1045),
}


def min_remaining_cost(categories):
    return sum(min(x["price"] for x in SHOP_ITEMS[c]) for c in categories)


def affordable_items(balance: int, category_index: int):
    category = SHOP_CATEGORIES[category_index]
    remaining = SHOP_CATEGORIES[category_index + 1:]
    reserve = min_remaining_cost(remaining)
    items = [x for x in SHOP_ITEMS[category] if x["price"] <= balance - reserve]
    return items or [min(SHOP_ITEMS[category], key=lambda x: x["price"])]


def _open_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def _crop_visible(img: Image.Image) -> Image.Image:
    alpha = img.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return img
    return img.crop(bbox)


def _place_in_box(canvas: Image.Image, layer: Image.Image, box):
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    layer = _crop_visible(layer)
    if layer.width == 0 or layer.height == 0:
        return
    scale = min(bw / layer.width, bh / layer.height, 1.0)
    nw = max(1, int(layer.width * scale))
    nh = max(1, int(layer.height * scale))
    if (nw, nh) != layer.size:
        layer = layer.resize((nw, nh), Image.Resampling.LANCZOS)
    # Bottom-center placement. This keeps feet/base aligned and gives consistent depth.
    x = x1 + (bw - nw) // 2
    y = y2 - nh
    canvas.alpha_composite(layer, (x, y))


def compose_shop_scene(asset_dir: Path, selected: dict, output_path: Path) -> Path:
    background_path = asset_dir / "shop_background.jpg"
    bg = _open_rgba(background_path).resize((1080, 1080), Image.Resampling.LANCZOS)

    for category in RENDER_ORDER:
        item_id = selected.get(category)
        if not item_id:
            continue
        item = next(x for x in SHOP_ITEMS[category] if x["id"] == item_id)
        layer_path = asset_dir / item["file"]
        layer = _open_rgba(layer_path)
        _place_in_box(bg, layer, TARGET_BOXES[category])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    bg.save(output_path, "PNG")
    return output_path
