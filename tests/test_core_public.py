"""Public tests use generic, deliberately synthetic software fixtures only."""
import copy
import csv
from decimal import Decimal
import io
import math
import unittest

from cfu_core import convert_cfu
from materials_core import calculate_materials, materials_csv, normalize_request
from mix_core import FeasibilityError, InputError, calculate_mix, parse_recipe, result_csv, result_document


def synthetic_mix(mode="separate", volume="1200", unit="µL"):
    return {"cultures": [{"name": "A", "od": "2", "dilution": "1", "ratio": "1"},
                         {"name": "B", "od": "4", "dilution": "1", "ratio": "1"},
                         {"name": "C", "od": "1.5", "dilution": "1", "ratio": "2"}],
            "target_od": "1", "volume": volume, "unit": unit, "mode": mode}


def synthetic_material(basis="ww", total="20", unit="g"):
    return {"basis": basis, "total": total, "unit": unit, "solvent": "Solvent",
            "components": [{"name": "Material A", "percent": "20"}]}


def synthetic_molar():
    return {"basis": "molar", "total": "20", "unit": "mL", "mass_unit": "mg", "solvent": "Solvent",
            "components": [{"name": "Material A", "concentration": "10", "concentration_unit": "μM",
                            "molar_mass": "500", "molar_mass_unit": "g/mol"}]}


class MixingTests(unittest.TestCase):
    def test_separate_fixture_preserves_volume_and_od_contribution(self):
        result = calculate_mix(parse_recipe(synthetic_mix(), complete=True))
        self.assertEqual([p.culture_ul for p in result.portions], [150, 75, 400])
        self.assertEqual([p.diluent_ul for p in result.portions], [250, 325, 0])
        self.assertEqual([p.prepared_ul for p in result.portions], [400, 400, 400])
        self.assertAlmostEqual(result.theoretical_od, 1)
        self.assertAlmostEqual(result.maximum_od, 1)
        self.assertAlmostEqual(result.culture_ul + result.diluent_ul, 1200)
        self.assertEqual([p.contribution_od for p in result.portions], [.25, .25, .5])

    def test_direct_fixture_has_one_shared_diluent_amount(self):
        result = calculate_mix(parse_recipe(synthetic_mix("direct"), complete=True))
        self.assertEqual([p.culture_ul for p in result.portions], [150, 75, 400])
        self.assertEqual(result.diluent_ul, 575)
        self.assertTrue(all(p.diluent_ul is None for p in result.portions))
        self.assertAlmostEqual(result.maximum_od, 1.92)

    def test_measurement_dilution_and_volume_units_are_equivalent(self):
        original = calculate_mix(parse_recipe(synthetic_mix(), complete=True))
        diluted = synthetic_mix(volume="1.2", unit="mL")
        for row in diluted["cultures"]:
            row["od"] = str(float(row["od"]) / 10)
            row["dilution"] = "10"
        result = calculate_mix(parse_recipe(diluted, complete=True))
        self.assertEqual(result.total_ul, original.total_ul)
        for first, second in zip(result.portions, original.portions):
            self.assertAlmostEqual(first.culture_ul, second.culture_ul)

    def test_feasibility_depends_on_selected_process(self):
        data = synthetic_mix()
        data["target_od"] = "1.1"
        with self.assertRaises(FeasibilityError) as caught:
            calculate_mix(parse_recipe(data, complete=True))
        self.assertAlmostEqual(caught.exception.maximum_od, 1)
        data["mode"] = "direct"
        result = calculate_mix(parse_recipe(data, complete=True))
        self.assertAlmostEqual(result.theoretical_od, 1.1)
        self.assertGreater(result.diluent_ul, 0)

    def test_csv_contains_same_input_and_result_cells(self):
        result = calculate_mix(parse_recipe(synthetic_mix(), complete=True))
        self.assertEqual(list(csv.reader(io.StringIO(result_csv(result)))), result_document(result))
        self.assertIn("实验配液计算器", result_csv(result))

    def test_invalid_values_and_duplicate_names_are_rejected(self):
        for value in ("NaN", "Inf", "-1", "0", "", True):
            data = synthetic_mix()
            data["cultures"][0]["od"] = value
            with self.subTest(value=value), self.assertRaises(InputError):
                parse_recipe(data, complete=True)
        data = synthetic_mix()
        data["cultures"][1]["name"] = "a"
        with self.assertRaises(InputError):
            parse_recipe(data, complete=True)


