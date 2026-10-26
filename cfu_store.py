"""Atomic storage for user-supplied OD600/CFU calibration coefficients."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unicodedata
import uuid
from typing import Any, Mapping

from cfu_core import parse_calibration
from mix_core import InputError
from template_store import StorageError, default_data_dir


class CalibrationStore:
    def __init__(self, directory: Path | str | None = None):
        self.directory = Path(directory) if directory is not None else default_data_dir()
        self.path = self.directory / "cfu_calibrations.json"
        self._calibrations: list[dict[str, Any]] = []
        self.ready = False

    @property
    def calibrations(self) -> list[dict[str, Any]]:
        return deepcopy(self._calibrations)

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            self._calibrations = []
            self.ready = True
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8-sig"),
                                 parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"无效数值 {value}")))
            if (not isinstance(payload, dict) or type(payload.get("schema_version")) is not int or
                    payload["schema_version"] != 1 or not isinstance(payload.get("calibrations"), list)):
                raise ValueError("校准文件版本或格式不受支持")
            parsed, names, identifiers = [], set(), set()
            for raw in payload["calibrations"]:
                if not isinstance(raw, dict):
                    raise ValueError("校准方案格式无效")
                identifier = raw.get("id")
                if (not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 128 or
                        any(unicodedata.category(char) in ("Cc", "Cf", "Cs") for char in identifier) or
                        identifier in identifiers):
                    raise ValueError("校准方案标识无效或重复")
                entry = {"id": identifier, **parse_calibration(raw, require_name=True)}
                if entry["name"].casefold() in names:
                    raise ValueError("校准方案名称重复")
                parsed.append(entry)
                identifiers.add(identifier)
                names.add(entry["name"].casefold())
        except (OSError, UnicodeError, ValueError, TypeError, AttributeError) as error:
            self.ready = False
            raise StorageError(f"校准系数文件无法读取，原文件已保留。\n{self.path}\n原因：{error}") from error
        self._calibrations = parsed
        self.ready = True
        return self.calibrations

    def _refresh(self) -> None:
        if not self.ready:
            raise StorageError("校准库尚未成功读取，不能覆盖原文件。请检查校准系数文件后重新启动程序。")
        self.load()

    def _write(self, entries: list[dict[str, Any]]) -> None:
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=self.directory,
                                             prefix="cfu_calibrations_", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({"schema_version": 1, "calibrations": entries}, stream,
                          ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except (OSError, ValueError, TypeError) as error:
            raise StorageError(f"校准系数保存失败，已有校准方案未改变。\n{self.path}\n原因：{error}") from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def _commit(self, entries: list[dict[str, Any]]) -> None:
        self._write(entries)
        self._calibrations = deepcopy(entries)

    def get(self, identifier: str) -> dict[str, Any]:
        for entry in self._calibrations:
            if entry["id"] == identifier:
                return deepcopy(entry)
        raise InputError("该校准方案已不存在，请重新选择。")

    def _unique(self, data: Mapping[str, Any], except_id: str | None = None) -> dict[str, Any]:
        parsed = parse_calibration(data, require_name=True)
        if any(entry["name"].casefold() == parsed["name"].casefold() and entry["id"] != except_id
               for entry in self._calibrations):
            raise InputError(f"校准方案“{parsed['name']}”已存在。请换一个名称，或更新当前校准方案。")
        return parsed

    def create(self, data: Mapping[str, Any]) -> dict[str, Any]:
        self._refresh()
        entry = {"id": str(uuid.uuid4()), **self._unique(data)}
        self._commit(self._calibrations + [entry])
        return deepcopy(entry)

    def update(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        self._refresh()
        self.get(identifier)
        entry = {"id": identifier, **self._unique(data, except_id=identifier)}
        self._commit([entry if current["id"] == identifier else current for current in self._calibrations])
        return deepcopy(entry)

    def delete(self, identifier: str) -> None:
        self._refresh()
        self.get(identifier)
        self._commit([entry for entry in self._calibrations if entry["id"] != identifier])
