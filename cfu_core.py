"""User-calibrated OD600/CFU estimates using a line through the origin.

No biological coefficient is bundled.  The caller must supply a coefficient
measured for the applicable strain and measurement conditions.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
import math
from typing import Any, Mapping
import unicodedata

from mix_core import InputError


def _number(value: Any, field: str, *, optional: bool = False,
            positive: bool = False, minimum: float | None = None) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if optional:
            return None
        raise InputError(f"请填写{field}。")
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise InputError(f"{field}必须是有效数值。")
    try:
        text = str(value).strip()
        if len(text) > 128:
            raise ValueError("number too long")
        precise = Decimal(text)
        if not precise.is_finite():
            raise ValueError("non-finite number")
        number = float(precise)
    except (InvalidOperation, ValueError, TypeError, OverflowError):
        raise InputError(f"{field}必须是有限数值。") from None
    if not math.isfinite(number) or (precise != 0 and number == 0):
        raise InputError(f"{field}超出支持的数值范围。")
    if positive and precise <= 0:
        raise InputError(f"{field}必须大于零。")
    if not positive and precise < 0:
        raise InputError(f"{field}不得小于零。")
    if minimum is not None and precise < Decimal(str(minimum)):
        raise InputError(f"{field}不得小于 {minimum:g}。")
    return 0.0 if number == 0 else number


def _text(value: Any, field: str, limit: int, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise InputError(f"{field}必须是文字。")
    if any(unicodedata.category(char) in ("Cc", "Cf", "Cs") for char in value):
        raise InputError(f"{field}不能含换行、制表符或控制字符。")
    value = value.strip()
    if required and not value:
        raise InputError(f"请填写{field}。")
    if len(value) > limit:
        raise InputError(f"{field}不能超过 {limit} 个字符。")
    return value


def parse_calibration(data: Mapping[str, Any], require_name: bool = False) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise InputError("校准系数格式无效。")
    coefficient = _number(data.get("coefficient"), "校准系数 k", positive=True)
    lower = _number(data.get("od_min"), "校准 OD600 下限", optional=True)
    upper = _number(data.get("od_max"), "校准 OD600 上限", optional=True)
    if lower is not None and upper is not None and lower >= upper:
        raise InputError("校准 OD600 下限必须小于上限。")
    return {
        "name": _text(data.get("name", ""), "校准方案名称", 120, required=require_name),
        "species": _text(data.get("species", ""), "菌种 / 菌株", 120),
        "coefficient": coefficient,
        "od_min": lower,
        "od_max": upper,
        "notes": _text(data.get("notes", ""), "校准条件说明", 1000),
    }


def _supported_result(number: Decimal, field: str) -> float:
    value = float(number)
    if not math.isfinite(value) or (number != 0 and value == 0):
        raise InputError(f"{field}超出支持的数值范围，请检查系数与输入。")
    return 0.0 if value == 0 else value


def format_number(value: float) -> str:
    """Use the same presentation in the table, clipboard and CSV."""
    return "0" if value == 0 else f"{value:.8g}"


def range_text(calibration: Mapping[str, Any]) -> str:
    lower, upper = calibration["od_min"], calibration["od_max"]
    if lower is not None and upper is not None:
        return f"{format_number(lower)} ≤ 实测 OD600 ≤ {format_number(upper)}"
    if lower is not None:
        return f"实测 OD600 ≥ {format_number(lower)}（未填写上限）"
    if upper is not None:
        return f"实测 OD600 ≤ {format_number(upper)}（未填写下限）"
    return "未填写校准适用范围"


def convert_cfu(data: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise InputError("OD600–CFU 换算输入格式无效。")
    direction = data.get("direction")
    if direction not in ("od_to_cfu", "cfu_to_od"):
        raise InputError("请选择有效的 OD600–CFU 换算方向。")
    calibration = parse_calibration(data.get("calibration"))
    value = _number(data.get("value"), "实测 OD600" if direction == "od_to_cfu" else "原液 CFU/mL")
    dilution = _number(data.get("dilution"), "测定稀释倍数", minimum=1)
    with localcontext() as context:
        context.prec = 60
        input_decimal, factor, coefficient = (Decimal(str(number)) for number in
                                              (value, dilution, calibration["coefficient"]))
        if direction == "od_to_cfu":
            measured = input_decimal
            stock = measured * factor
            cfu = stock * coefficient
        else:
            cfu = input_decimal
            stock = cfu / coefficient
            measured = stock / factor
        measured_od = _supported_result(measured, "实测 / 预计实测 OD600")
        stock_od = _supported_result(stock, "原液等效 OD600")
        cfu_ml = _supported_result(cfu, "估算原液 CFU/mL")
        warnings = []
        lower, upper = calibration["od_min"], calibration["od_max"]
        if lower is None and upper is None:
            warnings.append("未填写校准适用范围；结果仅为按所填系数进行的线性估算。")
        elif ((lower is not None and measured < Decimal(str(lower))) or
              (upper is not None and measured > Decimal(str(upper)))):
            warnings.append(f"实测 / 预计实测 OD600 超出校准适用范围（{range_text(calibration)}），属于线性外推。")
        if value == 0:
            warnings.append("输入为 0 的模型估算结果不能证明无可培养活菌。")
    return {
        "direction": direction,
        "input_value": value,
        "dilution": dilution,
        "calibration": calibration,
        "measured_od": measured_od,
        "stock_od": stock_od,
        "cfu_ml": cfu_ml,
        "warnings": warnings,
    }


def conversion_table(result: Mapping[str, Any]) -> tuple[list[str], list[list[str]]]:
    calibration = result["calibration"]
    forward = result["direction"] == "od_to_cfu"
    rows = [
        ["结果性质", "按自定义校准系数线性估算，不代替平板培养计数"],
        ["换算方向", "实测 OD600 → 估算原液 CFU/mL" if forward else "原液 CFU/mL → 预计实测 OD600"],
        ["校准方案", calibration["name"] or "未保存方案"],
        ["菌种 / 菌株", calibration["species"] or "未填写"],
        ["校准条件说明", calibration["notes"] or "未填写"],
        ["校准系数 k（CFU/mL / OD600）", format_number(calibration["coefficient"])],
        ["测定稀释倍数 D", format_number(result["dilution"])],
        ["实测 OD600" if forward else "预计实测 OD600", format_number(result["measured_od"])],
        ["原液等效 OD600", format_number(result["stock_od"])],
        ["估算原液 CFU/mL", format_number(result["cfu_ml"])],
        ["校准适用范围", range_text(calibration)],
        ["范围与估算提示", "；".join(result["warnings"]) or "实测 / 预计实测 OD600 在所填校准范围内"],
        ["模型公式", "原液 CFU/mL = k × 实测 OD600 × 测定稀释倍数 D"],
        ["适用限制", "请使用同菌种及测量条件的校准系数；不根据混合菌总 OD600 拆分各菌 CFU"],
    ]
    return ["项目", "数值"], rows
