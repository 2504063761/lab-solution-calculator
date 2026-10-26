"""Percent and molarity based material preparation, independent of culture mixing.

Amounts use Decimal throughout. Volume-based mixtures are brought to their final
volume: the solvent volume cannot be inferred by subtracting solute volumes.
"""

from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation, localcontext
import io
from typing import Any, Mapping
import unicodedata

from mix_core import InputError


BASIS_LABELS = {"ww": "w/w", "wv": "w/v", "vv": "v/v", "molar": "摩尔浓度"}
MASS_UNITS = {"mg": Decimal(".001"), "g": Decimal(1), "kg": Decimal(1000)}
VOLUME_UNITS = {"µL": Decimal(".001"), "mL": Decimal(1), "L": Decimal(1000)}
MOLAR_UNITS = {"M": Decimal(1), "mM": Decimal(".001"),
               "μM": Decimal(".000001"), "nM": Decimal(".000000001")}
MOLAR_MASS_UNITS = {"g/mol": Decimal(1), "mg/mol": Decimal(".001")}
OUTPUT_MASS_UNITS = {"g": Decimal(1), "mg": Decimal(".001"), "μg": Decimal(".000001")}
HUNDRED = Decimal(100)


def _text(value: Any, field: str, default: str | None = None) -> str:
    if value is None and default is not None:
        value = default
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"请填写{field}。")
    value = value.strip()
    if len(value) > 120 or any(unicodedata.category(char) in ("Cc", "Cf", "Cs") for char in value):
        raise InputError(f"{field}不能超过 120 字，且不能含换行、制表符或控制字符。")
    return value


def _decimal(value: Any, field: str, *, optional: bool = False, zero: bool = False) -> Decimal | None:
    if value is None or isinstance(value, str) and not value.strip():
        if optional:
            return None
        raise InputError(f"请填写{field}。")
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise InputError(f"{field}必须是有效数值。")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise InputError(f"{field}必须是有效数值。") from None
    if not number.is_finite() or number < 0 or not zero and number == 0:
        requirement = "大于或等于零" if zero else "大于零"
        raise InputError(f"{field}必须是{requirement}的有限数值。")
    if number and not -300 <= number.adjusted() <= 300:
        raise InputError(f"{field}超出支持的数值范围（1e-300 至 1e300）。")
    if len(number.as_tuple().digits) > 50:
        raise InputError(f"{field}最多支持 50 位有效数字。")
    return number


def _canonical(number: Decimal | None) -> str | None:
    if number is None:
        return None
    if not number:
        return "0"
    with localcontext() as context:
        context.prec = 50
        return str(number.normalize())


def display_number(number: Decimal | str) -> str:
    """Display 12 significant digits without rounding tiny nonzero amounts to zero."""
    number = Decimal(number)
    if not number:
        return "0"
    with localcontext() as context:
        context.prec = 12
        rounded = +number
    if -5 <= rounded.adjusted() <= 8:
        return format(rounded, "f").rstrip("0").rstrip(".") if "." in format(rounded, "f") else format(rounded, "f")
    return str(rounded.normalize()).replace("E+", "e+").replace("E-", "e-")


def empty_materials() -> dict[str, Any]:
    return {"basis": "ww", "total": None, "unit": "g", "solvent": "溶剂 / 基质",
            "components": [{"name": "材料1", "percent": None}]}


def _unit(value: Any, units: Mapping[str, Decimal], field: str,
          aliases: Mapping[str, str] | None = None) -> str:
    if not isinstance(value, str):
        raise InputError(f"请选择有效的{field}。")
    value = value.strip()
    if aliases:
        value = aliases.get(value, value)
    if value not in units:
        raise InputError(f"{field}请选择 {'、'.join(units)}。")
    return value


