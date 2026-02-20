"""
Editor Tab - SKILL.md creator and editor
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QLineEdit, QTextEdit,
    QScrollArea, QFormLayout, QGridLayout,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QDialogButtonBox, QComboBox, QMessageBox,
    QListWidget, QListWidgetItem, QFileDialog, QFrame,
    QAbstractItemView, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCursor

from modules.validator import SkillValidator, ValidationResult
from modules.skill_io import SkillIO
from modules.syntax_highlighter import SkillHighlighter
from modules.theme import (
    BG_DARK, BG_MEDIUM, BG_LIGHT,
    FG_PRIMARY, FG_SECONDARY, FG_DIM,
    ACCENT, ACCENT_GREEN, ERROR_RED, WARN_ORANGE,
)

logger = logging.getLogger(__name__)

ALLOWED_TOOLS = [
    "Read", "Write", "Edit", "MultiEdit",
    "Grep", "Glob", "Bash",
    "WebFetch", "WebSearch",
    "Task", "TodoWrite", "NotebookEdit",
    "AskUserQuestion", "Skill",
]

# ── Built-in templates ────────────────────────────────────────────────────────

TEMPLATES: dict[str, str] = {
    "blank": """\
---
name: my-skill
description: Describe what this skill does and when Claude should use it.
---

""",

    "minimal": """\
---
name: my-skill
description: Describe what this skill does and when Claude should use it. Use when the user asks about...
---

# My Skill

## Instructions

Step-by-step guidance for Claude here.

## Examples

Describe example inputs and expected outputs.
""",

    "with-scripts": """\
---
name: my-skill
description: Skill that runs scripts. Use when the user needs...
allowed-tools: Read Bash
---

# My Skill

## Instructions

This skill uses scripts in the `scripts/` directory.

To run the main script:
```
scripts/main.py
```

## Usage

Describe what the script does and when to run it.
""",

    "with-references": """\
---
name: my-skill
description: Skill with detailed reference material. Use when the user needs...
allowed-tools: Read
---

# My Skill

## Quick Reference

See [detailed reference](references/REFERENCE.md) for complete documentation.

## Instructions

Brief instructions here. For edge cases, consult the reference.
""",

    "code-review": """\
---
name: code-review
description: Perform thorough code reviews. Use when the user asks to review code, check a PR, audit a file, or assess code quality.
allowed-tools: Read Glob Grep Bash
---

# Code Review

## Review Checklist

1. **Correctness** — Does the code do what it claims?
2. **Security** — SQL injection, XSS, path traversal, secrets in code?
3. **Error handling** — Are errors caught and logged, not silenced?
4. **Performance** — Any obvious bottlenecks?
5. **Readability** — Is the intent clear?
6. **Tests** — Are there tests? Do they cover edge cases?

## Output Format

For each issue found:
- **File:Line** — description
- **Severity:** Critical / High / Medium / Low
- **Suggestion:** specific fix

End with a summary table of issue counts by severity.
""",

    "git-workflow": """\
---
name: git-workflow
description: Git operations for commits, branches, and PRs. Use when the user asks to commit, create a branch, open a PR, or manage git history.
allowed-tools: Bash(git:*) Read
---

# Git Workflow

## Commit

1. Run `git status` to see changes
2. Stage relevant files with `git add <files>` (never `git add -A` blindly)
3. Write a commit message: imperative mood, under 72 chars, explain *why* not *what*
4. Commit: `git commit -m "message"`

## Pull Request

1. Ensure branch is up to date: `git fetch && git rebase origin/main`
2. Push: `git push -u origin <branch>`
3. Create PR with clear title and description

## Safety Rules

- NEVER force push to main/master
- NEVER amend published commits
- NEVER skip pre-commit hooks
""",

    "documentation": """\
---
name: documentation
description: Generate and update documentation. Use when the user asks to document code, write a README, generate API docs, or explain a codebase.
allowed-tools: Read Glob Grep Write
---

# Documentation Generator

## README Structure

1. Project name and one-line description
2. Quick start (installation + first run)
3. Usage examples
4. Configuration reference
5. Contributing guide

## Code Documentation

- Docstrings: describe *what*, *args*, *returns*, *raises*
- Inline comments: explain *why*, not *what*
- Keep docs close to code (same file > separate wiki)

## Style

- Active voice: "Returns the user ID" not "The user ID is returned"
- Concrete examples over abstract descriptions
- Update docs in the same PR as the code change
""",

    "testing": """\
---
name: testing
description: Write and run tests using TDD. Use when the user asks to write tests, fix failing tests, add test coverage, or practice TDD.
allowed-tools: Read Write Bash
---

# Testing Skill

## TDD Cycle

