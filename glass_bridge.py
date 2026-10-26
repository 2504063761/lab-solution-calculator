"""Local display adapter. All arithmetic and template persistence stay in the existing modules."""

import csv
import ctypes
import io
from ctypes import wintypes
from dataclasses import asdict
from functools import wraps
from pathlib import Path
import threading
import uuid

from mix_core import (InputError, calculate_mix, compact, empty_recipe, example_recipe, parse_recipe,
                      result_csv, result_table, result_text)
from template_store import StorageError, TemplateStore
from ui_preferences import read_visual_preferences
from cfu_core import convert_cfu, conversion_table, format_number
from cfu_store import CalibrationStore
from materials_core import calculate_materials, normalize_request, materials_text, materials_csv
from materials_store import MaterialStore

from app_identity import APP_NAME, VERSION


def clipboard_text(text):
    """Copy Unicode text without a second GUI event loop."""
    user, kernel = ctypes.windll.user32, ctypes.windll.kernel32
    kernel.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalLock.restype = wintypes.LPVOID
    kernel.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalFree.argtypes = [wintypes.HGLOBAL]
    user.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user.SetClipboardData.restype = wintypes.HANDLE
    payload = (text + "\0").encode("utf-16-le")
    handle = kernel.GlobalAlloc(0x0002, len(payload))
    if not handle:
        raise OSError("无法分配剪贴板内存。")
    owned = True
    try:
        pointer = kernel.GlobalLock(handle)
        if not pointer:
            raise OSError("无法写入剪贴板。")
        ctypes.memmove(pointer, payload, len(payload))
        kernel.GlobalUnlock(handle)
        if not user.OpenClipboard(None):
            raise OSError("剪贴板正被其他程序使用，请重试。")
        try:
            if not user.EmptyClipboard() or not user.SetClipboardData(13, handle):
                raise OSError("复制失败，请重试。")
            owned = False
        finally:
            user.CloseClipboard()
    finally:
        if owned:
            kernel.GlobalFree(handle)


def response(function):
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            try:
                return {"ok": True, "data": function(self, *args, **kwargs)}
            except (InputError, StorageError, OSError) as error:
                return {"ok": False, "error": str(error), "maximum_od": getattr(error, "maximum_od", None)}
    return wrapped