def normalize_request(data: Mapping[str, Any], complete: bool = True) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise InputError("材料配方格式无效。")
    basis = data.get("basis")
    if not isinstance(basis, str) or basis not in BASIS_LABELS:
        raise InputError("浓度口径请选择 w/w、w/v、v/v 或摩尔浓度。")
    units = MASS_UNITS if basis == "ww" else VOLUME_UNITS
    unit = data.get("unit")
    if not isinstance(unit, str) or unit not in units:
        raise InputError("w/w 的总量请选择 mg、g 或 kg。" if basis == "ww" else "最终体积请选择 µL、mL 或 L。")
    total = _decimal(data.get("total"), "最终总质量" if basis == "ww" else "最终总体积", optional=not complete)
    solvent_value = data.get("solvent")
    if solvent_value is None or isinstance(solvent_value, str) and not solvent_value.strip():
        solvent_value = "溶剂 / 基质"
    solvent = _text(solvent_value, "溶剂 / 基质名称")
    components = data.get("components")
    if not isinstance(components, (list, tuple)) or not components:
        raise InputError("请至少填写一种材料。")
    if len(components) > 100:
        raise InputError("单个配方最多支持 100 种材料。")
    parsed, names, percentages = [], set(), []
    for index, row in enumerate(components, 1):
        if not isinstance(row, Mapping):
            raise InputError(f"第 {index} 行的材料格式无效。")
        name = _text(row.get("name"), f"第 {index} 行材料名称")
        if name.casefold() in names:
            raise InputError(f"材料名称“{name}”重复，请使用不同的名称。")
        names.add(name.casefold())
        if basis == "molar":
            concentration = _decimal(row.get("concentration"), f"{name}的目标摩尔浓度",
                                     optional=not complete, zero=True)
            concentration_unit = _unit(row.get("concentration_unit"), MOLAR_UNITS, "摩尔浓度单位",
                {"µM": "μM", "uM": "μM", "mol/L": "M", "mmol/L": "mM",
                 "μmol/L": "μM", "µmol/L": "μM", "umol/L": "μM", "nmol/L": "nM"})
            molar_mass = _decimal(row.get("molar_mass"), f"{name}的摩尔质量", optional=not complete)
            molar_mass_unit = _unit(row.get("molar_mass_unit"), MOLAR_MASS_UNITS, "摩尔质量单位")
            parsed.append({"name": name, "concentration": _canonical(concentration),
                           "concentration_unit": concentration_unit, "molar_mass": _canonical(molar_mass),
                           "molar_mass_unit": molar_mass_unit})
            continue
        percent = _decimal(row.get("percent"), f"{name}的目标浓度（%）", optional=not complete, zero=True)
        if percent is not None:
            percentages.append(percent)
        parsed.append({"name": name, "percent": _canonical(percent)})
    with localcontext() as context:
        context.prec = 350
        if basis in ("ww", "vv") and sum(percentages, Decimal(0)) > HUNDRED:
            raise InputError(f"{BASIS_LABELS[basis]} 各材料的百分浓度之和不得超过 100%。")
    normalized = {"basis": basis, "total": _canonical(total), "unit": unit, "solvent": solvent,
                  "components": parsed}
    if basis == "molar":
        normalized["mass_unit"] = _unit(data.get("mass_unit", "mg"), OUTPUT_MASS_UNITS, "称量单位",
                                        {"µg": "μg", "ug": "μg"})
    return normalized


def _calculate_molar(request: Mapping[str, Any]) -> dict[str, Any]:
    target = f"{display_number(request['total'])} {request['unit']}"
    mass_unit = request["mass_unit"]
    headers = ["材料 / 项目", "目标浓度", "摩尔质量", "用量", "单位", "配制操作"]
    rows = []
    with localcontext() as context:
        context.prec = 350
        volume_l = Decimal(request["total"]) * VOLUME_UNITS[request["unit"]] / Decimal(1000)
        for item in request["components"]:
            concentration = Decimal(item["concentration"])
            molar_mass = Decimal(item["molar_mass"])
            mass_g = (concentration * MOLAR_UNITS[item["concentration_unit"]] * volume_l *
                      molar_mass * MOLAR_MASS_UNITS[item["molar_mass_unit"]])
            mass = mass_g / OUTPUT_MASS_UNITS[mass_unit]
            rows.append([item["name"], f"{display_number(concentration)} {item['concentration_unit']}",
                         f"{display_number(molar_mass)} {item['molar_mass_unit']}",
                         display_number(mass), mass_unit, "称取后溶解 / 分散"])
    rows.append([request["solvent"], "—", "—", "适量", "—", f"定容至 {target}"])
    notes = ["质量(g) = 摩尔浓度(mol/L) × 最终体积(L) × 摩尔质量(g/mol)。",
             "M = mol/L；mM = 1e-3 mol/L；μM = 1e-6 mol/L；nM = 1e-9 mol/L。",
             "g/mol、mg/mol 是摩尔质量单位；1 g/mol = 1000 mg/mol。请使用实际原料的摩尔质量，区分盐型和水合物。",
             f"先加入部分{request['solvent']}使材料溶解 / 分散，再定容至 {target}；最终体积包含所有组分。",
             "不假设混合体积可加和，不能据此计算精确的补溶剂体积。按原料直接称量，不计纯度或母液浓度，不判断溶解度。"]
    return {"request": request, "basis": "molar", "headers": headers, "rows": rows, "notes": notes,
            "summary": f"摩尔浓度 · 最终总体积 {target} · {len(request['components'])} 种材料 · 称量单位 {mass_unit}"}