1. Write a failing test (Red)
2. Write minimum code to pass (Green)
3. Refactor (Refactor)
4. Repeat

## Test Structure

```python
def test_<what>_<when>_<expected>():
    # Arrange
    ...
    # Act
    result = ...
    # Assert
    assert result == expected
```

## Rules

- Test one thing per test
- Tests must be independent (no shared state)
- Test edge cases: empty, None, max values, errors
- Name tests so failures are self-explanatory
""",

    "data-analysis": """\
---
name: data-analysis
description: Analyse data files (CSV, JSON, Excel). Use when the user asks to analyse data, summarise a dataset, find patterns, or generate statistics.
allowed-tools: Read Bash
---

# Data Analysis

## Steps

1. Load and inspect the data (shape, dtypes, sample rows)
2. Check for nulls and duplicates
3. Compute summary statistics
4. Identify distributions and outliers
5. Answer the user's specific question with evidence

## Output Format

- Lead with the key finding
- Support with numbers (not just "most" — say "73%")
- Suggest follow-up analyses if relevant
""",

    "security-audit": """\
---
name: security-audit
description: Security review of code. Use when the user asks for a security audit, vulnerability scan, or OWASP review.
allowed-tools: Read Glob Grep Bash
---

# Security Audit

## OWASP Top 10 Checklist

1. Broken Access Control — check authorisation on every endpoint
2. Cryptographic Failures — secrets in code? Weak hashing?
3. Injection — SQL, command, LDAP injection possible?
4. Insecure Design — threat model missing?
5. Security Misconfiguration — debug mode in prod? Default creds?
6. Vulnerable Components — outdated dependencies?
7. Auth Failures — brute force protection? Session management?
8. Data Integrity Failures — unsigned packages? Unsafe deserialisation?
9. Logging Failures — security events logged? No sensitive data in logs?
10. SSRF — untrusted URLs fetched server-side?

## Output

Report issues by severity: Critical > High > Medium > Low > Info
""",

    "devops": """\
---
name: devops
description: CI/CD, Docker, and cloud deployment. Use when the user needs to set up pipelines, write Dockerfiles, deploy to cloud, or manage infrastructure.
allowed-tools: Read Write Bash
---

# DevOps Skill

## Docker

- Use multi-stage builds to minimise image size
- Pin base image versions (`python:3.11-slim`, not `python:latest`)
- Run as non-root user
- Use `.dockerignore`

## CI/CD

- Lint → Test → Build → Push → Deploy (in order)
- Fail fast on lint errors
- Cache dependencies between runs
- Secrets via environment variables, never in code

## Cloud Deployment

- Infrastructure as Code (Terraform/Pulumi) for reproducibility
- Blue/green or canary deployments for zero downtime
- Monitor: CPU, memory, error rate, latency
""",

    "frontend-design": """\
---
name: frontend-design
description: UI/UX frontend design with strong aesthetic decisions. Use when the user asks to build a UI, design a component, or create a web interface.
allowed-tools: Read Write
---

# Frontend Design

## Design Principles

- **Hierarchy**: Size, weight, and contrast guide the eye
- **Whitespace**: Don't fill every pixel — breathing room matters
- **Consistency**: Same patterns for same actions, always
- **Feedback**: Every action needs a response (loading, success, error)

## Anti-patterns to Avoid

- Generic "AI slop" aesthetics (grey cards, blue buttons, thin fonts)
- Centred everything — use alignment grids
- Too many font sizes — 3 max
- Animations that don't serve a purpose

## Component Checklist

- [ ] Works at mobile and desktop widths
- [ ] Keyboard navigable
- [ ] Error and empty states designed
- [ ] Loading state designed
""",

    "database": """\
---
name: database
description: Database queries and schema work. Use when the user needs SQL queries, schema design, migrations, or database optimisation.
allowed-tools: Read Bash
---

# Database Skill

## Query Rules

- Always use parameterised queries (never string formatting for user input)
- Explain queries before optimising (`EXPLAIN ANALYSE`)
- Add indexes on columns used in WHERE, JOIN, ORDER BY
- Avoid SELECT * in production queries

## Schema Design

- Use explicit column types (not TEXT for everything)
- Normalise to 3NF unless read performance demands otherwise
- Foreign key constraints everywhere
- Timestamps: `created_at`, `updated_at` on all tables

## Safety

- Test migrations on a copy before production
- Always have a rollback script
- No destructive operations in the same transaction as application logic
""",

    "api-integration": """\
---
name: api-integration
description: Third-party API integration. Use when the user needs to connect to an external API, handle authentication, or process API responses.
allowed-tools: Read Write Bash WebFetch
---

# API Integration

## Steps