class MaterialsTests(unittest.TestCase):
    def test_mass_fraction_uses_final_mass(self):
        data = synthetic_material()
        data["components"].append({"name": "Material B", "percent": ".5"})
        result = calculate_materials(data)
        self.assertEqual([row[2] for row in result["rows"]], ["4", "0.1", "15.9"])
        self.assertEqual(sum(Decimal(row[2]) for row in result["rows"]), Decimal(20))

    def test_volume_modes_specify_final_volume_not_exact_solvent_volume(self):
        mass_volume = calculate_materials(synthetic_material("wv", unit="mL"))
        volume_volume = synthetic_material("vv", "10", "mL")
        volume_volume["components"][0]["percent"] = "70"
        volume_volume = calculate_materials(volume_volume)
        self.assertEqual(mass_volume["rows"][0][2:4], ["4", "g"])
        self.assertEqual(volume_volume["rows"][0][2:4], ["7", "mL"])
        for result in (mass_volume, volume_volume):
            self.assertEqual(result["rows"][-1][2], "适量")
            self.assertIn("定容", result["rows"][-1][-1])

    def test_molar_mass_and_output_units_have_correct_scale(self):
        data = synthetic_molar()
        self.assertEqual(calculate_materials(data)["rows"][0][3:5], ["0.1", "mg"])
        data["components"][0].update(molar_mass="500000", molar_mass_unit="mg/mol")
        self.assertEqual(calculate_materials(data)["rows"][0][3:5], ["0.1", "mg"])
        data["mass_unit"] = "μg"
        self.assertEqual(calculate_materials(data)["rows"][0][3:5], ["100", "μg"])

    def test_molar_concentration_units_and_volume_are_equivalent(self):
        for concentration, unit in ((".00001", "M"), (".01", "mM"), ("10", "μM"), ("10000", "nM")):
            data = synthetic_molar()
            data["components"][0].update(concentration=concentration, concentration_unit=unit)
            data.update(total="20000", unit="µL")
            with self.subTest(unit=unit):
                self.assertEqual(calculate_materials(data)["rows"][0][3], "0.1")

    def test_partial_molar_templates_can_be_saved_but_not_calculated(self):
        data = synthetic_molar()
        data["components"][0].update(concentration="", molar_mass="")
        partial = normalize_request(data, complete=False)
        self.assertIsNone(partial["components"][0]["molar_mass"])
        with self.assertRaises(InputError):
            calculate_materials(data)

    def test_invalid_concentrations_and_units_are_rejected(self):
        for field, value in (("concentration", "NaN"), ("concentration", "-1"), ("molar_mass", "0"),
                             ("molar_mass", ""), ("concentration_unit", "mm"), ("molar_mass_unit", "g/mL")):
            data = synthetic_molar()
            data["components"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(InputError):
                calculate_materials(data)

    def test_tiny_amounts_and_exported_formula_like_names_are_preserved_safely(self):
        data = synthetic_molar()
        data["components"][0].update(name="=1+1", concentration="1e-100")
        result = calculate_materials(data)
        self.assertGreater(Decimal(result["rows"][0][3]), 0)
        rows = list(csv.reader(io.StringIO(materials_csv(result))))
        self.assertEqual(rows[2][0], "'=1+1")
        self.assertEqual(result["rows"][0][0], "=1+1")


class CFUTests(unittest.TestCase):
    def calibration(self):
        return {"name": "Synthetic coefficient", "species": "Sample A", "coefficient": "4e7",
                "od_min": ".1", "od_max": ".6", "notes": "Software fixture only"}

    def test_forward_reverse_and_dilution(self):
        data = {"direction": "od_to_cfu", "value": ".25", "dilution": "8", "calibration": self.calibration()}
        result = convert_cfu(data)
        self.assertEqual(result["cfu_ml"], 8e7)
        self.assertEqual(result["stock_od"], 2)
        reverse = convert_cfu({**data, "direction": "cfu_to_od", "value": "8e7"})
        self.assertEqual(reverse["measured_od"], .25)

    def test_extrapolation_and_zero_are_not_claimed_as_measured_counts(self):
        data = {"direction": "od_to_cfu", "value": ".8", "dilution": "1", "calibration": self.calibration()}
        self.assertTrue(any("外推" in message for message in convert_cfu(data)["warnings"]))
        self.assertTrue(any("不能证明" in message for message in convert_cfu({**data, "value": "0"})["warnings"]))

    def test_calibration_must_be_provided_and_finite(self):
        for coefficient in ("", "0", "NaN", "-1"):
            calibration = self.calibration()
            calibration["coefficient"] = coefficient
            with self.subTest(coefficient=coefficient), self.assertRaises(InputError):
                convert_cfu({"direction": "od_to_cfu", "value": ".2", "dilution": "1", "calibration": calibration})


if __name__ == "__main__":
    unittest.main()
