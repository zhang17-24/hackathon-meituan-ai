"""SKILL.md 文件扫描与 YAML frontmatter 解析。"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from .models import Skill

logger = logging.getLogger(__name__)

_BUILTIN_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills_builtin"
_CUSTOM_SKILLS_DIR = Path("data/skills")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


class SkillLoader:
    """扫描 skills/ 目录，解析 SKILL.md 文件。"""

    def __init__(self, builtin_dir: Path | None = None, custom_dir: Path | None = None):
        self._builtin_dir = builtin_dir or _BUILTIN_SKILLS_DIR
        self._custom_dir = custom_dir or _CUSTOM_SKILLS_DIR

    def load_all(self) -> list[Skill]:
        """加载所有技能，自定义目录覆盖内置同名技能。"""
        skills: dict[str, Skill] = {}

        for skill in self._scan_dir(self._builtin_dir, source="builtin"):
            skills[skill.name] = skill

        for skill in self._scan_dir(self._custom_dir, source="custom"):
            skills[skill.name] = skill

        return list(skills.values())

    def load_by_group(self, group: str) -> list[Skill]:
        """按权限组加载技能。"""
        return [s for s in self.load_all() if s.group == group]

    def _scan_dir(self, directory: Path, source: str) -> list[Skill]:
        if not directory.exists():
            return []
        results: list[Skill] = []
        for md_file in sorted(directory.rglob("*.skill.md")):
            skill = self._parse_file(md_file, source)
            if skill:
                results.append(skill)
        return results

    def _parse_file(self, file_path: Path, source: str) -> Skill | None:
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to read skill file %s: %s", file_path, e)
            return None

        match = _FRONTMATTER_RE.match(text)
        if not match:
            logger.warning("Skill file %s missing valid YAML frontmatter", file_path)
            return None

        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as e:
            logger.warning("Skill file %s YAML parse error: %s", file_path, e)
            return None

        name = meta.get("name")
        if not name:
            logger.warning("Skill file %s missing required 'name' field", file_path)
            return None

        return Skill(
            name=name,
            description=meta.get("description", ""),
            group=meta.get("group", "nail_ops"),
            version=str(meta.get("version", "v1")),
            tools=meta.get("tools", []),
            body=match.group(2).strip(),
            file_path=str(file_path),
            source=source,
        )
