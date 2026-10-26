"""Headless frozen-EXE checks using synthetic coefficients, never biological defaults."""
import math
import tempfile

from cfu_core import convert_cfu, conversion_table
from cfu_store import CalibrationStore


def verify_cfu_bundle():
    calibration = {"name": "软件测试系数", "species": "测试菌种", "coefficient": "2e8",
                   "od_min": ".1", "od_max": ".5", "notes": "合成测试数据，不用于实验"}
    data = {"direction": "od_to_cfu", "value": ".25", "dilution": "10", "calibration": calibration}
    result = convert_cfu(data)
    assert result["cfu_ml"] == 5e8 and result["measured_od"] == .25 and result["stock_od"] == 2.5
    assert not result["warnings"]
    reverse = convert_cfu({**data, "direction": "cfu_to_od", "value": "5e8"})
    assert math.isclose(reverse["measured_od"], .25) and reverse["stock_od"] == 2.5
    extrapolated = convert_cfu({**data, "value": ".8"})
    assert any("外推" in warning for warning in extrapolated["warnings"])
    assert "外推" in str(conversion_table(extrapolated))
    with tempfile.TemporaryDirectory(prefix="cfu_bundle_verify_") as folder:
        store = CalibrationStore(folder)
        assert store.load() == [] and not store.path.exists()
        item = store.create(calibration)
        reopened = CalibrationStore(folder)
        reopened.load()
        assert reopened.get(item["id"])["coefficient"] == 2e8
        reopened.update(item["id"], {**calibration, "name": "更新测试方案", "coefficient": "4e8"})
        final = CalibrationStore(folder)
        final.load()
        assert final.get(item["id"])["coefficient"] == 4e8
        final.delete(item["id"])
        assert final.load() == []
    return ["OD600–CFU 双向换算与测前稀释倍数（合成测试系数）",
            "实测 OD600 校准范围与外推标记", "校准系数独立保存、重开、更新、调用和删除"]
