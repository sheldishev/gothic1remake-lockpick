#!/usr/bin/env python3
"""
Решатель головоломки с взаимосвязанными пластинками.

Количество пластинок задаётся пользователем. Положение каждой — от 1 до 7
(без зацикливания). Цель: все пластинки в положении 4.

Пластинку можно сдвинуть влево (-1) или вправо (+1). При сдвиге пластинки i
на d её связи действуют так же, умноженные на d.

Ход допустим только если ни одна затронутая пластинка не выходит за границы 1..7.

Запуск:
  python plate_puzzle_solver.py
  python plate_puzzle_gui.py
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from i18n import Lang, format_times, move_side, t

Move = Tuple[int, int]  # (номер пластинки, направление -1 или +1)
Delta = Tuple[int, int]  # (индекс строки, изменение положения)

MIN_POS = 1
MAX_POS = 7
TARGET = 4
MIN_PLATES = 4
MAX_PLATES = 7
DEFAULT_NUM_PLATES = 6


@dataclass(frozen=True)
class PuzzleConfig:
    num_plates: int
    min_pos: int = MIN_POS
    max_pos: int = MAX_POS
    target: int = TARGET

    def __post_init__(self) -> None:
        if not MIN_PLATES <= self.num_plates <= MAX_PLATES:
            raise ValueError(
                f"Количество пластинок должно быть от {MIN_PLATES} до {MAX_PLATES}, "
                f"получено: {self.num_plates}"
            )


@dataclass(frozen=True)
class MoveTable:
    """Предвычисленные сдвиги для каждого хода (пластинка, направление)."""

    moves: Tuple[Tuple[int, int, Delta, ...], ...]
    num_plates: int
    min_pos: int
    max_pos: int

    def apply(self, state: Tuple[int, ...], move_idx: int) -> Optional[Tuple[int, ...]]:
        _, _, *deltas = self.moves[move_idx]
        pos = list(state)
        for row, delta in deltas:
            pos[row] += delta
            if pos[row] < self.min_pos or pos[row] > self.max_pos:
                return None
        return tuple(pos)

    def predecessor(self, state: Tuple[int, ...], move_idx: int) -> Optional[Tuple[int, ...]]:
        """Состояние до хода move_idx, если apply(результат, move_idx) == state."""
        _, _, *deltas = self.moves[move_idx]
        pos = list(state)
        for row, delta in deltas:
            pos[row] -= delta
            if pos[row] < self.min_pos or pos[row] > self.max_pos:
                return None
        return tuple(pos)


def build_effect_matrix(
    influences: Dict[int, Dict[int, int]], config: PuzzleConfig
) -> List[List[int]]:
    """A[j][i]: изменение пластинки (j+1) при сдвиге (i+1) на +1."""
    n = config.num_plates
    matrix = [[0] * n for _ in range(n)]
    for plate in range(1, n + 1):
        col = plate - 1
        matrix[col][col] = 1
        for affected, sign in influences.get(plate, {}).items():
            if not 1 <= affected <= n:
                raise ValueError(f"Номер пластинки вне диапазона 1..{n}: {affected}")
            if sign not in (-1, 1):
                raise ValueError(f"Знак влияния должен быть -1 или +1, получено: {sign}")
            matrix[affected - 1][col] += sign
    return matrix


def build_move_table(
    influences: Dict[int, Dict[int, int]], config: PuzzleConfig
) -> MoveTable:
    effects = build_effect_matrix(influences, config)
    n = config.num_plates
    moves: List[Tuple[int, int, Delta, ...]] = []
    for plate_idx in range(n):
        for direction in (-1, 1):
            deltas = tuple(
                (row, direction * effects[row][plate_idx])
                for row in range(n)
                if effects[row][plate_idx]
            )
            moves.append((plate_idx + 1, direction, *deltas))
    return MoveTable(tuple(moves), n, config.min_pos, config.max_pos)


def _encode_state(state: Tuple[int, ...]) -> int:
    code = 0
    for value in state:
        code = code * (MAX_POS - MIN_POS + 1) + (value - MIN_POS)
    return code


def _decode_state(code: int, num_plates: int) -> Tuple[int, ...]:
    base = MAX_POS - MIN_POS + 1
    values = [0] * num_plates
    for index in range(num_plates - 1, -1, -1):
        values[index] = code % base + MIN_POS
        code //= base
    return tuple(values)


def _move_from_index(table: MoveTable, move_idx: int) -> Move:
    plate, direction, *_ = table.moves[move_idx]
    return plate, direction


def _switch_cost(last_plate: Optional[int], plate: int) -> int:
    return 0 if last_plate is None or last_plate == plate else 1


def _reconstruct_forward(
    parent: Dict[int, Tuple[int, int]],
    start: int,
    goal: int,
    table: MoveTable,
) -> List[Move]:
    path: List[Move] = []
    state = goal
    while state != start:
        prev, move_idx = parent[state]
        path.append(_move_from_index(table, move_idx))
        state = prev
    path.reverse()
    return path


def _bidirectional_min_depth(
    table: MoveTable, start: int, goal: int
) -> Tuple[Optional[int], Dict[int, int]]:
    """Минимальное число ходов и расстояния до цели (двунаправленный BFS)."""
    if start == goal:
        return 0, {goal: 0}

    forward_depth = {start: 0}
    backward_depth = {goal: 0}
    forward_frontier = {start: 0}
    backward_frontier = {goal: 0}
    best_depth = 10**9

    while forward_frontier and backward_frontier:
        if best_depth < 10**9:
            if min(forward_frontier.values()) + min(backward_frontier.values()) >= best_depth:
                break

        if len(forward_frontier) <= len(backward_frontier):
            next_frontier: Dict[int, int] = {}
            for state, depth in forward_frontier.items():
                decoded = _decode_state(state, table.num_plates)
                for move_idx in range(len(table.moves)):
                    new_state = table.apply(decoded, move_idx)
                    if new_state is None:
                        continue
                    encoded = _encode_state(new_state)
                    new_depth = depth + 1
                    if encoded in backward_depth:
                        best_depth = min(best_depth, new_depth + backward_depth[encoded])
                    if encoded in forward_depth:
                        continue
                    forward_depth[encoded] = new_depth
                    next_frontier[encoded] = new_depth
            forward_frontier = next_frontier
        else:
            next_frontier = {}
            for state, depth in backward_frontier.items():
                decoded = _decode_state(state, table.num_plates)
                for move_idx in range(len(table.moves)):
                    pred = table.predecessor(decoded, move_idx)
                    if pred is None:
                        continue
                    encoded = _encode_state(pred)
                    new_depth = depth + 1
                    if encoded in forward_depth:
                        best_depth = min(best_depth, forward_depth[encoded] + new_depth)
                    if encoded in backward_depth:
                        continue
                    backward_depth[encoded] = new_depth
                    next_frontier[encoded] = new_depth
            backward_frontier = next_frontier

    if best_depth == 10**9:
        return None, backward_depth
    return best_depth, backward_depth


def _backward_distances(table: MoveTable, goal: int, max_depth: int) -> Dict[int, int]:
    """Расстояния от каждого состояния до цели (обратный BFS)."""
    dist = {goal: 0}
    frontier = {goal}
    for depth in range(max_depth):
        next_frontier: set[int] = set()
        for state in frontier:
            decoded = _decode_state(state, table.num_plates)
            for move_idx in range(len(table.moves)):
                pred = table.predecessor(decoded, move_idx)
                if pred is None:
                    continue
                encoded = _encode_state(pred)
                if encoded in dist:
                    continue
                dist[encoded] = depth + 1
                next_frontier.add(encoded)
        frontier = next_frontier
        if not frontier:
            break
    return dist


def _layered_min_switch_search(
    table: MoveTable,
    start: int,
    goal: int,
    depth_limit: int,
    dist_to_goal: Dict[int, int],
) -> Optional[List[Move]]:
    """Кратчайший путь с минимумом переключений между пластинками на заданной глубине."""
    n = table.num_plates
    num_moves = len(table.moves)
    frontier: Dict[int, Tuple[int, Optional[int]]] = {start: (0, None)}
    parent: Dict[int, Tuple[int, int]] = {}

    for depth in range(1, depth_limit + 1):
        remaining = depth_limit - depth
        next_frontier: Dict[int, Tuple[int, Optional[int]]] = {}
        for state, (switches, last_plate) in frontier.items():
            decoded = _decode_state(state, n)
            for move_idx in range(num_moves):
                new_decoded = table.apply(decoded, move_idx)
                if new_decoded is None:
                    continue
                encoded = _encode_state(new_decoded)
                if dist_to_goal.get(encoded, depth_limit + 1) > remaining:
                    continue
                plate, _, *_ = table.moves[move_idx]
                new_switches = switches + _switch_cost(last_plate, plate)
                prev = next_frontier.get(encoded)
                if prev is not None and prev[0] <= new_switches:
                    continue
                next_frontier[encoded] = (new_switches, plate)
                parent[encoded] = (state, move_idx)

        if goal in next_frontier:
            return _reconstruct_forward(parent, start, goal, table)
        frontier = next_frontier

    return None


def bfs_solve(
    positions: List[int],
    influences: Dict[int, Dict[int, int]],
    config: PuzzleConfig,
    minimize_switches: bool = True,
    lang: Lang = "ru",
) -> Tuple[Optional[List[Move]], str]:
    """
    Поиск кратчайшей последовательности сдвигов.
    Сначала минимум ходов (двунаправленный BFS), затем — переключений между пластинками.
    """
    n = config.num_plates
    if len(positions) != n:
        raise ValueError(f"Нужно ровно {n} начальных положений, получено {len(positions)}")
    for p in positions:
        if not config.min_pos <= p <= config.max_pos:
            raise ValueError(
                f"Положение должно быть от {config.min_pos} до {config.max_pos}, получено: {p}"
            )

    table = build_move_table(influences, config)
    start_tuple = tuple(positions)
    start = _encode_state(start_tuple)
    goal = _encode_state(tuple([config.target] * n))

    if start == goal:
        return [], t("already_solved_full", lang, target=config.target)

    min_depth, _ = _bidirectional_min_depth(table, start, goal)
    if min_depth is None:
        return None, t("solution_not_found", lang)

    dist_to_goal = _backward_distances(table, goal, min_depth)
    path = _layered_min_switch_search(table, start, goal, min_depth, dist_to_goal)
    if path is None:
        return None, t("solution_not_found", lang)

    if minimize_switches:
        path = coalesce_moves(start_tuple, path, table)

    return path, t("solution_found", lang)


def coalesce_moves(
    start: Tuple[int, ...],
    move_sequence: List[Move],
    table: MoveTable,
) -> List[Move]:
    """Сдвигает одинаковые ходы одной пластинки ближе, сохраняя результат."""
    moves = move_sequence[:]
    move_index = {(plate, direction): i for i, (plate, direction, *_) in enumerate(table.moves)}

    def replay(seq: List[Move]) -> Optional[Tuple[int, ...]]:
        state = start
        for plate, direction in seq:
            state = table.apply(state, move_index[plate, direction])
            if state is None:
                return None
        return state

    target = replay(moves)
    if target is None:
        return move_sequence

    changed = True
    while changed:
        changed = False
        for i in range(len(moves) - 2):
            if moves[i] == moves[i + 2] and moves[i] != moves[i + 1]:
                candidate = moves[: i + 1] + [moves[i + 2], moves[i + 1]] + moves[i + 3 :]
                if replay(candidate) == target:
                    moves = candidate
                    changed = True
                    break
    return moves


def compress_moves(move_sequence: List[Move]) -> List[Tuple[int, int, int]]:
    """(пластинка, направление, количество) для подряд идущих одинаковых ходов."""
    if not move_sequence:
        return []
    compressed: List[Tuple[int, int, int]] = []
    plate, direction = move_sequence[0]
    count = 1
    for move in move_sequence[1:]:
        if move == (plate, direction):
            count += 1
        else:
            compressed.append((plate, direction, count))
            plate, direction = move
            count = 1
    compressed.append((plate, direction, count))
    return compressed


def format_grouped_steps(
    positions: List[int],
    move_sequence: List[Move],
    table: MoveTable,
    lang: Lang = "ru",
) -> List[str]:
    state = tuple(positions)
    move_index = {(plate, direction): i for i, (plate, direction, *_) in enumerate(table.moves)}
    lines: List[str] = []

    for plate, direction, count in compress_moves(move_sequence):
        for _ in range(count):
            new_state = table.apply(state, move_index[plate, direction])
            if new_state is None:
                lines.append(
                    f"ERROR — plate {plate} {move_side(direction, lang)} @ {list(state)}"
                )
                return lines
            state = new_state
        lines.append(
            t(
                "move_line",
                lang,
                plate=plate,
                times=format_times(count, lang),
                side=move_side(direction, lang),
            )
        )

    return lines


def format_solution_text(
    positions: List[int],
    move_sequence: List[Move],
    influences: Dict[int, Dict[int, int]],
    config: PuzzleConfig,
    lang: Lang = "ru",
) -> str:
    if not move_sequence:
        return t("already_solved", lang)
    table = build_move_table(influences, config)
    steps = format_grouped_steps(positions, move_sequence, table, lang)
    return "\n".join(
        f"{t('step', lang)} {i + 1}. {line}" for i, line in enumerate(steps)
    )


def print_solution(
    positions: List[int],
    move_sequence: List[Move],
    influences: Dict[int, Dict[int, int]],
    config: PuzzleConfig,
) -> None:
    print("\n" + format_solution_text(positions, move_sequence, influences, config))


# --- CLI ---

def parse_positions(text: str, num_plates: int) -> List[int]:
    parts = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
    if len(parts) != num_plates:
        raise ValueError(f"Ожидается {num_plates} чисел, получено {len(parts)}")
    return [int(p) for p in parts]


def read_num_plates_interactive() -> int:
    while True:
        raw = input(
            f"Введите количество пластинок ({MIN_PLATES}..{MAX_PLATES}, "
            f"по умолчанию {DEFAULT_NUM_PLATES}): "
        ).strip()
        if not raw:
            return DEFAULT_NUM_PLATES
        try:
            value = int(raw)
            PuzzleConfig(num_plates=value)
            return value
        except ValueError as exc:
            print(f"Ошибка: {exc}")


def parse_influences_interactive(config: PuzzleConfig) -> Dict[int, Dict[int, int]]:
    n = config.num_plates
    print(f"\nВведите влияние каждой из {n} пластинок.")
    print("Формат строки: номер:цель1:знак1,цель2:знак2  (знак +1 или -1)")
    print("Пример для пластинки 1: 1:2:-1,5:+1")
    print("Пустая строка — нет дополнительного влияния (кроме самой пластинки).\n")

    influences: Dict[int, Dict[int, int]] = {}
    for plate in range(1, n + 1):
        while True:
            raw = input(f"Пластинка {plate}: ").strip()
            if not raw:
                influences[plate] = {}
                break
            try:
                influences[plate] = {}
                if ":" not in raw:
                    raise ValueError("нужен формат номер:цель:знак,...")
                head, *pairs = raw.split(":")
                if int(head) != plate:
                    print(f"  Предупреждение: первая цифра {head}, ожидалась {plate}. Использую {plate}.")
                for pair in pairs:
                    if not pair:
                        continue
                    if pair.startswith(("+", "-")):
                        raise ValueError("укажите цель:знак, например 2:-1")
                    target_str, sign_str = pair.rsplit(":", 1)
                    target, sign = int(target_str), int(sign_str)
                    if sign not in (-1, 1):
                        raise ValueError("знак только +1 или -1")
                    if not 1 <= target <= n:
                        raise ValueError(f"цель должна быть от 1 до {n}")
                    influences[plate][target] = sign
                break
            except ValueError as exc:
                print(f"  Ошибка разбора: {exc}. Повторите ввод.")
    return influences


def chain_influences(num_plates: int) -> Dict[int, Dict[int, int]]:
    influences: Dict[int, Dict[int, int]] = {}
    for plate in range(1, num_plates + 1):
        linked: Dict[int, int] = {}
        if plate > 1:
            linked[plate - 1] = -1
        if plate < num_plates:
            linked[plate + 1] = 1
        influences[plate] = linked
    return influences


EXAMPLE_INFLUENCES_6 = {
    1: {2: -1, 5: +1},
    2: {1: -1, 3: +1},
    3: {2: -1, 4: +1},
    4: {3: -1, 5: +1},
    5: {4: -1, 6: +1},
    6: {5: -1, 1: +1},
}


def resolve_num_plates(args: argparse.Namespace) -> int:
    if args.plates is not None:
        PuzzleConfig(num_plates=args.plates)
        return args.plates
    if args.positions:
        count = len([p for p in args.positions.replace(";", ",").split(",") if p.strip()])
        if MIN_PLATES <= count <= MAX_PLATES:
            PuzzleConfig(num_plates=count)
            return count
    return read_num_plates_interactive()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Решатель головоломки с взаимосвязанными пластинками (положения 1..7, цель 4)"
    )
    parser.add_argument("--plates", type=int, help=f"Количество пластинок ({MIN_PLATES}..{MAX_PLATES})")
    parser.add_argument("--positions", help="Начальные положения через запятую")
    parser.add_argument("--influences-json", help='JSON влияний, например: {"1":{"6":1}}')
    parser.add_argument("--example", action="store_true", help="Пример цепочечного влияния")
    args = parser.parse_args()

    num_plates = resolve_num_plates(args)
    config = PuzzleConfig(num_plates=num_plates)

    print(
        f"Головоломка: {num_plates} пластинок, положения {MIN_POS}..{MAX_POS}, "
        f"цель — все на {TARGET}."
    )
    print("Каждую пластинку можно сдвигать влево или вправо.")
    print("Ход возможен только если все затронутые пластинки остаются в пределах 1..7.\n")

    if args.positions:
        positions = parse_positions(args.positions, num_plates)
    else:
        while True:
            raw = input(f"Введите {num_plates} начальных положений через запятую: ").strip()
            try:
                positions = parse_positions(raw, num_plates)
                break
            except ValueError as exc:
                print(f"Ошибка: {exc}")

    if args.influences_json:
        raw_map = json.loads(args.influences_json)
        influences = {int(k): {int(t): int(s) for t, s in v.items()} for k, v in raw_map.items()}
    elif args.example:
        if num_plates == 6:
            influences = deepcopy(EXAMPLE_INFLUENCES_6)
            print("Используется пример цепочечного влияния для 6 пластинок.")
        else:
            influences = chain_influences(num_plates)
            print(f"Используется цепочечное влияние для {num_plates} пластинок.")
    else:
        influences = parse_influences_interactive(config)

    move_sequence, message = bfs_solve(positions, influences, config)
    if move_sequence is None:
        print(message)
        return 1

    print_solution(positions, move_sequence, influences, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
