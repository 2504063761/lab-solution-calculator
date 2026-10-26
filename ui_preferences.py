"""Read Windows visual preferences without changing any system settings."""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import sys


@dataclass(frozen=True)
class VisualPreferences:
    reduce_transparency: bool = False
    reduce_motion: bool = False
    high_contrast: bool = False


def _system_bool(action, default):
    try:
        value = wintypes.BOOL()
        if ctypes.windll.user32.SystemParametersInfoW(action, 0, ctypes.byref(value), 0):
            return bool(value.value)
    except (AttributeError, OSError):
        pass
    return default


def _transparency_enabled():
    try:
        import winreg
        path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ) as key:
            return bool(winreg.QueryValueEx(key, "EnableTransparency")[0])
    except (ImportError, OSError, ValueError):
        return True


def _high_contrast_enabled():
    class HighContrast(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwFlags", wintypes.DWORD),
                    ("lpszDefaultScheme", wintypes.LPWSTR)]

    try:
        value = HighContrast()
        value.cbSize = ctypes.sizeof(value)
        if ctypes.windll.user32.SystemParametersInfoW(0x0042, value.cbSize, ctypes.byref(value), 0):
            return bool(value.dwFlags & 1)  # HCF_HIGHCONTRASTON
    except (AttributeError, OSError):
        pass
    return False


def read_visual_preferences():
    if sys.platform != "win32":
        return VisualPreferences(reduce_transparency=True, reduce_motion=True)
    return VisualPreferences(
        reduce_transparency=not _transparency_enabled() or _system_bool(0x1040, False),
        reduce_motion=not _system_bool(0x1042, True),
        high_contrast=_high_contrast_enabled())


def read_system_colors():
    """Return the active contrast theme's colors, or a readable solid fallback."""
    defaults = {"window": "#FFFFFF", "text": "#000000", "selection": "#000080", "selection_text": "#FFFFFF"}
    if sys.platform != "win32":
        return defaults
    try:
        for name, index in (("window", 5), ("text", 8), ("selection", 13), ("selection_text", 14)):
            value = ctypes.windll.user32.GetSysColor(index)
            defaults[name] = f"#{value & 255:02X}{value >> 8 & 255:02X}{value >> 16 & 255:02X}"
    except (AttributeError, OSError):
        pass
    return defaults
