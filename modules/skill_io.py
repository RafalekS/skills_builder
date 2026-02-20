"""
Skill IO - File I/O for reading, writing, listing, exporting, importing skills
"""

import logging
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from modules.validator import SkillValidator

logger = logging.getLogger(__name__)
_validator = SkillValidator()


class SkillIO:

    # ── List ──────────────────────────────────────────────────────────────────

    def list_skills(self, skills_dir: Path) -> list[dict]:
        """
        Scan a skills directory and return a list of skill metadata dicts.
        Each dict: name, path, description, has_scripts, has_references,
                   has_assets, extra_files, modified
        """
        if not skills_dir or not skills_dir.exists():
            return []

        skills = []
        for entry in sorted(skills_dir.iterdir()):
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                content = skill_md.read_text(encoding="utf-8")
                fm = _validator.parse_frontmatter(content) or {}
                description = fm.get("description", "")
                modified = datetime.fromtimestamp(skill_md.stat().st_mtime)
                extra = [
                    f.name for f in entry.rglob("*")
                    if f.is_file() and f.name != "SKILL.md"
                ]
                skills.append({
                    "name":           entry.name,
                    "path":           entry,
                    "description":    description,
                    "has_scripts":    (entry / "scripts").is_dir(),
                    "has_references": (entry / "references").is_dir(),
                    "has_assets":     (entry / "assets").is_dir(),
                    "extra_files":    extra,
                    "modified":       modified,
                    "frontmatter":    fm,
                })
            except Exception:
                logger.exception("Error reading skill at %s", entry)

        return skills

    # ── Read ──────────────────────────────────────────────────────────────────

    def read_skill(self, skill_dir: Path) -> dict:
        """
        Read a skill directory.
        Returns: frontmatter (dict), body (str), full_content (str), files (list[str])
        """
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")

        full_content = skill_md.read_text(encoding="utf-8")
        fm = _validator.parse_frontmatter(full_content) or {}
        body = _validator.extract_body(full_content)
        files = [
            str(f.relative_to(skill_dir))
            for f in skill_dir.rglob("*")
            if f.is_file() and f.name != "SKILL.md"
        ]
        return {
            "frontmatter":  fm,
            "body":         body,
            "full_content": full_content,
            "files":        sorted(files),
        }

    # ── Write ─────────────────────────────────────────────────────────────────

    def write_skill(self, skills_dir: Path, name: str, content: str) -> Path:
        """
        Write SKILL.md to skills_dir/name/SKILL.md.
        Creates directory if needed. Returns the skill directory path.
        """
        skill_dir = skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(content, encoding="utf-8")
        logger.info("Wrote skill '%s' to %s", name, skill_md)
        return skill_dir

    def update_skill(self, skill_dir: Path, content: str) -> Path:
        """Overwrite an existing skill's SKILL.md."""
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(content, encoding="utf-8")
        logger.info("Updated skill at %s", skill_md)
        return skill_dir

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_skill(self, skill_dir: Path) -> bool:
        """Delete the entire skill directory."""
        try:
            shutil.rmtree(skill_dir)
            logger.info("Deleted skill at %s", skill_dir)
            return True
        except Exception:
            logger.exception("Failed to delete skill at %s", skill_dir)
            return False

    # ── Backup ───────────────────────────────────────────────────────────────

    def backup_skill(self, skill_dir: Path, backup_dir: Path) -> Path:
        """
        Copy SKILL.md to backup_dir/skill-name-YYYYMMDD-HHMMSS.md
        Returns path to backup file.
        """
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = backup_dir / f"{skill_dir.name}-{timestamp}.md"
        skill_md = skill_dir / "SKILL.md"
        shutil.copy2(skill_md, dest)
        logger.info("Backed up skill to %s", dest)
        return dest

    # ── Export ZIP ────────────────────────────────────────────────────────────

    def export_zip(self, skill_dirs: list[Path], zip_path: Path) -> bool:
        """
        Export one or more skill directories into a ZIP file.
        ZIP structure: skill-name/SKILL.md (+ all bundled files)
        """
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for skill_dir in skill_dirs:
                    for file_path in skill_dir.rglob("*"):
                        if file_path.is_file():
                            arcname = file_path.relative_to(skill_dir.parent)
                            zf.write(file_path, arcname)
            logger.info("Exported %d skill(s) to %s", len(skill_dirs), zip_path)
            return True
        except Exception:
            logger.exception("Failed to export ZIP to %s", zip_path)
            return False

    # ── Import ZIP ────────────────────────────────────────────────────────────

    def import_zip(self, zip_path: Path, target_dir: Path,
                   overwrite: bool = False) -> list[str]:
        """
        Import skills from a ZIP file.
        Returns list of imported skill names.
        """
        imported = []
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                # Detect skill roots: directories containing SKILL.md
                skill_roots = set()
                for name in names:
                    parts = Path(name).parts
                    if len(parts) == 2 and parts[1] == "SKILL.md":
                        skill_roots.add(parts[0])

                for root in skill_roots:
                    dest = target_dir / root
                    if dest.exists() and not overwrite:
                        logger.warning("Skill '%s' already exists, skipping", root)
                        continue
                    dest.mkdir(parents=True, exist_ok=True)
                    for name in names:
                        if name.startswith(root + "/"):
                            zf.extract(name, target_dir)
                    imported.append(root)

            logger.info("Imported %d skill(s) from %s", len(imported), zip_path)
        except Exception:
            logger.exception("Failed to import ZIP from %s", zip_path)

        return imported

    # ── Import from directory ─────────────────────────────────────────────────

    def import_from_dir(self, source_dir: Path, target_dir: Path,
                        overwrite: bool = False) -> bool:
        """Copy a skill directory into target_dir."""
        dest = target_dir / source_dir.name
        if dest.exists() and not overwrite:
            logger.warning("Skill '%s' already exists at target, skipping", source_dir.name)
            return False
        try:
            shutil.copytree(source_dir, dest, dirs_exist_ok=True)
            logger.info("Imported skill '%s' to %s", source_dir.name, dest)
            return True
        except Exception:
            logger.exception("Failed to import from %s", source_dir)
            return False
