"""Small packaged-runtime checks; examples are software fixtures, not protocols."""
from pathlib import Path
import tempfile

from glass_bridge import GlassBridge
from materials_core import calculate_materials, materials_csv


def verify_materials_bundle():
    checks = []
    for basis, unit in (("ww", "g"), ("wv", "mL"), ("vv", "mL")):
        data = {"basis": basis, "total": "20", "unit": unit, "solvent": "测试基质",
                "components": [{"name": "测试材料", "percent": "20"}]}
        result = calculate_materials(data)
        assert result["basis"] == basis and result["rows"]
        assert "测试材料" in materials_csv(result)
        if basis in ("wv", "vv"):
            assert "定容" in materials_csv(result)
    checks.append("材料 w/w、w/v、v/v 独立计算及定容说明可用")
    molar = {"basis": "molar", "total": "20", "unit": "mL", "mass_unit": "mg", "solvent": "测试溶剂",
             "components": [{"name": "摩尔软件测试", "concentration": "10", "concentration_unit": "μM",
                             "molar_mass": "500", "molar_mass_unit": "g/mol"}]}
    assert calculate_materials(molar)["rows"][0][3:5] == ["0.1", "mg"]
    molar["components"][0].update(molar_mass="500000", molar_mass_unit="mg/mol")
    assert calculate_materials(molar)["rows"][0][3:5] == ["0.1", "mg"]
    checks.append("摩尔浓度与 g/mol、mg/mol 换算，10 μM×20 mL×500 g/mol = 0.1 mg")
    with tempfile.TemporaryDirectory(prefix="materials_bundle_") as folder:
        bridge = GlassBridge(folder)
        assert bridge.materials_bootstrap()["data"]["profiles"] == []
        original = Path(folder, "templates.json").read_bytes()
        profile = bridge.materials_save_template("软件测试模板", data)["data"]["profile"]
        reopened = GlassBridge(folder)
        assert reopened.materials_load_template(profile["id"])["ok"]
        assert Path(folder, "templates.json").read_bytes() == original
        molar_profile = bridge.materials_save_template("摩尔软件测试模板", molar)["data"]["profile"]
        reopened = GlassBridge(folder)
        loaded = reopened.materials_load_template(molar_profile["id"])["data"]["profile"]["recipe"]
        assert calculate_materials(loaded)["rows"][0][3:5] == ["0.1", "mg"]
    checks.append("材料模板可独立保存/重读，菌液模板保持兼容")
    return checks
