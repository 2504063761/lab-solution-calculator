"""Separate, atomic, user-local material recipe library."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping
import unicodedata
import uuid

from materials_core import normalize_request
from mix_core import InputError
from template_store import StorageError, default_data_dir


def _name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError("请填写材料模板名称。")
    value = value.strip()
    if len(value) > 120 or any(unicodedata.category(char) in ("Cc", "Cf", "Cs") for char in value):
        raise InputError("材料模板名称不能超过 120 字，且不能含控制字符。")
    return value


class MaterialStore:
    def __init__(self, directory: Path | str | None = None):
        self.directory = Path(directory) if directory is not None else default_data_dir()
        self.path = self.directory / "materials_templates.json"
        self._profiles: list[dict[str, Any]] = []
        self.ready = False

    @property
    def profiles(self) -> list[dict[str, Any]]:
        return deepcopy(self._profiles)

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            self._profiles = []
            self.ready = True
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8-sig"),
                                 parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"无效数值 {value}")))
            if (not isinstance(payload, dict) or type(payload.get("schema_version")) is not int or
                    payload["schema_version"] != 1 or not isinstance(payload.get("profiles"), list)):
                raise ValueError("材料模板文件版本或格式不受支持")
            parsed, names, identifiers = [], set(), set()
            for raw in payload["profiles"]:
                if not isinstance(raw, dict):
                    raise ValueError("材料模板格式无效")
                identifier = raw.get("id")
                if (not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 128 or
                        any(unicodedata.category(char) in ("Cc", "Cf", "Cs") for char in identifier) or
                        identifier in identifiers):
                    raise ValueError("材料模板标识无效或重复")
                name = _name(raw.get("name"))
                if name.casefold() in names:
                    raise ValueError("材料模板名称重复")
                parsed.append({"id": identifier, "name": name,
                               "recipe": normalize_request(raw.get("recipe"), complete=False)})
                names.add(name.casefold())
                identifiers.add(identifier)
        except (OSError, UnicodeError, ValueError, TypeError, AttributeError) as error:
            self.ready = False
            raise StorageError(f"材料模板文件无法读取，原文件已保留。\n{self.path}\n原因：{error}") from error
        self._profiles = parsed
        self.ready = True
        return self.profiles

    def _refresh(self) -> None:
        if not self.ready:
            raise StorageError("材料模板库尚未成功读取，不能覆盖原文件。请检查材料模板文件后重新启动程序。")
        self.load()

    def _write(self, entries: list[dict[str, Any]]) -> None:
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=self.directory,
                                             prefix="materials_templates_", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({"schema_version": 1, "profiles": entries}, stream,
                          ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except (OSError, ValueError, TypeError) as error:
            raise StorageError(f"材料模板保存失败，已有模板未改变。\n{self.path}\n原因：{error}") from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def _commit(self, entries: list[dict[str, Any]]) -> None:
        self._write(entries)
        self._profiles = deepcopy(entries)

    def get(self, identifier: str) -> dict[str, Any]:
        for entry in self._profiles:
            if entry["id"] == identifier:
                return deepcopy(entry)
        raise InputError("该材料模板已不存在，请重新选择。")

    def _entry(self, identifier: str, name: Any, data: Mapping[str, Any], except_id: str | None = None) -> dict[str, Any]:
        name = _name(name)
        if any(item["name"].casefold() == name.casefold() and item["id"] != except_id for item in self._profiles):
            raise InputError(f"材料模板“{name}”已存在。请换一个名称，或更新当前模板。")
        return {"id": identifier, "name": name, "recipe": normalize_request(data, complete=False)}

    def create(self, name: str, data: Mapping[str, Any]) -> dict[str, Any]:
        self._refresh()
        entry = self._entry(str(uuid.uuid4()), name, data)
        self._commit(self._profiles + [entry])
        return deepcopy(entry)

    def update(self, identifier: str, name: str, data: Mapping[str, Any]) -> dict[str, Any]:
        self._refresh()
        self.get(identifier)
        entry = self._entry(identifier, name, data, except_id=identifier)
        self._commit([entry if item["id"] == identifier else item for item in self._profiles])
        return deepcopy(entry)

    def delete(self, identifier: str) -> None:
        self._refresh()
        self.get(identifier)
        self._commit([entry for entry in self._profiles if entry["id"] != identifier])