1. Read the API documentation first
2. Identify authentication method (OAuth2, API key, JWT)
3. Start with the simplest endpoint to verify auth works
4. Handle rate limits (respect `Retry-After`, exponential backoff)
5. Handle errors explicitly (don't assume 200)

## Error Handling

```python
response = requests.get(url, headers=headers, timeout=10)
response.raise_for_status()  # raises on 4xx/5xx
```

## Secrets

- API keys in environment variables, never in code
- Use `.env` files locally, secrets manager in production
""",
}


# ── Styles ────────────────────────────────────────────────────────────────────

BTN_STYLE = f"""
    QPushButton {{
        background-color: {BG_LIGHT};
        color: {FG_PRIMARY};
        border: 1px solid #3a3a3d;
        padding: 5px 12px;
        border-radius: 3px;
    }}
    QPushButton:hover {{ background-color: #3a3a3d; }}
    QPushButton:pressed {{ background-color: {ACCENT}; color: #ffffff; }}
    QPushButton:disabled {{ color: {FG_DIM}; }}
"""

EDITOR_STYLE = f"""
    QTextEdit {{
        font-family: Consolas, 'Courier New', monospace;
        background-color: {BG_DARK};
        color: {FG_PRIMARY};
        border: none;
        padding: 8px;
        selection-background-color: {ACCENT};
    }}
"""

INPUT_STYLE = f"""
    QLineEdit, QTextEdit {{
        background-color: {BG_MEDIUM};
        color: {FG_PRIMARY};
        border: 1px solid #3a3a3d;
        border-radius: 3px;
        padding: 4px 6px;
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border-color: {ACCENT};
    }}
"""

FORM_LABEL_STYLE  = f"color: {FG_SECONDARY}; font-size: 12px;"
SECTION_STYLE     = f"color: {FG_PRIMARY}; font-size: 12px; font-weight: bold; margin-top: 6px;"
CHAR_COUNTER_STYLE = f"color: {FG_DIM}; font-size: 11px;"


# ─────────────────────────────────────────────────────────────────────────────
# Editor Tab
# ─────────────────────────────────────────────────────────────────────────────

class EditorTab(QWidget):

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.validator = SkillValidator()
        self.skill_io  = SkillIO()

        self.current_skill_dir: Path | None = None
        self.is_modified = False
        self._syncing    = False

        # Debounce timer: raw editor → form sync
        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(600)
        self._sync_timer.timeout.connect(self._raw_to_form)

        self._build_ui()
        self._new_skill()   # start with a blank skill

    # ── Build UI ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BG_LIGHT}; }}")

        splitter.addWidget(self._build_form_panel())
        splitter.addWidget(self._build_raw_panel())
        splitter.setSizes([380, 720])
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, False)
        self._splitter = splitter

        layout.addWidget(splitter, 1)
        layout.addWidget(self._build_bottom_bar())

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"background: {BG_MEDIUM}; border-bottom: 1px solid {BG_LIGHT};")
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(4)

        def btn(label, tip, slot):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setStyleSheet(BTN_STYLE)
            b.clicked.connect(slot)
            return b

        row.addWidget(btn("New",            "New skill (Ctrl+N)",           self._new_skill))
        row.addWidget(btn("Open...",        "Open existing skill",          self._open_skill))
        row.addWidget(btn("Save",           "Save skill (Ctrl+S)",          self._save))
        row.addWidget(btn("Save As...",     "Save to new location",         self._save_as))
        row.addWidget(btn("Backup & Save",  "Backup then save",             self._backup_and_save))
        row.addWidget(self._vsep())
        row.addWidget(btn("Templates...",   "Pick a starting template",     self._open_templates))
        row.addWidget(self._vsep())
        row.addWidget(btn("Validate",       "Validate frontmatter",         self._run_validation))

        row.addStretch()

        self._form_toggle_btn = QPushButton("Hide Form")
        self._form_toggle_btn.setToolTip("Show/hide the frontmatter form panel")
        self._form_toggle_btn.setStyleSheet(BTN_STYLE)
        self._form_toggle_btn.setCheckable(True)
        self._form_toggle_btn.toggled.connect(self._toggle_form)
        row.addWidget(self._form_toggle_btn)

        return bar

    # ── Form panel ────────────────────────────────────────────────────────────

    def _build_form_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_MEDIUM}; }}")

        inner = QWidget()
        inner.setStyleSheet(f"background: {BG_MEDIUM};")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # ── name ──
        layout.addWidget(self._section_label("Frontmatter"))

        name_row = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("my-skill")
        self.name_edit.setStyleSheet(INPUT_STYLE)
        self.name_edit.textChanged.connect(self._on_name_changed)
        self.name_counter = QLabel("0/64")
        self.name_counter.setStyleSheet(CHAR_COUNTER_STYLE)
        name_row.addWidget(self.name_edit)
        name_row.addWidget(self.name_counter)
        layout.addWidget(QLabel("Name *", styleSheet=FORM_LABEL_STYLE))
        layout.addLayout(name_row)

        # ── description ──
        layout.addWidget(QLabel("Description *", styleSheet=FORM_LABEL_STYLE))
        desc_row = QHBoxLayout()
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText(
            "What this skill does and when Claude should use it.\n"
            "Tip: include 'Use when...' to help Claude trigger it correctly."
        )
        self.desc_edit.setStyleSheet(INPUT_STYLE)
        self.desc_edit.setMaximumHeight(90)
        self.desc_edit.textChanged.connect(self._on_desc_changed)
        layout.addWidget(self.desc_edit)
        self.desc_counter = QLabel("0/1024")
        self.desc_counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.desc_counter.setStyleSheet(CHAR_COUNTER_STYLE)
        layout.addWidget(self.desc_counter)

        # ── license ──
        layout.addWidget(QLabel("License", styleSheet=FORM_LABEL_STYLE))
        self.license_edit = QLineEdit()
        self.license_edit.setPlaceholderText("MIT / Apache-2.0 / Proprietary")
        self.license_edit.setStyleSheet(INPUT_STYLE)
        self.license_edit.textChanged.connect(self._schedule_form_to_raw)
        layout.addWidget(self.license_edit)

        # ── compatibility ──
        layout.addWidget(QLabel("Compatibility", styleSheet=FORM_LABEL_STYLE))
        self.compat_edit = QLineEdit()
        self.compat_edit.setPlaceholderText("Designed for Claude Code (optional)")
        self.compat_edit.setStyleSheet(INPUT_STYLE)
        self.compat_edit.textChanged.connect(self._schedule_form_to_raw)
        layout.addWidget(self.compat_edit)

        # ── allowed-tools ──
        layout.addWidget(self._section_label("allowed-tools"))
        tools_widget = QWidget()
        tools_widget.setStyleSheet(f"background: {BG_DARK}; border-radius: 3px; padding: 4px;")
        tools_grid = QGridLayout(tools_widget)
        tools_grid.setSpacing(2)
        tools_grid.setContentsMargins(4, 4, 4, 4)
        self.tool_checkboxes: dict[str, QCheckBox] = {}
        for i, tool in enumerate(ALLOWED_TOOLS):
            cb = QCheckBox(tool)
            cb.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 12px;")
            if tool in ("Read", "Grep", "Glob"):
                cb.setChecked(True)
            cb.stateChanged.connect(self._schedule_form_to_raw)
            self.tool_checkboxes[tool] = cb
            tools_grid.addWidget(cb, i // 3, i % 3)
        layout.addWidget(tools_widget)

        # ── metadata ──
        layout.addWidget(self._section_label("metadata (key: value pairs)"))
        self.meta_table = QTableWidget(0, 2)
        self.meta_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.meta_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.meta_table.verticalHeader().hide()
        self.meta_table.setMaximumHeight(110)
        self.meta_table.setStyleSheet(f"""
            QTableWidget {{
                background: {BG_DARK}; color: {FG_PRIMARY};
                border: 1px solid {BG_LIGHT}; font-size: 12px;
            }}
            QHeaderView::section {{
                background: {BG_MEDIUM}; color: {FG_SECONDARY};
                padding: 3px; border: 1px solid {BG_LIGHT};
            }}
        """)
        self.meta_table.itemChanged.connect(self._schedule_form_to_raw)
        layout.addWidget(self.meta_table)

        meta_btn_row = QHBoxLayout()
        add_meta = QPushButton("+ Add row")
        add_meta.setStyleSheet(BTN_STYLE)
        add_meta.clicked.connect(self._add_meta_row)
        del_meta = QPushButton("- Remove row")
        del_meta.setStyleSheet(BTN_STYLE)
        del_meta.clicked.connect(self._del_meta_row)
        meta_btn_row.addWidget(add_meta)
        meta_btn_row.addWidget(del_meta)
        meta_btn_row.addStretch()
        layout.addLayout(meta_btn_row)

        # ── validation panel ──
        layout.addWidget(self._section_label("Validation"))
        self.validation_label = QLabel("—")
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet(
            f"color: {FG_SECONDARY}; font-size: 12px; "
            f"background: {BG_DARK}; padding: 6px; border-radius: 3px;"
        )
        layout.addWidget(self.validation_label)

        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    # ── Raw editor panel ──────────────────────────────────────────────────────

    def _build_raw_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {BG_DARK};")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header row
        header = QWidget()
        header.setStyleSheet(f"background: {BG_MEDIUM}; border-bottom: 1px solid {BG_LIGHT};")
        hrow = QHBoxLayout(header)
        hrow.setContentsMargins(8, 3, 8, 3)
        self._raw_title = QLabel("SKILL.md")
        self._raw_title.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 12px;")
        hrow.addWidget(self._raw_title)
        hrow.addStretch()

        wrap_cb = QCheckBox("Wrap")
        wrap_cb.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 11px;")
        wrap_cb.setChecked(self.config.get("editor.wrap_lines", True))
        wrap_cb.stateChanged.connect(self._on_wrap_changed)
        hrow.addWidget(wrap_cb)
        self._wrap_cb = wrap_cb

        layout.addWidget(header)

        # Editor
        self.raw_editor = QTextEdit()
        self.raw_editor.setStyleSheet(EDITOR_STYLE)
        font = QFont(
            self.config.get("editor.font_family", "Consolas"),
            self.config.get("editor.font_size", 13)
        )
        self.raw_editor.setFont(font)
        self._apply_wrap(self.config.get("editor.wrap_lines", True))

        self.highlighter = SkillHighlighter(self.raw_editor.document())
        self.raw_editor.textChanged.connect(self._on_raw_changed)
        self.raw_editor.cursorPositionChanged.connect(self._update_cursor_pos)
        layout.addWidget(self.raw_editor, 1)

        return panel

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(24)
        bar.setStyleSheet(f"background: {BG_MEDIUM}; border-top: 1px solid {BG_LIGHT};")
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(12)

        self._cursor_label   = QLabel("Ln 1, Col 1")
        self._file_label     = QLabel("New skill")
        self._modified_label = QLabel("")

        for lbl in (self._cursor_label, self._file_label, self._modified_label):
            lbl.setStyleSheet(f"color: {FG_DIM}; font-size: 11px;")

        row.addWidget(self._cursor_label)
        row.addWidget(self._vsep())
        row.addWidget(self._file_label)
        row.addStretch()
        row.addWidget(self._modified_label)
        return bar

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(SECTION_STYLE)
        return lbl

    @staticmethod
    def _vsep() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {BG_LIGHT};")
        return sep

    def _apply_wrap(self, wrap: bool):
        if wrap:
            self.raw_editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        else:
            self.raw_editor.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

    # ── Sync: form → raw ──────────────────────────────────────────────────────

    def _schedule_form_to_raw(self, *_):
        if not self._syncing:
            self._form_to_raw()

    def _form_to_raw(self):
        if self._syncing:
            return
        self._syncing = True
        try:
            fm = self._build_frontmatter_str()
            body = self.validator.extract_body(self.raw_editor.toPlainText())
            new_content = fm + "\n" + body
            cursor = self.raw_editor.textCursor()
            pos = cursor.position()
            self.raw_editor.blockSignals(True)
            self.raw_editor.setPlainText(new_content)
            self.raw_editor.blockSignals(False)
            # Restore cursor roughly
            cursor = self.raw_editor.textCursor()
            cursor.setPosition(min(pos, len(new_content)))
            self.raw_editor.setTextCursor(cursor)
        finally:
            self._syncing = False
        self._mark_modified()
        self._run_validation()

    def _build_frontmatter_str(self) -> str:
        lines = ["---"]
        name = self.name_edit.text().strip()
        if name:
            lines.append(f"name: {name}")
        desc = self.desc_edit.toPlainText().strip()
        if desc:
            if "\n" in desc:
                lines.append("description: |")
                for line in desc.split("\n"):
                    lines.append(f"  {line}")
            else:
                lines.append(f"description: {desc}")
        lic = self.license_edit.text().strip()
        if lic:
            lines.append(f"license: {lic}")
        compat = self.compat_edit.text().strip()
        if compat:
            lines.append(f"compatibility: {compat}")
        selected_tools = [t for t in ALLOWED_TOOLS if self.tool_checkboxes[t].isChecked()]
        if selected_tools:
            lines.append(f"allowed-tools: {' '.join(selected_tools)}")
        meta = self._get_metadata()
        if meta:
            lines.append("metadata:")
            for k, v in meta.items():
                lines.append(f"  {k}: {v}")
        lines.append("---")
        return "\n".join(lines)

    def _get_metadata(self) -> dict:
        meta = {}
        for row in range(self.meta_table.rowCount()):
            k_item = self.meta_table.item(row, 0)
            v_item = self.meta_table.item(row, 1)
            k = k_item.text().strip() if k_item else ""
            v = v_item.text().strip() if v_item else ""
            if k:
                meta[k] = v
        return meta

    # ── Sync: raw → form ──────────────────────────────────────────────────────

    def _on_raw_changed(self):
        if not self._syncing:
            self._mark_modified()
            self._sync_timer.start()

    def _raw_to_form(self):
        if self._syncing:
            return
        self._syncing = True
        try:
            content = self.raw_editor.toPlainText()
            fm = self.validator.parse_frontmatter(content)
            if fm is not None:
                self._populate_form(fm)
            self._run_validation()
        finally:
            self._syncing = False

    def _populate_form(self, fm: dict):
        self.name_edit.blockSignals(True)
        self.desc_edit.blockSignals(True)
        self.license_edit.blockSignals(True)
        self.compat_edit.blockSignals(True)
        try:
            self.name_edit.setText(str(fm.get("name", "")))
            self.desc_edit.setPlainText(str(fm.get("description", "")))
            self.license_edit.setText(str(fm.get("license", "")))
            self.compat_edit.setText(str(fm.get("compatibility", "")))

            # allowed-tools
            tools_str = str(fm.get("allowed-tools", ""))
            active = set(tools_str.split()) if tools_str else set()
            for tool, cb in self.tool_checkboxes.items():
                cb.blockSignals(True)
                cb.setChecked(tool in active)
                cb.blockSignals(False)

            # metadata
            meta = fm.get("metadata", {}) or {}
            self.meta_table.blockSignals(True)
            self.meta_table.setRowCount(0)
            if isinstance(meta, dict):
                for k, v in meta.items():
                    self._add_meta_row(str(k), str(v))
            self.meta_table.blockSignals(False)
        finally:
            self.name_edit.blockSignals(False)
            self.desc_edit.blockSignals(False)
            self.license_edit.blockSignals(False)
            self.compat_edit.blockSignals(False)

    # ── Validation ────────────────────────────────────────────────────────────

    def _run_validation(self):
        fm = self.validator.parse_frontmatter(self.raw_editor.toPlainText())
        if fm is None:
            self.validation_label.setStyleSheet(
                f"color: {WARN_ORANGE}; font-size: 12px; "
                f"background: {BG_DARK}; padding: 6px; border-radius: 3px;"
            )
            self.validation_label.setText("⚠ No valid frontmatter detected.")
            return

        result = self.validator.validate_frontmatter(fm)
        body = self.validator.extract_body(self.raw_editor.toPlainText())
        result.merge(self.validator.validate_body(body))

        lines = []
        for e in result.errors:
            lines.append(f"✖ {e}")
        for w in result.warnings:
            lines.append(f"⚠ {w}")
        if not lines:
            lines.append("✔ Valid")

        if result.errors:
            colour = ERROR_RED
        elif result.warnings:
            colour = WARN_ORANGE
        else:
            colour = ACCENT_GREEN

        self.validation_label.setStyleSheet(
            f"color: {colour}; font-size: 12px; "
            f"background: {BG_DARK}; padding: 6px; border-radius: 3px;"
        )
        self.validation_label.setText("\n".join(lines))

    # ── Character counters ────────────────────────────────────────────────────

    def _on_name_changed(self, text: str):
        n = len(text)
        self.name_counter.setText(f"{n}/64")
        self.name_counter.setStyleSheet(
            CHAR_COUNTER_STYLE if n <= 64 else f"color: {ERROR_RED}; font-size: 11px;"
        )
        self._schedule_form_to_raw()

    def _on_desc_changed(self):
        text = self.desc_edit.toPlainText()
        n = len(text)
        self.desc_counter.setText(f"{n}/1024")
        self.desc_counter.setStyleSheet(
            CHAR_COUNTER_STYLE if n <= 1024 else f"color: {ERROR_RED}; font-size: 11px;"
        )
        self._schedule_form_to_raw()

    # ── Metadata table ────────────────────────────────────────────────────────

    def _add_meta_row(self, key: str = "", value: str = ""):
        row = self.meta_table.rowCount()
        self.meta_table.insertRow(row)
        self.meta_table.setItem(row, 0, QTableWidgetItem(key))
        self.meta_table.setItem(row, 1, QTableWidgetItem(value))

    def _del_meta_row(self):
        row = self.meta_table.currentRow()
        if row >= 0:
            self.meta_table.removeRow(row)
            self._schedule_form_to_raw()

    # ── Cursor position ───────────────────────────────────────────────────────

    def _update_cursor_pos(self):
        cursor = self.raw_editor.textCursor()
        line = cursor.blockNumber() + 1
        col  = cursor.columnNumber() + 1
        self._cursor_label.setText(f"Ln {line}, Col {col}")

    # ── Modified state ────────────────────────────────────────────────────────

    def _mark_modified(self):
        if not self.is_modified:
            self.is_modified = True
        self._modified_label.setText("● Unsaved")
        self._modified_label.setStyleSheet(f"color: {WARN_ORANGE}; font-size: 11px;")
        self._update_file_label()

    def _mark_clean(self):
        self.is_modified = False
        self._modified_label.setText("")
        self._update_file_label()

    def _update_file_label(self):
        if self.current_skill_dir:
            name = self.current_skill_dir.name
            modified = " ●" if self.is_modified else ""
            self._file_label.setText(f"{name}{modified}")
            self._raw_title.setText(f"SKILL.md — {name}")
        else:
            self._file_label.setText("New skill" + (" ●" if self.is_modified else ""))
            self._raw_title.setText("SKILL.md")

    # ── New / Open ────────────────────────────────────────────────────────────

    def _new_skill(self):
        if not self._confirm_discard():
            return
        self.current_skill_dir = None
        self.is_modified = False
        self._syncing = True
        try:
            self.raw_editor.setPlainText(TEMPLATES["minimal"])
            self._populate_form({"name": "", "description": ""})
        finally:
            self._syncing = False
        self._mark_clean()
        self._run_validation()
        self.raw_editor.setFocus()

    def _open_skill(self):
        if not self._confirm_discard():
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Select skill directory",
            str(self.config.get_user_skills_dir())
        )
        if not folder:
            return
        skill_dir = Path(folder)
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            QMessageBox.warning(self, "Not a skill", f"No SKILL.md found in:\n{skill_dir}")
            return
        self.load_skill(skill_dir)

    def load_skill(self, skill_dir: Path):
        """Public: load a skill directory into the editor (called from Library/Search tabs)."""
        try:
            data = self.skill_io.read_skill(skill_dir)
            self.current_skill_dir = skill_dir
            self._syncing = True
            try:
                self.raw_editor.setPlainText(data["full_content"])
                self._populate_form(data["frontmatter"])
            finally:
                self._syncing = False
            self._mark_clean()
            self._run_validation()
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"Failed to open skill:\n{e}")

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save(self):
        if self.current_skill_dir is None:
            self._save_as()
            return
        self._do_save(self.current_skill_dir)

    def _save_as(self):
        dialog = SaveSkillDialog(self.config, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, target_dir = dialog.get_result()
        skill_dir = target_dir / name

        if skill_dir.exists() and skill_dir != self.current_skill_dir:
            reply = QMessageBox.question(
                self, "Already exists",
                f"Skill '{name}' already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.current_skill_dir = skill_dir
        self._do_save(skill_dir)

    def _backup_and_save(self):
        if self.current_skill_dir is None:
            self._save_as()
            return
        try:
            backup_dir = Path(__file__).parent.parent / "backup"
            dest = self.skill_io.backup_skill(self.current_skill_dir, backup_dir)
            self._do_save(self.current_skill_dir)
            self._notify(f"Backed up to {dest.name}", success=True)
        except Exception as e:
            QMessageBox.critical(self, "Backup Error", f"Backup failed:\n{e}")

    def _do_save(self, skill_dir: Path):
        content = self.raw_editor.toPlainText()
        try:
            self.skill_io.write_skill(skill_dir.parent, skill_dir.name, content)
            self.current_skill_dir = skill_dir
            self._mark_clean()
            self._notify(f"Saved to {skill_dir}", success=True)
            # Tell main window to refresh status bar
            mw = self.window()
            if hasattr(mw, "_refresh_skills_status"):
                mw._refresh_skills_status()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save:\n{e}")

    # ── Templates ────────────────────────────────────────────────────────────

    def _open_templates(self):
        dialog = TemplateDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            tmpl = dialog.get_selected_template()
            if tmpl and not self._confirm_discard():
                return
            if tmpl:
                self._syncing = True
                try:
                    self.raw_editor.setPlainText(tmpl)
                    fm = self.validator.parse_frontmatter(tmpl) or {}
                    self._populate_form(fm)
                finally:
                    self._syncing = False
                self.current_skill_dir = None
                self._mark_modified()
                self._run_validation()

    # ── Wrap / form toggle ────────────────────────────────────────────────────

    def _on_wrap_changed(self, state):
        wrap = bool(state)
        self._apply_wrap(wrap)
        self.config.set("editor.wrap_lines", wrap)

    def _toggle_form(self, hidden: bool):
        panel = self._splitter.widget(0)
        panel.setVisible(not hidden)
        self._form_toggle_btn.setText("Show Form" if hidden else "Hide Form")

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _confirm_discard(self) -> bool:
        if not self.is_modified:
            return True
        reply = QMessageBox.question(
            self, "Unsaved changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        )
        return reply == QMessageBox.StandardButton.Discard

    def _notify(self, message: str, success: bool = True):
        mw = self.window()
        if hasattr(mw, "set_status"):
            mw.set_status(message)

    # ── Public API (called from main_window menu) ─────────────────────────────

    def action_new(self):  self._new_skill()
    def action_save(self): self._save()
    def action_save_as(self): self._save_as()


# ─────────────────────────────────────────────────────────────────────────────
# Save Skill Dialog
# ─────────────────────────────────────────────────────────────────────────────

class SaveSkillDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Save Skill")
        self.setModal(True)
        self.setMinimumWidth(460)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        # Destination
        self.dest_combo = QComboBox()
        self.dest_combo.setStyleSheet(INPUT_STYLE)
        user_dir = self.config.get_user_skills_dir()
        self.dest_combo.addItem(f"User skills  (~/.claude/skills)", user_dir)
        proj_dir = self.config.get_project_skills_dir()
        if proj_dir:
            self.dest_combo.addItem(f"Project skills  ({proj_dir.name})", proj_dir)
        self.dest_combo.addItem("Custom directory...", None)
        self.dest_combo.currentIndexChanged.connect(self._on_dest_changed)
        form.addRow("Save to:", self.dest_combo)

        # Name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("my-skill")
        self.name_edit.setStyleSheet(INPUT_STYLE)
        self.name_edit.textChanged.connect(self._update_preview)
        form.addRow("Skill name:", self.name_edit)
        layout.addLayout(form)

        # Preview path
        self.preview_label = QLabel("")
        self.preview_label.setStyleSheet(f"color: {FG_DIM}; font-size: 11px;")
        self.preview_label.setWordWrap(True)
        layout.addWidget(self.preview_label)

        # Name hint
        hint = QLabel("Name: lowercase letters, digits, hyphens only. Must match directory name.")
        hint.setStyleSheet(f"color: {FG_DIM}; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_preview()

    def _on_dest_changed(self, index):
        data = self.dest_combo.currentData()
        if data is None:
            folder = QFileDialog.getExistingDirectory(self, "Choose skills directory")
            if folder:
                self.dest_combo.setItemData(index, Path(folder))
                self.dest_combo.setItemText(index, f"Custom: {folder}")
            else:
                self.dest_combo.setCurrentIndex(0)
        self._update_preview()

    def _update_preview(self):
        dest = self.dest_combo.currentData()
        name = self.name_edit.text().strip()
        if dest and name:
            self.preview_label.setText(f"→ {dest / name / 'SKILL.md'}")
        else:
            self.preview_label.setText("")

    def _validate_and_accept(self):
        name = self.name_edit.text().strip()
        from modules.validator import SkillValidator
        v = SkillValidator()
        result = v.validate_name(name)
        if not result.valid:
            QMessageBox.warning(self, "Invalid name", "\n".join(result.errors))
            return
        dest = self.dest_combo.currentData()
        if not dest:
            QMessageBox.warning(self, "No destination", "Please select a destination directory.")
            return
        self.accept()

    def get_result(self) -> tuple[str, Path]:
        return self.name_edit.text().strip(), self.dest_combo.currentData()


# ─────────────────────────────────────────────────────────────────────────────
# Template Dialog
# ─────────────────────────────────────────────────────────────────────────────

class TemplateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose a Template")
        self.setModal(True)
        self.setMinimumSize(700, 450)
        self._selected_content: str | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)

        # Left: list
        left = QWidget()
        left.setMaximumWidth(200)
        llayout = QVBoxLayout(left)
        llayout.setContentsMargins(0, 0, 0, 0)
        llayout.addWidget(QLabel("Templates:", styleSheet=SECTION_STYLE))
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background: {BG_MEDIUM}; color: {FG_PRIMARY};
                border: 1px solid {BG_LIGHT}; font-size: 13px;
            }}
            QListWidget::item:selected {{ background: {ACCENT}; color: #fff; }}
            QListWidget::item:hover {{ background: {BG_LIGHT}; }}
        """)
        for name in TEMPLATES:
            self.list_widget.addItem(QListWidgetItem(name))
        self.list_widget.currentRowChanged.connect(self._on_select)
        self.list_widget.setCurrentRow(0)
        llayout.addWidget(self.list_widget)
        layout.addWidget(left)

        # Right: preview
        right = QWidget()
        rlayout = QVBoxLayout(right)
        rlayout.setContentsMargins(0, 0, 0, 0)
        rlayout.addWidget(QLabel("Preview:", styleSheet=SECTION_STYLE))
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet(EDITOR_STYLE)
        font = QFont("Consolas", 12)
        self.preview.setFont(font)
        rlayout.addWidget(self.preview)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Use Template")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        rlayout.addWidget(buttons)
        layout.addWidget(right)

    def _on_select(self, row: int):
        if row < 0:
            return
        name = self.list_widget.item(row).text()
        content = TEMPLATES.get(name, "")
        self._selected_content = content
        self.preview.setPlainText(content)
        # Re-apply highlighter
        SkillHighlighter(self.preview.document())

    def get_selected_template(self) -> str | None:
        return self._selected_content
