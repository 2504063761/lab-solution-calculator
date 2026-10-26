"""Build the offline Windows application from this repository."""
import os
from pathlib import Path
import subprocess
import sys

from app_identity import APP_NAME, VERSION


def main():
    root = Path(__file__).resolve().parent
    os.chdir(root)
    os.environ["PYINSTALLER_CONFIG_DIR"] = str(root / ".build/cache")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed", "--noupx",
               "--icon", str(root / "assets/app.ico"), "--name", APP_NAME,
               "--distpath", str(root / "dist" / VERSION), "--workpath", str(root / ".build/work"),
               "--specpath", str(root / ".build"), "--collect-all", "webview", "--collect-all", "pythonnet",
               "--collect-all", "clr_loader", "--hidden-import", "webview.platforms.edgechromium"]
    for name in ("glass_ui", "assets", "third_party_licenses", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        destination = name if (root / name).is_dir() else "."
        command.extend(["--add-data", f"{root/name}{os.pathsep}{destination}"])
    command.append(str(root / "glass_app.py"))
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
