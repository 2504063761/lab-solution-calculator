"""User-local templates with validated, atomic JSON persistence."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mix_core import InputError, Recipe, example_recipe, parse_recipe


class StorageError(Exception):
    pass


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    include_od: bool
    recipe: Recipe

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "include_od": self.include_od,
                "recipe": self.recipe.as_dict(include_od=self.include_od)}


def default_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "菌液配比计算器"
    return Path.home() / "AppData" / "Local" / "菌液配比计算器"


def valid_name(name: str) -> str:
    if not isinstance(name, str):
        raise InputError("模板名称必须是文字。")
    name = name.strip()
    if not name:
        raise InputError("请填写模板名称。")
    if any(ord(char) < 32 for char in name):
        raise InputError("模板名称不能含换行或制表符。")
    return name


class TemplateStore:
    def __init__(self, directory: Path | str | None = None):
        self.directory = Path(directory) if directory is not None else default_data_dir()
        self.path = self.directory / "templates.json"
        self.templates: list[Template] = []
        self.ready = False

    def load(self) -> list[Template]:
        if not self.path.exists():
            initial = [Template(str(uuid.uuid4()), "通用示例 · A:B:C", False, example_recipe())]
            self._write(initial)
            self.templates = initial
            self.ready = True
            return list(self.templates)
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, dict) or payload.get("schema_version") != 1:
                raise ValueError("模板文件版本或格式不受支持")
            raw_templates = payload.get("templates")
            if not isinstance(raw_templates, list):
                raise ValueError("模板列表格式无效")
            parsed = []
            names, ids = set(), set()
            for item in raw_templates:
                if not isinstance(item, dict):
                    raise ValueError("模板内容无效")
                template_id = item.get("id")
                if not isinstance(template_id, str) or not template_id or template_id in ids:
                    raise ValueError("模板标识无效或重复")
                name = valid_name(item.get("name", ""))
                if name.casefold() in names:
                    raise ValueError("模板名称重复")
                includes = item.get("include_od")
                if not isinstance(includes, bool):
                    raise ValueError("模板 OD 保存选项无效")
                recipe = parse_recipe(item.get("recipe"), complete=False)
                recipe = parse_recipe(recipe.as_dict(include_od=includes), complete=False)
                parsed.append(Template(template_id, name, includes, recipe))
                names.add(name.casefold())
                ids.add(template_id)
        except (OSError, UnicodeError, ValueError, TypeError, AttributeError) as error:
            self.ready = False
            raise StorageError(f"模板文件无法读取，原文件已保留。\n{self.path}\n原因：{error}") from error
        self.templates = parsed
        self.ready = True
        return list(self.templates)

    def _write(self, templates: list[Template]) -> None:
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n",
                                             dir=self.directory, prefix="templates_", suffix=".tmp",
                                             delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({"schema_version": 1, "templates": [t.as_dict() for t in templates]},
                          stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except (OSError, ValueError, TypeError) as error:
            raise StorageError(f"模板保存失败，已有模板未改变。\n{self.path}\n原因：{error}") from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def _refresh(self) -> None:
        if not self.ready:
            raise StorageError("模板库尚未成功读取，不能覆盖原文件。请检查模板文件后重新启动程序。")
        # Refresh before editing so changes in another running window are retained.
        if self.path.exists():
            self.load()

    def _commit(self, candidate: list[Template]) -> None:
        self._write(candidate)
        self.templates = candidate

    def get(self, template_id: str) -> Template:
        for template in self.templates:
            if template.id == template_id:
                return template
        raise InputError("该模板已不存在，请重新选择模板。")

    def _check_unique(self, name: str, except_id: str | None = None) -> str:
        name = valid_name(name)
        if any(t.name.casefold() == name.casefold() and t.id != except_id for t in self.templates):
            raise InputError(f"模板名称“{name}”已存在。请换一个名称，或使用“更新当前模板”。")
        return name

    def create(self, name: str, recipe: Recipe, include_od: bool = False) -> Template:
        self._refresh()
        name = self._check_unique(name)
        recipe = parse_recipe(recipe.as_dict(), complete=False)
        recipe = parse_recipe(recipe.as_dict(include_od=include_od), complete=False)
        template = Template(str(uuid.uuid4()), name, include_od, recipe)
        self._commit(self.templates + [template])
        return template

    def update(self, template_id: str, name: str, recipe: Recipe, include_od: bool) -> Template:
        self._refresh()
        self.get(template_id)
        name = self._check_unique(name, template_id)
        recipe = parse_recipe(recipe.as_dict(), complete=False)
        recipe = parse_recipe(recipe.as_dict(include_od=include_od), complete=False)
        template = Template(template_id, name, include_od, recipe)
        self._commit([template if t.id == template_id else t for t in self.templates])
        return template

    def rename(self, template_id: str, name: str) -> Template:
        self._refresh()
        original = self.get(template_id)
        return self.update(template_id, name, original.recipe, original.include_od)

    def delete(self, template_id: str) -> None:
        self._refresh()
        self.get(template_id)
        self._commit([t for t in self.templates if t.id != template_id])
