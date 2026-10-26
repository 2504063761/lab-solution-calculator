"""Package only the executable, generic documentation, assets and notices."""
import hashlib
from pathlib import Path
import zipfile

from app_identity import APP_NAME, VERSION

ROOT = Path(__file__).resolve().parent


def main():
    folder = ROOT / "dist" / VERSION
    exe = folder / f"{APP_NAME}.exe"
    output = folder / f"lab-solution-calculator-v{VERSION}-windows.zip"
    files = [exe, ROOT / "README.md", ROOT / "LICENSE", ROOT / "THIRD_PARTY_NOTICES.md"]
    files.extend(p for p in (ROOT / "docs").rglob("*") if p.is_file())
    files.extend(p for p in (ROOT / "third_party_licenses").iterdir() if p.is_file())
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            name = path.name if path == exe else path.relative_to(ROOT).as_posix()
            archive.write(path, f"{APP_NAME}/" + name)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert not any("templates.json" in name or "__pycache__" in name for name in archive.namelist())
    checksums = folder / "SHA256SUMS.txt"
    checksums.write_text("".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
                                for path in (exe, output)), encoding="utf-8")
    print(f"Created {output.name}")


if __name__ == "__main__":
    main()
