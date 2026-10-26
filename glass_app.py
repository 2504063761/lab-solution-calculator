"""Offline WebView2 frontend for the existing local calculator."""

import argparse
import ctypes
import json
from pathlib import Path
import sys

from glass_bridge import GlassBridge
from app_identity import APP_NAME, VERSION


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--self-test", type=Path)
    args = parser.parse_args()
    if args.self_test:
        from verification import verify_bundle
        verify_bundle(args.self_test)
        report = json.loads(args.self_test.read_text(encoding="utf-8"))
        report["version"] = VERSION
        from cfu_verification import verify_cfu_bundle
        from materials_verification import verify_materials_bundle
        try:
            report["checks"].extend(verify_cfu_bundle())
            report["checks"].extend(verify_materials_bundle())
        except Exception as error:
            report["passed"] = False
            report["error"] = repr(error)
            args.self_test.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            raise
        args.self_test.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    import webview
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    bridge = GlassBridge(args.data_dir)
    window = webview.create_window(f"{APP_NAME}  {VERSION}", str(root / "glass_ui/index.html"),
                                  js_api=bridge, width=1220, height=850, min_size=(960, 620),
                                  background_color="#E8F0FA", text_select=True)
    bridge._window = window
    webview.settings["ALLOW_DOWNLOADS"] = False
    try:
        webview.start(gui="edgechromium", private_mode=True, icon=str(root / "assets/app.ico"))
    except Exception as error:
        ctypes.windll.user32.MessageBoxW(None,
            "无法启动程序界面。此版本需要 Windows 的 Microsoft Edge WebView2 Runtime。\n"
            "请从 Microsoft 官方来源安装 WebView2 Runtime 后重试。\n\n" + str(error),
            f"{APP_NAME} · 界面未启动", 0x10)


if __name__ == "__main__":
    main()