class GlassBridge:
    def __init__(self, directory=None):
        self._lock = threading.RLock()
        self._window = None
        self._store = TemplateStore(directory)
        self._storage_error = None
        self._result = None
        self._result_id = None
        self._cfu_store = CalibrationStore(directory)
        self._cfu_storage_error = None
        self._cfu_result = None
        self._cfu_result_id = None
        self._materials_store = MaterialStore(directory)
        self._materials_storage_error = None
        self._materials_result = None
        self._materials_result_id = None
        try:
            self._store.load()
        except StorageError as error:
            self._storage_error = str(error)
        try:
            self._cfu_store.load()
        except StorageError as error:
            self._cfu_storage_error = str(error)
        try:
            self._materials_store.load()
        except StorageError as error:
            self._materials_storage_error = str(error)

    def _templates(self):
        return [item.as_dict() for item in self._store.templates]

    @response
    def bootstrap(self):
        initial = self._store.templates[0] if self._store.templates else None
        return {"version": VERSION, "app_name": APP_NAME, "templates": self._templates(), "preferences": asdict(read_visual_preferences()),
                "recipe": initial.recipe.as_dict() if initial else example_recipe().as_dict(),
                "current": initial.as_dict() if initial else None, "empty_recipe": empty_recipe().as_dict(),
                "storage_error": self._storage_error}

    @response
    def calculate(self, data):
        self._result = self._result_id = None
        result = calculate_mix(parse_recipe(data, complete=True))
        self._result = result
        self._result_id = str(uuid.uuid4())
        headers, rows = result_table(result)
        return {"id": self._result_id, "headers": headers, "rows": rows, "total_ul": result.total_ul,
                "theoretical_od": result.theoretical_od, "maximum_od": result.maximum_od,
                "total_display": f"{result.total_ul:.3f}", "od_display": compact(result.theoretical_od)}

    def _current(self, result_id, data):
        if not self._result or result_id != self._result_id or parse_recipe(data, complete=True) != self._result.recipe:
            raise InputError("输入已改变，请重新计算后再复制或导出。")
        return self._result

    @response
    def copy_result(self, result_id, data):
        clipboard_text(result_text(self._current(result_id, data)))
        return "配液表已复制，可粘贴到 Excel。"

    @response
    def export_result(self, result_id, data):
        result = self._current(result_id, data)
        import webview
        paths = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename="菌液配比结果.csv",
                                                file_types=("CSV 文件 (*.csv)",))
        if not paths:
            return None
        path = Path(paths[0])
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        path.write_text(result_csv(result), encoding="utf-8-sig", newline="")
        return f"已导出：{path.name}"

    @response
    def save_template(self, name, data, include_od, template_id=None):
        if not isinstance(include_od, bool):
            raise InputError("请正确选择是否包含初始 OD。")
        recipe = parse_recipe(data, complete=False)
        item = (self._store.update(template_id, name, recipe, include_od) if template_id
                else self._store.create(name, recipe, include_od))
        return {"current": item.as_dict(), "templates": self._templates()}

    @response
    def load_template(self, template_id):
        if self._store.ready:
            self._store.load()
        current = self._store.get(template_id)
        self._result = self._result_id = None
        return {"current": current.as_dict(), "templates": self._templates()}

    @response
    def rename_template(self, template_id, name):
        item = self._store.rename(template_id, name)
        return {"current": item.as_dict(), "templates": self._templates()}

    @response
    def delete_template(self, template_id):
        self._store.delete(template_id)
        return {"templates": self._templates()}

    @response
    def cfu_bootstrap(self):
        try:
            self._cfu_store.load()
            self._cfu_storage_error = None
        except StorageError as error:
            self._cfu_storage_error = str(error)
        return {"profiles": [] if self._cfu_storage_error else self._cfu_store.calibrations,
                "storage_error": self._cfu_storage_error}

    def _invalidate_cfu(self):
        self._cfu_result = self._cfu_result_id = None

    @response
    def cfu_convert(self, data):
        self._invalidate_cfu()
        result = convert_cfu(data)
        headers, rows = conversion_table(result)
        self._cfu_result = result
        self._cfu_result_id = str(uuid.uuid4())
        return {**result, "id": self._cfu_result_id, "headers": headers, "rows": rows,
                "display": {key: format_number(result[key])
                            for key in ("cfu_ml", "measured_od", "stock_od")}}

    def _current_cfu(self, result_id, data):
        message = "换算输入或校准系数已改变，请重新换算后再复制或导出。"
        if self._cfu_result is None or result_id != self._cfu_result_id:
            raise InputError(message)
        try:
            unchanged = convert_cfu(data) == self._cfu_result
        except InputError:
            unchanged = False
        if not unchanged:
            raise InputError(message)
        return self._cfu_result

    @response
    def cfu_copy_result(self, result_id, data):
        headers, rows = conversion_table(self._current_cfu(result_id, data))
        clipboard_text("\n".join("\t".join(row) for row in [headers, *rows]))
        return "OD600–CFU 估算结果已复制，可粘贴到 Excel。"

    @response
    def cfu_export_result(self, result_id, data):
        headers, rows = conversion_table(self._current_cfu(result_id, data))
        import webview
        paths = self._window.create_file_dialog(webview.FileDialog.SAVE,
            save_filename="OD600-CFU估算结果.csv", file_types=("CSV 文件 (*.csv)",))
        if not paths:
            return None
        path = Path(paths[0])
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerows([headers, *rows])
        path.write_text(stream.getvalue(), encoding="utf-8-sig", newline="")
        return f"已导出：{path.name}"

    @response
    def cfu_save_profile(self, data, profile_id=None):
        profile = (self._cfu_store.update(profile_id, data) if profile_id
                   else self._cfu_store.create(data))
        self._invalidate_cfu()
        return {"profile": profile, "profiles": self._cfu_store.calibrations}

    @response
    def cfu_load_profile(self, profile_id):
        try:
            self._cfu_store.load()
            self._cfu_storage_error = None
        except StorageError as error:
            self._cfu_storage_error = str(error)
            raise
        profile = self._cfu_store.get(profile_id)
        self._invalidate_cfu()
        return {"profile": profile, "profiles": self._cfu_store.calibrations}

    @response
    def cfu_delete_profile(self, profile_id):
        self._cfu_store.delete(profile_id)
        self._invalidate_cfu()
        return {"profiles": self._cfu_store.calibrations}

    @response
    def materials_bootstrap(self):
        try:
            self._materials_store.load()
            self._materials_storage_error = None
        except StorageError as error:
            self._materials_storage_error = str(error)
        return {"profiles": [] if self._materials_storage_error else self._materials_store.profiles,
                "storage_error": self._materials_storage_error}

    def _invalidate_materials(self):
        self._materials_result = self._materials_result_id = None

    @response
    def materials_calculate(self, data):
        self._invalidate_materials()
        result = calculate_materials(data)
        self._materials_result = result
        self._materials_result_id = str(uuid.uuid4())
        return {**result, "id": self._materials_result_id}

    def _current_materials(self, result_id, data):
        message = "材料配制输入已改变，请重新计算后再复制或导出。"
        if self._materials_result is None or result_id != self._materials_result_id:
            raise InputError(message)
        try:
            unchanged = normalize_request(data) == self._materials_result["request"]
        except InputError:
            unchanged = False
        if not unchanged:
            raise InputError(message)
        return self._materials_result

    @response
    def materials_copy_result(self, result_id, data):
        clipboard_text(materials_text(self._current_materials(result_id, data)))
        return "材料配制表已复制，可粘贴到 Excel。"

    @response
    def materials_export_result(self, result_id, data):
        result = self._current_materials(result_id, data)
        import webview
        paths = self._window.create_file_dialog(webview.FileDialog.SAVE,
            save_filename="材料配制结果.csv", file_types=("CSV 文件 (*.csv)",))
        if not paths:
            return None
        path = Path(paths[0])
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        path.write_text(materials_csv(result), encoding="utf-8-sig", newline="")
        return f"已导出：{path.name}"

    @response
    def materials_save_template(self, name, data, template_id=None):
        profile = (self._materials_store.update(template_id, name, data) if template_id
                   else self._materials_store.create(name, data))
        return {"profile": profile, "profiles": self._materials_store.profiles}

    @response
    def materials_load_template(self, template_id):
        try:
            self._materials_store.load()
            self._materials_storage_error = None
        except StorageError as error:
            self._materials_storage_error = str(error)
            raise
        profile = self._materials_store.get(template_id)
        self._invalidate_materials()
        return {"profile": profile, "profiles": self._materials_store.profiles}

    @response
    def materials_delete_template(self, template_id):
        self._materials_store.delete(template_id)
        return {"profiles": self._materials_store.profiles}
