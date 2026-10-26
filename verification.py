"""Frozen-app checks using generic, synthetic software fixtures only."""

from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
import tempfile

from mix_core import FeasibilityError, calculate_mix, parse_recipe, result_csv, result_document
from template_store import TemplateStore
from app_identity import APP_NAME, VERSION


def synthetic_recipe(mode="separate", unit="µL", volume=1200):
    """A/B/C and these numbers are synthetic arithmetic fixtures, not measurements."""
    return parse_recipe({"cultures": [
        {"name": "A", "od": 2, "dilution": 1, "ratio": 1},
        {"name": "B", "od": 4, "dilution": 1, "ratio": 1},
        {"name": "C", "od": 1.5, "dilution": 1, "ratio": 2}],
        "target_od": 1, "volume": volume, "unit": unit, "mode": mode}, complete=True)


def verify_bundle(report_path: Path):
    checks = []
    try:
        result = calculate_mix(synthetic_recipe())
        expected = [150.0, 75.0, 400.0]
        assert all(math.isclose(p.culture_ul, value, rel_tol=1e-12)
                   for p, value in zip(result.portions, expected))
        assert math.isclose(result.culture_ul + result.diluent_ul, 1200, rel_tol=1e-12)
        assert math.isclose(result.theoretical_od, 1, rel_tol=1e-12)
        checks.append("通用合成算例和体积守恒")
        direct = calculate_mix(synthetic_recipe("direct"))
        assert all(math.isclose(p.culture_ul, q.culture_ul, rel_tol=1e-12)
                   for p, q in zip(result.portions, direct.portions))
        checks.append("两种配液流程")
        converted = calculate_mix(synthetic_recipe(unit="mL", volume=1.2))
        assert math.isclose(converted.total_ul, result.total_ul, rel_tol=1e-12)
        checks.append("体积单位换算")
        invalid = synthetic_recipe().as_dict()
        invalid["target_od"] = 1.1
        try:
            calculate_mix(parse_recipe(invalid, complete=True))
            raise AssertionError("没有拒绝不可行配方")
        except FeasibilityError as error:
            assert math.isclose(error.maximum_od, 1, rel_tol=1e-12)
        checks.append("不可行配方检查")
        with tempfile.TemporaryDirectory(prefix="mix_bundle_verify_") as folder:
            store = TemplateStore(folder)
            store.load()
            first = store.create("不含 OD 的模板", synthetic_recipe(), False)
            second = store.create("含 OD 的模板", synthetic_recipe("direct"), True)
            reopened = TemplateStore(folder)
            reopened.load()
            assert all(c.od is None for c in reopened.get(first.id).recipe.cultures)
            assert reopened.get(second.id).recipe.cultures[0].od == 2
            renamed = reopened.rename(first.id, "重命名后")
            assert renamed.name == "重命名后"
            reopened.delete(first.id)
            final = TemplateStore(folder)
            final.load()
            assert len(final.templates) == 2
            assert final.get(second.id).recipe.mode == "direct"
        checks.append("模板保存、重开、调用、重命名和删除")
        assert list(csv.reader(io.StringIO(result_csv(result)))) == result_document(result)
        checks.append("导出表与结果一致")
        report = {"passed": True, "version": VERSION, "app_name": APP_NAME, "checks": checks,
                  "synthetic_raw_ul": [p.culture_ul for p in result.portions],
                  "synthetic_diluent_ul": [p.diluent_ul for p in result.portions],
                  "theoretical_od": result.theoretical_od}
    except Exception as error:
        report = {"passed": False, "checks": checks, "error": repr(error)}
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    verify_bundle(Path("verification_report.json"))
