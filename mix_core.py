"""Pure OD-contribution calculations; volumes are kept in microlitres."""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass
from typing import Any, Mapping

from upstream.calculator import calculate_volumes

MODE_LABELS = {"separate": "分别稀释后混合", "direct": "原液直接混合"}
UNITS = {"µL": 1.0, "mL": 1000.0}


class InputError(ValueError):
    """An input is missing or invalid."""


class FeasibilityError(InputError):
    def __init__(self, maximum_od: float, mode: str, limiting: tuple[str, ...] = ()):
        self.maximum_od = maximum_od
        self.limiting = limiting
        detail = f"限制菌种：{'、'.join(limiting)}。\n" if limiting else ""
        super().__init__(
            f"当前参数无法仅靠稀释实现“{MODE_LABELS[mode]}”。\n"
            f"{detail}最高可实现的目标总 OD：{maximum_od!r}。\n"
            "请降低目标总 OD 或修改配方；改变最终体积不会改变这一浓度上限。"
        )


def positive_number(value: Any, field: str, optional: bool = False) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if optional:
            return None
        raise InputError(f"请填写{field}。")
    if isinstance(value, bool):
        raise InputError(f"{field}必须是有效的正数。")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise InputError(f"{field}必须是有效的正数。") from None
    if not math.isfinite(number) or number <= 0:
        raise InputError(f"{field}必须是大于零的有限数值。")
    return number


@dataclass(frozen=True)
class Culture:
    name: str
    od: float | None
    dilution: float
    ratio: float


@dataclass(frozen=True)
class Recipe:
    cultures: tuple[Culture, ...]
    target_od: float | None = None
    volume: float | None = None
    unit: str = "µL"
    mode: str = "separate"

    def as_dict(self, include_od: bool = True) -> dict[str, Any]:
        return {
            "cultures": [
                {"name": c.name, "od": c.od if include_od else None,
                 "dilution": c.dilution, "ratio": c.ratio}
                for c in self.cultures
            ],
            "target_od": self.target_od, "volume": self.volume,
            "unit": self.unit, "mode": self.mode,
        }


def parse_recipe(data: Mapping[str, Any], complete: bool = False) -> Recipe:
    if not isinstance(data, Mapping):
        raise InputError("配方格式无效。")
    rows = data.get("cultures")
    if not isinstance(rows, (list, tuple)) or not rows:
        raise InputError("请至少填写一种菌。")
    cultures = []
    names = set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, Mapping):
            raise InputError(f"第 {index} 行的菌种信息无效。")
        name_value = row.get("name", "")
        name = name_value.strip() if isinstance(name_value, str) else ""
        if not name:
            raise InputError(f"请填写第 {index} 行的菌种名称。")
        if any(ord(char) < 32 for char in name):
            raise InputError(f"第 {index} 行的名称不能含换行或制表符。")
        if name.casefold() in names:
            raise InputError(f"菌种名称“{name}”重复，请使用不同的样品名称。")
        names.add(name.casefold())
        od = positive_number(row.get("od"), f"{name}的初始 OD", optional=not complete)
        dilution = positive_number(row.get("dilution", 1), f"{name}的测定稀释倍数")
        if dilution < 1:
            raise InputError(f"{name}的测定稀释倍数不得小于 1。")
        ratio = positive_number(row.get("ratio"), f"{name}的比例")
        if od is not None and not math.isfinite(od * dilution):
            raise InputError(f"{name}换算后的原液 OD 超出支持的数值范围。")
        cultures.append(Culture(name, od, dilution, ratio))
    unit = data.get("unit", "µL")
    mode = data.get("mode", "separate")
    if unit not in UNITS:
        raise InputError("体积单位请选择 µL 或 mL。")
    if mode not in MODE_LABELS:
        raise InputError("请选择有效的配液流程。")
    target = positive_number(data.get("target_od"), "目标总 OD", optional=not complete)
    volume = positive_number(data.get("volume"), "最终体积", optional=not complete)
    if volume is not None and not math.isfinite(volume * UNITS[unit]):
        raise InputError("最终体积超出支持的数值范围。")
    return Recipe(tuple(cultures), target, volume, unit, mode)


def example_recipe() -> Recipe:
    # Generic software example, not an experimental recipe or measured readings.
    return Recipe((Culture("A", None, 1, 1), Culture("B", None, 1, 1), Culture("C", None, 1, 2)))


def empty_recipe() -> Recipe:
    return Recipe((Culture("菌种1", None, 1, 1),))


@dataclass(frozen=True)
class Portion:
    name: str
    measured_od: float
    dilution: float
    stock_od: float
    ratio: float
    weight: float
    culture_ul: float
    diluent_ul: float | None
    prepared_ul: float
    working_od: float | None
    contribution_od: float


@dataclass(frozen=True)
class MixResult:
    recipe: Recipe
    portions: tuple[Portion, ...]
    total_ul: float
    culture_ul: float
    diluent_ul: float
    theoretical_od: float
    maximum_od: float


