"""Render documentation screenshots using isolated synthetic fixtures only."""
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import webview
from app_identity import APP_NAME
from glass_bridge import GlassBridge
from verification import synthetic_recipe


def main():
    destination = ROOT / "docs/images"
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="documentation_demo_") as folder:
        bridge = GlassBridge(folder)
        window = webview.create_window(APP_NAME, str(ROOT / "glass_ui/index.html"), js_api=bridge,
                                       width=1220, height=850, background_color="#E8F0FA")
        bridge._window = window

        def js(expression):
            return window.evaluate_js(expression)

        def wait(expression):
            until = time.monotonic() + 20
            while time.monotonic() < until:
                if js(expression):
                    return
                time.sleep(.05)
            raise AssertionError("Demo UI did not become ready")

        def capture(name):
            from webview.platforms.winforms import BrowserView
            from System import Action
            from System.IO import FileAccess, FileMode, FileStream
            from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
            form = BrowserView.instances[window.uid]
            pending = []
            def start():
                stream = FileStream(str(destination / name), FileMode.Create, FileAccess.Write)
                pending.extend([stream, form.browser.webview.CoreWebView2.CapturePreviewAsync(
                    CoreWebView2CapturePreviewImageFormat.Png, stream)])
            form.Invoke(Action(start))
            try:
                pending[1].GetAwaiter().GetResult()
            finally:
                pending[0].Close()

        def run():
            try:
                wait("typeof state!=='undefined'&&state.ready&&materialState.ready")
                js("applyRecipe(" + json.dumps(synthetic_recipe().as_dict()) + ");void calculate()")
                wait("!!state.result")
                capture("overview.png")
                percent = {"basis": "wv", "total": "20", "unit": "mL", "solvent": "水",
                           "components": [{"name": "材料 A（合成示例）", "percent": "20"},
                                          {"name": "材料 B（合成示例）", "percent": "0.5"}]}
                js("switchModule('materials');materialApplyRecipe(" + json.dumps(percent) + ");void materialCalculate()")
                wait("!!materialState.result")
                capture("materials-percent.png")
                molar = {"basis": "molar", "total": "20", "unit": "mL", "mass_unit": "mg", "solvent": "水",
                         "components": [{"name": "材料 A（合成示例）", "concentration": "10", "concentration_unit": "μM",
                                         "molar_mass": "500", "molar_mass_unit": "g/mol"}]}
                js("materialApplyRecipe(" + json.dumps(molar) + ");void materialCalculate()")
                wait("!!materialState.result")
                capture("materials-molar.png")
                js("switchModule('mix');void cfuOpen()")
                wait("cfuState.ready")
                demo = {"cfuName": "合成演示系数", "cfuSpecies": "演示样品 A", "cfuCoefficient": "2e8",
                        "cfuOdMin": ".1", "cfuOdMax": ".5", "cfuNotes": "仅用于软件演示，不用于实验",
                        "cfuValue": ".25", "cfuDilution": "10"}
                js("Object.entries(" + json.dumps(demo) + ").forEach(([id,value])=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))});void cfuConvert()")
                wait("!!cfuState.result")
                capture("cfu.png")
                print("Created four synthetic documentation screenshots", flush=True)
            finally:
                window.destroy()
        webview.start(run, gui="edgechromium", private_mode=True, icon=str(ROOT / "assets/app.ico"))


if __name__ == "__main__":
    main()
