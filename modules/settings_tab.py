"""
Settings Tab - Application configuration
Sub-tabs: Paths | GitHub | Editor | Sources | About
"""

import json
import logging
import webbrowser
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QLineEdit, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QCheckBox, QSpinBox, QComboBox,
    QFormLayout, QScrollArea, QDialog, QDialogButtonBox,
    QMessageBox, QFileDialog, QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from modules.theme import (
    BG_DARK, BG_MEDIUM, BG_LIGHT,
    FG_PRIMARY, FG_SECONDARY, FG_DIM,
    ACCENT, ACCENT_GREEN, ERROR_RED, WARN_ORANGE,
)

logger = logging.getLogger(__name__)

# ── Styles ────────────────────────────────────────────────────────────────────

BTN_STYLE = f"""
    QPushButton {{
        background-color: {BG_LIGHT};
        color: {FG_PRIMARY};
        border: 1px solid #3a3a3d;
        padding: 5px 14px;
        border-radius: 3px;
    }}
    QPushButton:hover {{ background-color: #3a3a3d; }}
    QPushButton:pressed {{ background-color: {ACCENT}; color: #ffffff; }}
    QPushButton:disabled {{ color: {FG_DIM}; }}
"""

INPUT_STYLE = f"""
    QLineEdit {{
        background: {BG_MEDIUM}; color: {FG_PRIMARY};
        border: 1px solid #3a3a3d; border-radius: 3px; padding: 4px 8px;
    }}
    QLineEdit:focus {{ border-color: {ACCENT}; }}
"""

SPIN_STYLE = f"""
    QSpinBox {{
        background: {BG_MEDIUM}; color: {FG_PRIMARY};
        border: 1px solid #3a3a3d; border-radius: 3px; padding: 3px 6px;
    }}
    QSpinBox:focus {{ border-color: {ACCENT}; }}
    QSpinBox::up-button, QSpinBox::down-button {{
        background: {BG_LIGHT}; border: none; width: 16px;
    }}
"""

COMBO_STYLE = f"""
    QComboBox {{
        background: {BG_MEDIUM}; color: {FG_PRIMARY};
        border: 1px solid #3a3a3d; border-radius: 3px;
        padding: 4px 24px 4px 6px;
    }}
    QComboBox:focus {{ border-color: {ACCENT}; }}
    QComboBox::drop-down {{
        subcontrol-origin: padding; subcontrol-position: top right;
        width: 20px; border-left: 1px solid #3a3a3d;
    }}
    QComboBox::down-arrow {{
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 6px solid {FG_SECONDARY};
    }}
    QComboBox QAbstractItemView {{
        background: {BG_MEDIUM}; color: {FG_PRIMARY};
        selection-background-color: {ACCENT}; outline: none;
    }}
"""

TABLE_STYLE = f"""
    QTableWidget {{
        background: {BG_DARK}; color: {FG_PRIMARY};
        border: 1px solid {BG_LIGHT};
        gridline-color: {BG_LIGHT};
        selection-background-color: {ACCENT};
        font-size: 12px;
    }}
    QTableWidget::item {{ padding: 3px 6px; }}
    QHeaderView::section {{
        background: {BG_MEDIUM}; color: {FG_SECONDARY};
        padding: 4px 6px; border: 1px solid {BG_LIGHT};
        font-size: 12px;
    }}
"""

SECTION_TITLE_STYLE = f"""
    QLabel {{
        color: {ACCENT};
        font-size: 13px;
        font-weight: bold;
        padding-bottom: 4px;
        border-bottom: 1px solid {BG_LIGHT};
    }}
"""

HINT_STYLE = f"color: {FG_DIM}; font-size: 11px;"


def _scroll_wrap(inner: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidget(inner)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {BG_DARK}; }}")
    return scroll


# ── Background worker for GitHub token test ───────────────────────────────────

class TestTokenWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(self, token: str, timeout: int):
        super().__init__()
        self._token   = token
        self._timeout = timeout

    def run(self):
        try:
            from modules.github_client import GitHubClient
            client = GitHubClient(token=self._token, timeout=self._timeout)
            rl = client.get_rate_limit()
            if rl:
                kind = "Authenticated" if self._token else "Anonymous"
                self.finished.emit(f"✔ {kind}: {rl.remaining}/{rl.limit} requests/hour")
            else:
                self.finished.emit("✖ Could not reach GitHub API — check network or token")
        except Exception as e:
            self.finished.emit(f"✖ Error: {e}")


# ── Source dialog (add / edit a source entry) ─────────────────────────────────

class SourceDialog(QDialog):
    def __init__(self, source: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Source" if source is None else "Edit Source")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._build_ui(source or {})

    def _build_ui(self, src: dict):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self.owner_edit = QLineEdit(src.get("owner", ""))
        self.owner_edit.setStyleSheet(INPUT_STYLE)
        self.owner_edit.setPlaceholderText("e.g. anthropics")
        form.addRow("Owner:", self.owner_edit)

        self.repo_edit = QLineEdit(src.get("repo", ""))
        self.repo_edit.setStyleSheet(INPUT_STYLE)
        self.repo_edit.setPlaceholderText("e.g. skills")
        form.addRow("Repo:", self.repo_edit)

        self.type_combo = QComboBox()
        self.type_combo.setStyleSheet(COMBO_STYLE)
        self.type_combo.addItems(["direct", "awesome"])
        idx = 0 if src.get("type", "direct") == "direct" else 1
        self.type_combo.setCurrentIndex(idx)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Type:", self.type_combo)

        self.prefix_edit = QLineEdit(src.get("skills_prefix") or "")
        self.prefix_edit.setStyleSheet(INPUT_STYLE)
        self.prefix_edit.setPlaceholderText("e.g. skills/ (leave blank for repo root)")
        form.addRow("Skills prefix:", self.prefix_edit)

        self.desc_edit = QLineEdit(src.get("description", ""))
        self.desc_edit.setStyleSheet(INPUT_STYLE)
        form.addRow("Description:", self.desc_edit)

        layout.addLayout(form)

        hint = QLabel(
            "direct — repo contains skill dirs with SKILL.md files directly.\n"
            "awesome — repo README links to external skill repos (parsed automatically)."
        )
        hint.setStyleSheet(HINT_STYLE)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_type_changed(idx)

    def _on_type_changed(self, idx: int):
        # prefix only relevant for direct-type repos
        self.prefix_edit.setEnabled(idx == 0)

    def _validate_and_accept(self):
        owner = self.owner_edit.text().strip()
        repo  = self.repo_edit.text().strip()
        if not owner or not repo:
            QMessageBox.warning(self, "Required", "Owner and repo are required.")
            return
        self.accept()

    def get_source(self) -> dict:
        stype  = "direct" if self.type_combo.currentIndex() == 0 else "awesome"
        prefix = self.prefix_edit.text().strip() or None
        return {
            "owner":        self.owner_edit.text().strip(),
            "repo":         self.repo_edit.text().strip(),
            "type":         stype,
            "skills_prefix": prefix,
            "description":  self.desc_edit.text().strip(),
            "enabled":      True,
        }


# ── Paths tab ─────────────────────────────────────────────────────────────────

class PathsWidget(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._build_ui()
        self._refresh_status()

    def _build_ui(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        # User skills dir
        layout.addWidget(QLabel("User Skills Directory", styleSheet=SECTION_TITLE_STYLE))
        layout.addWidget(QLabel(
            "Where your personal skills live (~/.claude/skills by default).",
            styleSheet=HINT_STYLE,
        ))
        user_row = QHBoxLayout()
        self._user_edit = QLineEdit()
        self._user_edit.setStyleSheet(INPUT_STYLE)
        self._user_edit.setPlaceholderText(str(Path.home() / ".claude" / "skills"))
        self._user_edit.editingFinished.connect(self._save_user_dir)
        user_row.addWidget(self._user_edit, 1)
        for label, tip, slot in [
            ("Browse…", "Choose directory", self._browse_user),
            ("Reset",   "Reset to default (~/.claude/skills)", self._reset_user),
        ]:
            b = QPushButton(label)
            b.setStyleSheet(BTN_STYLE)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            user_row.addWidget(b)
        layout.addLayout(user_row)
        self._user_status = QLabel("")
        self._user_status.setStyleSheet(HINT_STYLE)
        layout.addWidget(self._user_status)

        layout.addWidget(self._hsep())

        # Project skills dir
        layout.addWidget(QLabel("Project Skills Directory", styleSheet=SECTION_TITLE_STYLE))
        layout.addWidget(QLabel(
            "Optional. Set this to the .claude/skills folder in your current project.",
            styleSheet=HINT_STYLE,
        ))
        proj_row = QHBoxLayout()
        self._proj_edit = QLineEdit()
        self._proj_edit.setStyleSheet(INPUT_STYLE)
        self._proj_edit.setPlaceholderText("(not set — project scope disabled)")
        self._proj_edit.editingFinished.connect(self._save_proj_dir)
        proj_row.addWidget(self._proj_edit, 1)
        for label, tip, slot in [
            ("Browse…", "Choose directory",              self._browse_proj),
            ("Clear",   "Remove project skills directory", self._clear_proj),
        ]:
            b = QPushButton(label)
            b.setStyleSheet(BTN_STYLE)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            proj_row.addWidget(b)
        layout.addLayout(proj_row)
        self._proj_status = QLabel("")
        self._proj_status.setStyleSheet(HINT_STYLE)
        layout.addWidget(self._proj_status)

        layout.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scroll_wrap(inner))

    @staticmethod
    def _hsep() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BG_LIGHT};")
        return sep

    def _refresh_status(self):
        raw_user = self.config.get("skills.user_skills_dir", "")
        self._user_edit.setText(raw_user)
        user_dir = self.config.get_user_skills_dir()
        if user_dir.exists():
            count = sum(1 for d in user_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists())
            self._user_status.setText(f"✔ Exists — {count} skills")
            self._user_status.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 11px;")
        else:
            self._user_status.setText(f"⚠ Not found: {user_dir}")
            self._user_status.setStyleSheet(f"color: {WARN_ORANGE}; font-size: 11px;")

        raw_proj = self.config.get("skills.project_skills_dir", "")
        self._proj_edit.setText(raw_proj)
        proj_dir = self.config.get_project_skills_dir()
        if proj_dir:
            if proj_dir.exists():
                count = sum(1 for d in proj_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists())
                self._proj_status.setText(f"✔ Exists — {count} skills")
                self._proj_status.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 11px;")
            else:
                self._proj_status.setText(f"⚠ Not found: {proj_dir}")
                self._proj_status.setStyleSheet(f"color: {WARN_ORANGE}; font-size: 11px;")
        else:
            self._proj_status.setText("(not set)")
            self._proj_status.setStyleSheet(HINT_STYLE)

    def _save_user_dir(self):
        val = self._user_edit.text().strip()
        self.config.set("skills.user_skills_dir", val)
        self.config.save()
        self._refresh_status()
        self._notify_mw()

    def _save_proj_dir(self):
        val = self._proj_edit.text().strip()
        self.config.set("skills.project_skills_dir", val)
        self.config.save()
        self._refresh_status()
        self._notify_mw()

    def _browse_user(self):
        folder = QFileDialog.getExistingDirectory(self, "Select user skills directory")
        if folder:
            self._user_edit.setText(folder)
            self._save_user_dir()

    def _reset_user(self):
        self._user_edit.setText("")
        self._save_user_dir()

    def _browse_proj(self):
        folder = QFileDialog.getExistingDirectory(self, "Select project skills directory")
        if folder:
            self._proj_edit.setText(folder)
            self._save_proj_dir()

    def _clear_proj(self):
        self._proj_edit.setText("")
        self._save_proj_dir()

    def _notify_mw(self):
        mw = self.window()
        if hasattr(mw, "_refresh_skills_status"):
            mw._refresh_skills_status()
        if hasattr(mw, "library_tab"):
            mw.library_tab.refresh()


# ── GitHub tab ────────────────────────────────────────────────────────────────

class GitHubWidget(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config  = config
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        layout.addWidget(QLabel("GitHub API Access", styleSheet=SECTION_TITLE_STYLE))
        layout.addWidget(QLabel(
            "Without a token you get 60 API requests/hour. "
            "With a Personal Access Token (PAT): 5000/hour.",
            styleSheet=HINT_STYLE,
        ))

        # Token row
        token_row = QHBoxLayout()
        self._token_edit = QLineEdit(self.config.get("github.token", ""))
        self._token_edit.setStyleSheet(INPUT_STYLE)
        self._token_edit.setPlaceholderText("ghp_xxxxxxxxxxxxxxxxxxxx")
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_edit.editingFinished.connect(self._save_token)
        token_row.addWidget(self._token_edit, 1)

        self._eye_btn = QPushButton("Show")
        self._eye_btn.setStyleSheet(BTN_STYLE)
        self._eye_btn.setCheckable(True)
        self._eye_btn.setToolTip("Toggle token visibility")
        self._eye_btn.toggled.connect(self._toggle_visibility)
        token_row.addWidget(self._eye_btn)

        test_btn = QPushButton("Test")
        test_btn.setStyleSheet(BTN_STYLE)
        test_btn.setToolTip("Test the token against GitHub API")
        test_btn.clicked.connect(self._test_token)
        token_row.addWidget(test_btn)

        form = QFormLayout()
        form.setSpacing(8)
        form.addRow("Personal Access Token:", token_row)

        self._test_status = QLabel("")
        self._test_status.setStyleSheet(HINT_STYLE)
        form.addRow("", self._test_status)
        layout.addLayout(form)

        layout.addWidget(QLabel(
            "Create a token at github.com → Settings → Developer settings → Personal access tokens.\n"
            "Only public_repo scope is needed for reading public repositories.",
            styleSheet=HINT_STYLE,
        ))

        layout.addWidget(self._hsep())
        layout.addWidget(QLabel("Request Settings", styleSheet=SECTION_TITLE_STYLE))

        form2 = QFormLayout()
        form2.setSpacing(8)

        self._timeout_spin = QSpinBox()
        self._timeout_spin.setStyleSheet(SPIN_STYLE)
        self._timeout_spin.setRange(5, 60)
        self._timeout_spin.setSuffix(" seconds")
        self._timeout_spin.setValue(self.config.get("github.search_timeout", 10))
        self._timeout_spin.valueChanged.connect(
            lambda v: self._save("github.search_timeout", v)
        )
        form2.addRow("Request timeout:", self._timeout_spin)

        self._cache_spin = QSpinBox()
        self._cache_spin.setStyleSheet(SPIN_STYLE)
        self._cache_spin.setRange(0, 168)
        self._cache_spin.setSuffix(" hours")
        self._cache_spin.setValue(self.config.get("github.cache_hours", 24))
        self._cache_spin.valueChanged.connect(
            lambda v: self._save("github.cache_hours", v)
        )
        form2.addRow("Cache duration:", self._cache_spin)
        layout.addLayout(form2)

        clear_btn = QPushButton("Clear GitHub Cache")
        clear_btn.setStyleSheet(BTN_STYLE)
        clear_btn.setToolTip("Delete all cached GitHub API responses")
        clear_btn.clicked.connect(self._clear_cache)
        layout.addWidget(clear_btn)

        layout.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scroll_wrap(inner))

    @staticmethod
    def _hsep() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BG_LIGHT};")
        return sep

    def _toggle_visibility(self, checked: bool):
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self._token_edit.setEchoMode(mode)
        self._eye_btn.setText("Hide" if checked else "Show")

    def _save_token(self):
        self._save("github.token", self._token_edit.text().strip())
        mw = self.window()
        if hasattr(mw, "search_tab"):
            mw.search_tab.refresh_client()

    def _save(self, key: str, value):
        self.config.set(key, value)
        self.config.save()

    def _test_token(self):
        self._save_token()
        self._test_status.setText("Testing…")
        self._test_status.setStyleSheet(HINT_STYLE)
        self._worker = TestTokenWorker(
            self._token_edit.text().strip(),
            self._timeout_spin.value(),
        )
        self._worker.finished.connect(self._on_test_done)
        self._worker.start()

    def _on_test_done(self, text: str):
        ok = text.startswith("✔")
        self._test_status.setText(text)
        self._test_status.setStyleSheet(
            f"color: {ACCENT_GREEN}; font-size: 11px;"
            if ok else
            f"color: {ERROR_RED}; font-size: 11px;"
        )
        mw = self.window()
        if hasattr(mw, "set_api_status"):
            mw.set_api_status(text.split(":")[1].strip() if ok else "API: error")

    def _clear_cache(self):
        mw = self.window()
        if hasattr(mw, "search_tab"):
            mw.search_tab.clear_cache()
        else:
            self._test_status.setText("Cache cleared")


