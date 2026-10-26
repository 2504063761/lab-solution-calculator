"""Bridge and persistence checks with isolated synthetic software data."""
import copy
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from glass_bridge import GlassBridge
from materials_core import materials_csv
from mix_core import parse_recipe
from template_store import StorageError, TemplateStore
from cfu_store import CalibrationStore
from materials_store import MaterialStore
from test_core_public import synthetic_mix, synthetic_material, synthetic_molar


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="public_calculator_")
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.bridge = GlassBridge(self.root)

    def calibration(self):
        return {"name": "Synthetic coefficient", "species": "Sample A", "coefficient": "4e7",
                "od_min": ".1", "od_max": ".6", "notes": "Software fixture only"}

    def test_generic_defaults_have_no_measurements_or_calibration(self):
        startup = self.bridge.bootstrap()["data"]
        self.assertEqual([c["name"] for c in startup["recipe"]["cultures"]], ["A", "B", "C"])
        self.assertTrue(all(c["od"] is None for c in startup["recipe"]["cultures"]))
        self.assertEqual(self.bridge.materials_bootstrap()["data"]["profiles"], [])
        self.assertEqual(self.bridge.cfu_bootstrap()["data"]["profiles"], [])

    def test_all_three_template_libraries_are_independent_and_reopen(self):
        mix = self.bridge.save_template("Mix software fixture", synthetic_mix(), False)["data"]["current"]
        mix_before = (self.root / "templates.json").read_bytes()
        material = self.bridge.materials_save_template("Material software fixture", synthetic_molar())["data"]["profile"]
        calibration = self.bridge.cfu_save_profile(self.calibration())["data"]["profile"]
        self.assertEqual((self.root / "templates.json").read_bytes(), mix_before)
        reopened = GlassBridge(self.root)
        loaded_mix = reopened.load_template(mix["id"])["data"]["current"]
        self.assertTrue(all(c["od"] is None for c in loaded_mix["recipe"]["cultures"]))
        loaded_material = reopened.materials_load_template(material["id"])["data"]["profile"]
        self.assertEqual(loaded_material["recipe"]["components"][0]["molar_mass_unit"], "g/mol")
        self.assertEqual(reopened.cfu_load_profile(calibration["id"])["data"]["profile"]["coefficient"], 4e7)

    def test_changed_or_replaced_mix_result_cannot_be_copied(self):
        data = synthetic_mix()
        old = self.bridge.calculate(data)["data"]["id"]
        with patch("glass_bridge.clipboard_text") as clipboard:
            changed = {**data, "volume": "1300"}
            self.assertFalse(self.bridge.copy_result(old, changed)["ok"])
            new = self.bridge.calculate(data)["data"]["id"]
            self.assertFalse(self.bridge.copy_result(old, data)["ok"])
            self.assertTrue(self.bridge.copy_result(new, data)["ok"])
            clipboard.assert_called_once()

    def test_material_molar_mass_or_unit_change_invalidates_output(self):
        data = synthetic_molar()
        result = self.bridge.materials_calculate(data)["data"]
        variants = [{**data, "mass_unit": "μg"}]
        for field, value in (("molar_mass", "600"), ("molar_mass_unit", "mg/mol"), ("concentration_unit", "mM")):
            changed = copy.deepcopy(data)
            changed["components"][0][field] = value
            variants.append(changed)
        with patch("glass_bridge.clipboard_text") as clipboard:
            for changed in variants:
                self.assertFalse(self.bridge.materials_copy_result(result["id"], changed)["ok"])
            self.assertTrue(self.bridge.materials_copy_result(result["id"], data)["ok"])
            clipboard.assert_called_once()

    def test_result_lifetimes_are_independent_across_modules(self):
        mix_data = synthetic_mix()
        material_data = synthetic_material()
        mix_id = self.bridge.calculate(mix_data)["data"]["id"]
        material_id = self.bridge.materials_calculate(material_data)["data"]["id"]
        self.bridge.cfu_convert({"direction": "od_to_cfu", "value": ".25", "dilution": "8", "calibration": self.calibration()})
        with patch("glass_bridge.clipboard_text"):
            self.assertTrue(self.bridge.copy_result(mix_id, mix_data)["ok"])
            self.assertTrue(self.bridge.materials_copy_result(material_id, material_data)["ok"])

    def test_exported_csv_has_bom_and_matches_display_calculation(self):
        data = synthetic_molar()
        result = self.bridge.materials_calculate(data)["data"]
        path = self.root / "material_result.csv"
        self.bridge._window = Mock()
        self.bridge._window.create_file_dialog.return_value = (str(path),)
        self.assertTrue(self.bridge.materials_export_result(result["id"], data)["ok"])
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertEqual(list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig")))),
                         list(csv.reader(io.StringIO(materials_csv(result)))))

    def test_corrupted_material_library_is_preserved_and_mix_still_works(self):
        self.bridge.materials_save_template("Material software fixture", synthetic_material())
        path = self.root / "materials_templates.json"
        path.write_text("broken fixture", encoding="utf-8")
        reopened = GlassBridge(self.root)
        self.assertTrue(reopened.materials_bootstrap()["data"]["storage_error"])
        self.assertFalse(reopened.materials_save_template("Another fixture", synthetic_material())["ok"])
        self.assertTrue(reopened.calculate(synthetic_mix())["ok"])
        self.assertTrue(reopened.materials_calculate(synthetic_material())["ok"])
        self.assertEqual(path.read_text(encoding="utf-8"), "broken fixture")

    def test_corrupted_cfu_and_mix_libraries_cannot_be_overwritten(self):
        for filename, store_class in (("templates.json", TemplateStore), ("cfu_calibrations.json", CalibrationStore)):
            path = self.root / filename
            path.write_text("broken fixture", encoding="utf-8")
            store = store_class(self.root)
            with self.subTest(filename=filename), self.assertRaises(StorageError):
                store.load()
            self.assertEqual(path.read_text(encoding="utf-8"), "broken fixture")


if __name__ == "__main__":
    unittest.main()