def calculate_materials(data: Mapping[str, Any]) -> dict[str, Any]:
    request = normalize_request(data)
    if request["basis"] == "molar":
        return _calculate_molar(request)
    basis, unit = request["basis"], request["unit"]
    total = Decimal(request["total"])
    quantity_name = "最终总质量" if basis == "ww" else "最终总体积"
    target = f"{display_number(total)} {unit}"
    headers = ["材料 / 项目", f"目标浓度 (% {BASIS_LABELS[basis]})", "用量", "单位", "配制操作"]
    rows, amounts = [], []
    notes = ["按所填原料直接计算；不计纯度、母液浓度或额外加料。浓度切换只改变口径，不进行密度换算。"]
    with localcontext() as context:
        context.prec = 350
        for item in request["components"]:
            percent = Decimal(item["percent"])
            if basis == "ww":
                amount = total * percent / HUNDRED
                amount_unit, operation = unit, "称取后加入"
            else:
                total_ml = total * VOLUME_UNITS[unit]
                amount = total_ml * percent / HUNDRED
                amount_unit, operation = ("g", "称取后溶解 / 分散") if basis == "wv" else ("mL", "量取后加入")
            amounts.append(amount)
            rows.append([item["name"], display_number(percent), display_number(amount), amount_unit, operation])
        if basis == "ww":
            solvent_amount = total - sum(amounts, Decimal(0))
            rows.append([request["solvent"], "—", display_number(solvent_amount), unit, f"补足总质量至 {target}"])
            notes.append("w/w = 组分质量 ÷ 最终混合物总质量 × 100%；溶剂 / 基质质量由质量守恒求得。")
        else:
            rows.append([request["solvent"], "—", "适量", "—", f"定容至 {target}"])
            definition = "每 100 mL 最终混合物所含组分的克数" if basis == "wv" else "组分加入体积 ÷ 最终混合物体积 × 100%"
            notes.append(f"{BASIS_LABELS[basis]} = {definition}。")
            notes.append(f"先加入部分{request['solvent']}混匀，再定容至 {target}；最终体积包含所有组分。")
            notes.append("混合体积不保证可加和，不能用最终体积减去组分体积来确定准确补液量。")
            if basis == "wv":
                notes.append("本计算不判断溶解度、溶解性或是否成胶；w/v 的百分数是 g/100 mL，可超过 100。")
    return {"request": request, "basis": basis, "headers": headers, "rows": rows, "notes": notes,
            "summary": f"{BASIS_LABELS[basis]} · {quantity_name} {target} · {len(amounts)} 种材料"}


def _export_cell(value: str) -> str:
    """Prevent user labels becoming spreadsheet formulas when pasted or imported."""
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def materials_text(result: Mapping[str, Any]) -> str:
    lines = [result["summary"], "\t".join(_export_cell(value) for value in result["headers"])]
    lines.extend("\t".join(_export_cell(value) for value in row) for row in result["rows"])
    lines.extend("说明：" + note for note in result["notes"])
    return "\n".join(lines)


def materials_csv(result: Mapping[str, Any]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["配制摘要", result["summary"]])
    writer.writerow([_export_cell(value) for value in result["headers"]])
    writer.writerows([_export_cell(value) for value in row] for row in result["rows"])
    writer.writerows(["说明", note] for note in result["notes"])
    return stream.getvalue()
