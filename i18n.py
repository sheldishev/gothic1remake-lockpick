"""Строки интерфейса и решения (RU / EN)."""

from __future__ import annotations

from typing import Dict, Literal

Lang = Literal["ru", "en"]

APP_TITLE = "Gothic 1 Remake lockpick"

MESSAGES: Dict[Lang, Dict[str, str]] = {
    "ru": {
        "plates": "Пластинок:",
        "solve": "▶ Решить",
        "example": "Пример",
        "clear": "Очистить",
        "ready": "Готово",
        "searching": "Поиск…",
        "example_loaded": "Пример загружен",
        "wait_title": "Подождите",
        "wait_body": "Решение уже выполняется.",
        "input_error": "Ошибка ввода",
        "error": "Ошибка",
        "start": "Старт",
        "plate_header": "П{n}",
        "influence_row": "→П{n}",
        "position_range": "Положение П{n} должно быть от {min} до {max}",
        "already_solved": "Уже решено.",
        "already_solved_full": "Уже решено: все пластинки в положении {target}.",
        "solution_found": "Решение найдено.",
        "solution_not_found": "Решение не найдено: ни одна последовательность допустимых ходов не приводит к цели.",
        "error_prefix": "Ошибка: {detail}",
        "step": "Шаг",
        "move_line": "Пластинку {plate} — {times} {side}",
        "left": "влево",
        "right": "вправо",
        "cli_puzzle_header": "Головоломка: {n} пластинок, положения {min}..{max}, цель — все на {target}.",
        "cli_move_rules": "Каждую пластинку можно сдвигать влево или вправо.",
        "cli_bounds_rules": "Ход возможен только если все затронутые пластинки остаются в пределах {min}..{max}.",
        "cli_builtin_example": "Используется встроенный пример влияний (как в GUI).",
        "cli_chain_influence": "Используется цепочечное влияние для {n} пластинок.",
    },
    "en": {
        "plates": "Plates:",
        "solve": "▶ Solve",
        "example": "Example",
        "clear": "Clear",
        "ready": "Ready",
        "searching": "Searching…",
        "example_loaded": "Example loaded",
        "wait_title": "Please wait",
        "wait_body": "A solve is already in progress.",
        "input_error": "Input error",
        "error": "Error",
        "start": "Start",
        "plate_header": "P{n}",
        "influence_row": "→P{n}",
        "position_range": "Plate P{n} must be between {min} and {max}",
        "already_solved": "Already solved.",
        "already_solved_full": "Already solved: all plates at position {target}.",
        "solution_found": "Solution found.",
        "solution_not_found": "No solution: no valid move sequence reaches the goal.",
        "error_prefix": "Error: {detail}",
        "step": "Step",
        "move_line": "Plate {plate} — {times} {side}",
        "left": "left",
        "right": "right",
        "cli_puzzle_header": "Puzzle: {n} plates, positions {min}..{max}, goal — all at {target}.",
        "cli_move_rules": "Each plate can move left or right.",
        "cli_bounds_rules": "A move is valid only if every affected plate stays within {min}..{max}.",
        "cli_builtin_example": "Using the built-in influence example (same as in the GUI).",
        "cli_chain_influence": "Using chain influence for {n} plates.",
    },
}


def t(key: str, lang: Lang, **kwargs: object) -> str:
    text = MESSAGES[lang][key]
    return text.format(**kwargs) if kwargs else text


def format_times(count: int, lang: Lang) -> str:
    if lang == "en":
        return f"{count} time" if count == 1 else f"{count} times"
    n, n1 = abs(count) % 100, abs(count) % 10
    if n1 == 1 and n != 11:
        return f"{count} раз"
    if n1 in (2, 3, 4) and n not in (12, 13, 14):
        return f"{count} раза"
    return f"{count} раз"


def move_side(direction: int, lang: Lang) -> str:
    if direction == 1:
        return t("left", lang)
    return t("right", lang)
