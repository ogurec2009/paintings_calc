import math
from typing import List, Tuple
from itertools import product

DEFAULT_OFFSET = 5.0  # 5 см с каждой стороны
EXHAUSTIVE_REFINE_MAX_PAINTINGS = 12  # до стольки картин перебираем все повороты полностью

def add_margins(w: float, h: float, offset: float = DEFAULT_OFFSET) -> Tuple[float, float]:
    return w + 2 * offset, h + 2 * offset

def try_layout(canvas_width: float, max_height: float, paintings: List[Tuple[float, float]], rotation_mask: List[bool], offset: float = DEFAULT_OFFSET) -> List[dict]:
    paintings_with_margin = []
    for i, (w, h) in enumerate(paintings):
        if rotation_mask[i]:
            w, h = h, w
        w, h = add_margins(w, h, offset)  # добавляем отступ с каждой стороны
        paintings_with_margin.append({
            "index": i,
            "width": w,
            "height": h,
            "raw": (paintings[i][0], paintings[i][1]),
            "rotated": rotation_mask[i]
        })

    layout = []
    current_y = 0.0
    row_height = 0.0
    row_x = 0.0

    for p in paintings_with_margin:
        if row_x + p["width"] <= canvas_width:
            layout.append({
                "x": row_x,
                "y": current_y,
                "width": p["width"],
                "height": p["height"],
                "original": p["raw"],
                "rotated": p["rotated"]
            })
            row_x += p["width"]
            row_height = max(row_height, p["height"])
        else:
            if p["width"] > canvas_width:
                return None  # не влезает по ширине даже в пустом ряду
            current_y += row_height
            if current_y + p["height"] > max_height:
                return None  # не влезает
            row_x = 0.0
            row_height = p["height"]
            layout.append({
                "x": row_x,
                "y": current_y,
                "width": p["width"],
                "height": p["height"],
                "original": p["raw"],
                "rotated": p["rotated"]
            })
            row_x += p["width"]

    # финальный размер холста (без учёта свободного места снизу)
    total_height = current_y + row_height
    if total_height > max_height:
        return None

    return layout

def _pack_shelves(canvas_width: float, items: List[dict]) -> Tuple[float, List[dict]]:
    """Жадная укладка рядами (shelf packing) с выбором поворота для каждой картины."""
    layout = []
    current_y = 0.0
    row_height = 0.0
    row_x = 0.0

    for item in items:
        orientations = item["orientations"]
        fitting = [o for o in orientations if row_x + o[0] <= canvas_width]
        if not fitting:
            # текущий ряд заполнен — начинаем новый
            current_y += row_height
            row_x = 0.0
            row_height = 0.0
            fitting = [o for o in orientations if o[0] <= canvas_width]
        # минимизируем высоту ряда, при равенстве берём более узкий вариант
        w, h, rotated = min(fitting, key=lambda o: (max(row_height, o[1]), o[0]))
        layout.append({
            "x": row_x,
            "y": current_y,
            "width": w,
            "height": h,
            "original": item["raw"],
            "rotated": rotated,
        })
        row_x += w
        row_height = max(row_height, h)

    return current_y + row_height, layout

