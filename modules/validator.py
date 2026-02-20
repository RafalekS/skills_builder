"""
Validator - SKILL.md frontmatter validation (pure logic, no Qt)
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

VALID_NAME_RE  = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$')
CONSEC_HYPH_RE = re.compile(r'--')
RESERVED_WORDS = {"anthropic", "claude"}

KNOWN_TOOLS = {
    "Read", "Write", "Edit", "MultiEdit",
    "Grep", "Glob", "Bash",
    "WebFetch", "WebSearch",
    "Task", "TodoWrite", "NotebookEdit",
    "AskUserQuestion", "Skill",
}

TRIGGER_HINTS = ("use when", "when user", "when working", "for ", "use for", "triggered")


@dataclass
class ValidationResult:
    valid: bool = True
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        if not other.valid:
            self.valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        return self


class SkillValidator:

    # ── Name ─────────────────────────────────────────────────────────────────

    def validate_name(self, name: str) -> ValidationResult:
        r = ValidationResult()
        if not name:
            r.add_error("Name is required.")
            return r
        if len(name) > 64:
            r.add_error(f"Name too long: {len(name)} chars (max 64).")
        if not VALID_NAME_RE.match(name):
            r.add_error("Name must contain only lowercase letters, digits, and hyphens, "
                        "and must not start or end with a hyphen.")
        if CONSEC_HYPH_RE.search(name):
            r.add_error("Name must not contain consecutive hyphens (--).")
        for word in RESERVED_WORDS:
            if word in name:
                r.add_error(f"Name must not contain reserved word '{word}'.")
        return r

    # ── Description ──────────────────────────────────────────────────────────

    def validate_description(self, description: str) -> ValidationResult:
        r = ValidationResult()
        if not description or not description.strip():
            r.add_error("Description is required.")
            return r
        desc = description.strip()
        if len(desc) > 1024:
            r.add_error(f"Description too long: {len(desc)} chars (max 1024).")
        if len(desc) < 20:
            r.add_warning("Description is very short — be specific about what the skill does and when to use it.")
        elif len(desc) < 50:
            r.add_warning("Description is short. Consider adding trigger keywords like 'Use when...'")
        lower = desc.lower()
        if not any(hint in lower for hint in TRIGGER_HINTS):
            r.add_warning("Consider adding when Claude should use this skill (e.g. 'Use when the user asks about...').")
        return r

    # ── allowed-tools ────────────────────────────────────────────────────────

    def validate_allowed_tools(self, tools_str: str) -> ValidationResult:
        r = ValidationResult()
        if not tools_str or not tools_str.strip():
            return r  # optional field
        tools = tools_str.strip().split()
        for tool in tools:
            if tool in KNOWN_TOOLS:
                continue
            if re.match(r'^Bash\(.+\)$', tool):
                continue
            if re.match(r'^mcp__', tool):
                continue
            r.add_warning(f"Unknown tool '{tool}'. Known tools: {', '.join(sorted(KNOWN_TOOLS))}.")
        return r

    # ── Full frontmatter dict ────────────────────────────────────────────────

    def validate_frontmatter(self, data: dict) -> ValidationResult:
        r = ValidationResult()
        r.merge(self.validate_name(data.get("name", "")))
        r.merge(self.validate_description(data.get("description", "")))
        tools = data.get("allowed-tools", "")
        if tools:
            r.merge(self.validate_allowed_tools(str(tools)))
        compat = data.get("compatibility", "")
        if compat and len(str(compat)) > 500:
            r.add_error(f"'compatibility' too long: {len(str(compat))} chars (max 500).")
        return r

    # ── Body ─────────────────────────────────────────────────────────────────

    def validate_body(self, body: str) -> ValidationResult:
        r = ValidationResult()
        if not body or not body.strip():
            r.add_warning("Skill body is empty — add instructions so Claude knows what to do.")
            return r
        lines = body.splitlines()
        if len(lines) > 500:
            r.add_warning(f"Body is {len(lines)} lines. Consider splitting into reference files "
                          "(keep SKILL.md under 500 lines).")
        estimated_tokens = len(body) // 4
        if estimated_tokens > 5000:
            r.add_warning(f"Body is ~{estimated_tokens} tokens (estimated). Aim for under 5,000 tokens.")
        return r

    # ── Parse frontmatter from raw SKILL.md content ──────────────────────────

    def parse_frontmatter(self, content: str) -> Optional[dict]:
        """
        Extract and parse YAML frontmatter from SKILL.md content.
        Returns parsed dict, or None if not found / invalid.
        """
        content = content.strip()
        if not content.startswith("---"):
            return None
        end = content.find("\n---", 3)
        if end == -1:
            return None
        fm_text = content[3:end].strip()
        try:
            result = yaml.safe_load(fm_text)
            return result if isinstance(result, dict) else {}
        except yaml.YAMLError as e:
            logger.debug("YAML parse error in frontmatter: %s", e)
            return None

    def extract_body(self, content: str) -> str:
        """Return the markdown body after the closing --- of frontmatter."""
        content_stripped = content.strip()
        if not content_stripped.startswith("---"):
            return content
        end = content_stripped.find("\n---", 3)
        if end == -1:
            return ""
        after = content_stripped[end + 4:]
        return after.lstrip("\n")