def calculate_mix(recipe: Recipe) -> MixResult:
    recipe = parse_recipe(recipe.as_dict(), complete=True)
    count = len(recipe.cultures)
    largest_ratio = max(c.ratio for c in recipe.cultures)
    scaled = [c.ratio / largest_ratio for c in recipe.cultures]
    ratio_sum = math.fsum(scaled)
    weights = [r / ratio_sum for r in scaled]
    if any(w <= 0 for w in weights):
        raise InputError("比例差异超出支持的数值范围，请缩小比例数值的差异。")
    stocks = [c.od * c.dilution for c in recipe.cultures]
    smallest_stock = min(stocks)
    if recipe.mode == "direct":
        maximum = smallest_stock / math.fsum(w * (smallest_stock / c) for w, c in zip(weights, stocks))
        limiting = ()
    else:
        limits = [c / (count * w) for w, c in zip(weights, stocks)]
        maximum = min(limits)
        limiting = tuple(c.name for c, limit in zip(recipe.cultures, limits)
                         if math.isclose(limit, maximum, rel_tol=1e-12))
    target = recipe.target_od
    if target > maximum and not math.isclose(target, maximum, rel_tol=1e-12, abs_tol=0):
        raise FeasibilityError(maximum, recipe.mode, limiting)
    # A target just above the limit through floating-point noise uses the boundary.
    target = min(target, maximum)
    total = recipe.volume * UNITS[recipe.unit]
    portions = []
    for culture, stock, weight in zip(recipe.cultures, stocks, weights):
        contribution = target * weight
        if recipe.mode == "separate":
            working_od = min(target * (count * weight), stock)
            prepared = total / count
            # Reuse the upstream MIT single-culture module without modifying it.
            raw, diluent = calculate_volumes({culture.name: stock}, working_od, prepared)[culture.name]
        else:
            working_od = None
            raw = (contribution / stock) * total
            diluent = None
            prepared = raw
        values = [raw, prepared, contribution] + ([diluent, working_od] if diluent is not None else [])
        if any(not math.isfinite(value) for value in values) or raw <= 0:
            raise InputError("计算结果超出支持的数值范围，请调整输入。")
        portions.append(Portion(culture.name, culture.od, culture.dilution, stock,
                                culture.ratio, weight, raw, diluent, prepared,
                                working_od, contribution))
    raw_total = math.fsum(p.culture_ul for p in portions)
    if recipe.mode == "separate":
        diluent_total = math.fsum(p.diluent_ul for p in portions)
    else:
        diluent_total = total - raw_total
        if diluent_total < 0:
            if math.isclose(raw_total, total, rel_tol=1e-12):
                diluent_total = 0.0
            else:
                raise FeasibilityError(maximum, recipe.mode)
    theoretical = math.fsum(p.stock_od * (p.culture_ul / total) for p in portions)
    return MixResult(recipe, tuple(portions), total, raw_total, diluent_total, theoretical, maximum)


def compact(number: float | None) -> str:
    return "" if number is None else format(number, ".12g")


def result_table(result: MixResult) -> tuple[list[str], list[list[str]]]:
    separate = result.recipe.mode == "separate"
    headers = ["菌种 / 样品", "原液 OD", "比例", "取原液 (µL)", "补液 (µL)",
               "配成 (µL)" if separate else "入管 (µL)",
               "调整后 OD" if separate else "OD 贡献"]
    rows = []
    for p in result.portions:
        rows.append([p.name, compact(p.stock_od), compact(p.ratio), f"{p.culture_ul:.3f}",
                     f"{p.diluent_ul:.3f}" if separate else "—", f"{p.prepared_ul:.3f}",
                     compact(p.working_od if separate else p.contribution_od)])
    if not separate:
        rows.append(["统一补液", "—", "—", "—", f"{result.diluent_ul:.3f}",
                     f"{result.diluent_ul:.3f}", "—"])
    rows.append(["合计 / 混合后", "—", "—", f"{result.culture_ul:.3f}",
                 f"{result.diluent_ul:.3f}", f"{result.total_ul:.3f}", compact(result.theoretical_od)])
    return headers, rows


def result_document(result: MixResult) -> list[list[str]]:
    headers, rows = result_table(result)
    metadata = [
        ["实验配液计算器 — 配液结果"],
        ["配液流程", MODE_LABELS[result.recipe.mode]],
        ["目标总 OD", compact(result.recipe.target_od)],
        ["最终体积 (µL)", compact(result.total_ul)],
        ["理论总 OD", compact(result.theoretical_od)],
        ["比例含义", "OD 贡献比，不等同活菌数量比"], [],
        ["输入菌种", "测得初始 OD", "测定稀释倍数", "换算原液 OD", "比例"],
    ]
    inputs = [[p.name, compact(p.measured_od), compact(p.dilution), compact(p.stock_od), compact(p.ratio)]
              for p in result.portions]
    return metadata + inputs + [[], headers] + rows


def result_text(result: MixResult) -> str:
    return "\n".join("\t".join(row) for row in result_document(result))


def result_csv(result: MixResult) -> str:
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows(result_document(result))
    return stream.getvalue()