def _pack_shelves_first_fit(canvas_width: float, items: List[dict]) -> Tuple[float, List[dict]]:
    """Укладка рядами по принципу first-fit: картина помещается в первый
    подходящий ряд (с выбором поворота), иначе открывается новый ряд.
    Сложность O(n * число рядов) — дороже, чем _pack_shelves, но точнее."""
    rows = []  # {"height": высота ряда, "x": занятая ширина}
    placements = []

    for item in items:
        best = None
        for ri, row in enumerate(rows):
            for w, h, rotated in item["orientations"]:
                if row["x"] + w <= canvas_width:
                    # сначала минимизируем прирост общей высоты, затем
                    # плотнее заполняем ряд (best-fit), затем берём ряд раньше
                    growth = max(row["height"], h) - row["height"]
                    key = (growth, canvas_width - row["x"] - w, ri)
                    if best is None or key < best[0]:
                        best = (key, ri, w, h, rotated)
        if best is None:
            # ни один ряд не подходит — открываем новый с минимальной высотой
            w, h, rotated = min(
                (o for o in item["orientations"] if o[0] <= canvas_width),
                key=lambda o: (o[1], o[0]),
            )
            ri = len(rows)
            rows.append({"height": h, "x": w})
            placements.append((ri, 0.0, w, h, rotated, item))
        else:
            _, ri, w, h, rotated = best
            row = rows[ri]
            placements.append((ri, row["x"], w, h, rotated, item))
            row["x"] += w
            row["height"] = max(row["height"], h)

    # координаты y рядов известны только после укладки всех картин
    row_y = []
    total_height = 0.0
    for row in rows:
        row_y.append(total_height)
        total_height += row["height"]

    layout = [
        {
            "x": x,
            "y": row_y[ri],
            "width": w,
            "height": h,
            "original": item["raw"],
            "rotated": rotated,
        }
        for ri, x, w, h, rotated, item in placements
    ]
    return total_height, layout

def find_min_canvas_length(canvas_width: float, paintings: List[Tuple[float, float]], offset: float = DEFAULT_OFFSET) -> Tuple[float, List[dict]]:
    """Подбор минимальной длины холста.

    Быстрая эвристика: картины сортируются несколькими способами и укладываются
    рядами с жадным выбором поворота. Для небольших наборов (до
    EXHAUSTIVE_REFINE_MAX_PAINTINGS картин) дополнительно выполняется полный
    перебор поворотов для каждого из порядков — это дёшево и почти всегда даёт
    оптимальный результат. Для больших наборов результат может быть немного
    хуже оптимального.
    """
    if not paintings:
        return 0.0, []

    items = []
    for w, h in paintings:
        w_m, h_m = add_margins(w, h, offset)  # добавляем отступ с каждой стороны
        orientations = [(w_m, h_m, False)]
        if w_m != h_m:
            orientations.append((h_m, w_m, True))
        if all(ow > canvas_width for ow, _, _ in orientations):
            return 0.0, None  # картина не помещается по ширине даже с поворотом
        items.append({
            "raw": (w, h),
            "orientations": orientations,
            "min_side": min(w_m, h_m),
            "max_side": max(w_m, h_m),
            "area": w_m * h_m,
        })

    # несколько проходов с разными порядками сортировки — берём лучший результат
    sort_keys = (
        lambda it: (-it["min_side"], -it["max_side"]),
        lambda it: (-it["max_side"], -it["min_side"]),
        lambda it: (-it["area"], -it["max_side"]),
    )
    orders = [sorted(items, key=key) for key in sort_keys]
    orders.append(items)  # исходный порядок ввода тоже может оказаться удачным

    best_length = math.inf
    best_layout = None
    for ordered in orders:
        length, layout = _pack_shelves(canvas_width, ordered)
        if length < best_length:
            best_length, best_layout = length, layout

    # first-fit улучшает результат на небольших наборах, но стоит O(n * число
    # рядов), поэтому для очень больших наборов ограничиваемся next-fit
    if len(items) <= 1000:
        for ordered in orders[:-1]:
            length, layout = _pack_shelves_first_fit(canvas_width, ordered)
            if length < best_length:
                best_length, best_layout = length, layout

    # для небольших наборов дёшево перебрать все повороты целиком:
    # несколько порядков * 2^n вариантов, при n <= 12 это доли секунды
    if len(items) <= EXHAUSTIVE_REFINE_MAX_PAINTINGS:
        raw_orders = list(dict.fromkeys(tuple(it["raw"] for it in ordered) for ordered in orders))
        for order in raw_orders:
            for rotation_mask in product([False, True], repeat=len(order)):
                layout = try_layout(canvas_width, math.inf, order, rotation_mask, offset)
                if layout is not None:
                    length = max(p["y"] + p["height"] for p in layout)
                    if length < best_length:
                        best_length, best_layout = length, layout

    # округляем вверх до 0.1 см, чтобы холст точно покрывал схему размещения
    return math.ceil(best_length * 10 - 1e-9) / 10, best_layout