# ── Editor tab ────────────────────────────────────────────────────────────────

class EditorWidget(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._build_ui()

    def _build_ui(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        layout.addWidget(QLabel("Editor Appearance", styleSheet=SECTION_TITLE_STYLE))

        form = QFormLayout()
        form.setSpacing(10)

        MONOSPACE_FONTS = [
            "Consolas", "Courier New", "Lucida Console", "Source Code Pro",
            "Fira Code", "JetBrains Mono", "Cascadia Code", "Inconsolata",
        ]
        self._font_combo = QComboBox()
        self._font_combo.setStyleSheet(COMBO_STYLE)
        self._font_combo.addItems(MONOSPACE_FONTS)
        current_font = self.config.get("editor.font_family", "Consolas")
        if current_font in MONOSPACE_FONTS:
            self._font_combo.setCurrentText(current_font)
        else:
            self._font_combo.addItem(current_font)
            self._font_combo.setCurrentText(current_font)
        self._font_combo.currentTextChanged.connect(self._on_font_changed)
        form.addRow("Font family:", self._font_combo)

        self._size_spin = QSpinBox()
        self._size_spin.setStyleSheet(SPIN_STYLE)
        self._size_spin.setRange(8, 24)
        self._size_spin.setSuffix(" pt")
        self._size_spin.setValue(self.config.get("editor.font_size", 13))
        self._size_spin.valueChanged.connect(self._on_size_changed)
        form.addRow("Font size:", self._size_spin)

        self._tab_spin = QSpinBox()
        self._tab_spin.setStyleSheet(SPIN_STYLE)
        self._tab_spin.setRange(1, 8)
        self._tab_spin.setSuffix(" spaces")
        self._tab_spin.setValue(self.config.get("editor.tab_width", 2))
        self._tab_spin.valueChanged.connect(
            lambda v: self._save_and_apply("editor.tab_width", v)
        )
        form.addRow("Tab width:", self._tab_spin)

        self._wrap_cb = QCheckBox("Wrap long lines")
        self._wrap_cb.setStyleSheet(f"color: {FG_PRIMARY};")
        self._wrap_cb.setChecked(self.config.get("editor.wrap_lines", True))
        self._wrap_cb.stateChanged.connect(
            lambda s: self._save_and_apply("editor.wrap_lines", bool(s))
        )
        form.addRow("Word wrap:", self._wrap_cb)

        layout.addLayout(form)

        # Live preview label
        self._preview_label = QLabel("The quick brown fox jumps over the lazy dog")
        self._preview_label.setStyleSheet(
            f"color: {FG_SECONDARY}; padding: 8px; "
            f"background: {BG_DARK}; border-radius: 3px;"
        )
        self._update_preview_font()
        layout.addWidget(self._preview_label)

        layout.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scroll_wrap(inner))

    def _on_font_changed(self, family: str):
        self._save_and_apply("editor.font_family", family)
        self._update_preview_font()

    def _on_size_changed(self, size: int):
        self._save_and_apply("editor.font_size", size)
        self._update_preview_font()

    def _update_preview_font(self):
        family = self._font_combo.currentText()
        size   = self._size_spin.value()
        self._preview_label.setFont(QFont(family, size))

    def _save_and_apply(self, key: str, value):
        self.config.set(key, value)
        self.config.save()
        mw = self.window()
        if hasattr(mw, "editor_tab"):
            mw.editor_tab.apply_settings()


# ── Sources tab ───────────────────────────────────────────────────────────────

SOURCES_PATH = Path(__file__).parent.parent / "config" / "sources.json"

# Default sources used by Reset button
DEFAULT_SOURCES = [
    {"owner": "anthropics",  "repo": "skills",              "type": "direct",  "skills_prefix": "skills/", "description": "Official Anthropic example skills", "enabled": True},
    {"owner": "VoltAgent",   "repo": "awesome-agent-skills","type": "awesome", "skills_prefix": None,       "description": "383+ skills from official engineering teams", "enabled": True},
    {"owner": "travisvn",    "repo": "awesome-claude-skills","type": "awesome","skills_prefix": None,       "description": "Curated community skills list", "enabled": True},
    {"owner": "ComposioHQ",  "repo": "awesome-claude-skills","type": "awesome","skills_prefix": None,       "description": "78 SaaS app integrations", "enabled": True},
    {"owner": "hesreallyhim","repo": "awesome-claude-code",  "type": "awesome","skills_prefix": None,       "description": "Broader Claude Code ecosystem", "enabled": True},
    {"owner": "BehiSecc",    "repo": "awesome-claude-skills","type": "awesome","skills_prefix": None,       "description": "Community skills - scientific, security, health", "enabled": True},
    {"owner": "obra",        "repo": "superpowers-skills",  "type": "direct",  "skills_prefix": "skills/", "description": "20+ battle-tested skills", "enabled": True},
    {"owner": "trailofbits", "repo": "skills",              "type": "direct",  "skills_prefix": "skills/", "description": "22 professional security skills", "enabled": True},
]


class SourcesWidget(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config   = config
        self._sources: list[dict] = []
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        hdr = QLabel(
            "These are the GitHub repositories shown in the Search → Source Repos tab. "
            "Changes take effect immediately.",
            styleSheet=HINT_STYLE,
        )
        hdr.setWordWrap(True)
        layout.addWidget(hdr)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Type", "Owner / Repo", "Prefix", "Description"])
        self._table.verticalHeader().hide()
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setStyleSheet(TABLE_STYLE)
        hdr_view = self._table.horizontalHeader()
        hdr_view.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr_view.setStretchLastSection(False)
        self._table.setColumnWidth(0,  70)
        self._table.setColumnWidth(1, 200)
        self._table.setColumnWidth(2,  90)
        self._table.setColumnWidth(3, 300)
        self._table.doubleClicked.connect(self._edit)
        layout.addWidget(self._table, 1)

        btn_row = QHBoxLayout()
        for label, tip, slot in [
            ("Add",             "Add a new source repo",      self._add),
            ("Edit",            "Edit selected source",       self._edit),
            ("Remove",          "Remove selected source",     self._remove),
            ("Reset to defaults","Restore the original list", self._reset),
        ]:
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setStyleSheet(BTN_STYLE)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _load(self):
        if SOURCES_PATH.exists():
            try:
                self._sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
            except Exception:
                logger.exception("Failed to load sources.json")
                self._sources = list(DEFAULT_SOURCES)
        else:
            self._sources = list(DEFAULT_SOURCES)
        self._populate()

    def _save(self):
        try:
            SOURCES_PATH.write_text(
                json.dumps(self._sources, indent=2), encoding="utf-8"
            )
            # Tell search tab to reload
            mw = self.window()
            if hasattr(mw, "search_tab"):
                mw.search_tab._source_tab._load_sources()
        except Exception:
            logger.exception("Failed to save sources.json")

    def _populate(self):
        self._table.setRowCount(0)
        for src in self._sources:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(src.get("type", "direct")))
            self._table.setItem(r, 1, QTableWidgetItem(
                f"{src['owner']}/{src['repo']}"
            ))
            self._table.setItem(r, 2, QTableWidgetItem(
                src.get("skills_prefix") or ""
            ))
            self._table.setItem(r, 3, QTableWidgetItem(
                src.get("description", "")
            ))

    def _selected_row(self) -> int:
        rows = self._table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _add(self):
        dlg = SourceDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._sources.append(dlg.get_source())
            self._populate()
            self._save()

    def _edit(self, _index=None):
        row = self._selected_row()
        if row < 0:
            return
        dlg = SourceDialog(source=self._sources[row], parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._sources[row] = dlg.get_source()
            self._populate()
            self._save()

    def _remove(self):
        row = self._selected_row()
        if row < 0:
            return
        src = self._sources[row]
        reply = QMessageBox.question(
            self, "Remove Source",
            f"Remove {src['owner']}/{src['repo']}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            del self._sources[row]
            self._populate()
            self._save()

    def _reset(self):
        reply = QMessageBox.question(
            self, "Reset Sources",
            "Replace the sources list with the default 8 sources?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._sources = list(DEFAULT_SOURCES)
            self._populate()
            self._save()


# ── About tab ─────────────────────────────────────────────────────────────────

class AboutWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        from main import APP_NAME, APP_VERSION
        title = QLabel(f"{APP_NAME}  v{APP_VERSION}")
        title.setStyleSheet(f"color: {FG_PRIMARY}; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel(
            "Visual editor and manager for Claude Code Skills (SKILL.md files).\n"
            "Create, browse, validate, and import skills from community repos."
        )
        desc.setStyleSheet(f"color: {FG_SECONDARY}; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addWidget(self._hsep())

        links = [
            ("Skills Specification",    "https://agentskills.io/specification"),
            ("Official Anthropic Skills","https://github.com/anthropics/skills"),
            ("VoltAgent Awesome Skills", "https://github.com/VoltAgent/awesome-agent-skills"),
            ("Superpowers Skills",       "https://github.com/obra/superpowers-skills"),
            ("Trail of Bits Security",   "https://github.com/trailofbits/skills"),
            ("Source on GitHub",         "https://github.com/RafalekS/skills_builder"),
        ]
        layout.addWidget(QLabel("Links:", styleSheet=f"color: {FG_SECONDARY}; font-size: 12px;"))
        for label, url in links:
            btn = QPushButton(label)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: none; color: {ACCENT};
                    border: none; text-align: left;
                    font-size: 12px; padding: 2px 0;
                }}
                QPushButton:hover {{ color: #79b8ff; }}
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked, u=url: webbrowser.open(u))
            layout.addWidget(btn)

        layout.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(_scroll_wrap(inner))

    @staticmethod
    def _hsep() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BG_LIGHT};")
        return sep


# ── Main Settings Tab ─────────────────────────────────────────────────────────

class SettingsTab(QWidget):

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._paths_widget   = PathsWidget(self.config,  parent=self)
        self._github_widget  = GitHubWidget(self.config, parent=self)
        self._editor_widget  = EditorWidget(self.config, parent=self)
        self._sources_widget = SourcesWidget(self.config, parent=self)
        self._about_widget   = AboutWidget(parent=self)

        self._tabs.addTab(self._paths_widget,   "Paths")
        self._tabs.addTab(self._github_widget,  "GitHub")
        self._tabs.addTab(self._editor_widget,  "Editor")
        self._tabs.addTab(self._sources_widget, "Sources")
        self._tabs.addTab(self._about_widget,   "About")

        layout.addWidget(self._tabs)
