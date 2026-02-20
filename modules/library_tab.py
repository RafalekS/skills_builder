"""
Library Tab - Local skill library browser
"""

import logging
import platform
import shutil
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QLineEdit, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QFileDialog,
    QSplitter, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from modules.skill_io import SkillIO
from modules.syntax_highlighter import SkillHighlighter
from modules.theme import (
    BG_DARK, BG_MEDIUM, BG_LIGHT,
    FG_PRIMARY, FG_SECONDARY, FG_DIM,
    ACCENT, ERROR_RED,
)

logger = logging.getLogger(__name__)

BTN_STYLE = f"""
    QPushButton {{
        background-color: {BG_LIGHT};
        color: {FG_PRIMARY};
        border: 1px solid #3a3a3d;
        padding: 4px 10px;
        border-radius: 3px;
    }}
    QPushButton:hover {{ background-color: #3a3a3d; }}
    QPushButton:pressed {{ background-color: {ACCENT}; color: #ffffff; }}
    QPushButton:disabled {{ color: {FG_DIM}; }}
"""

TABLE_STYLE = f"""
    QTableWidget {{
        background: {BG_DARK};
        color: {FG_PRIMARY};
        border: 1px solid {BG_LIGHT};
        gridline-color: {BG_LIGHT};
        selection-background-color: {ACCENT};
        font-size: 12px;
    }}
    QTableWidget::item {{ padding: 3px 6px; }}
    QHeaderView::section {{
        background: {BG_MEDIUM};
        color: {FG_SECONDARY};
        padding: 4px 6px;
        border: 1px solid {BG_LIGHT};
        font-size: 12px;
    }}
"""


# ── Background scanner ────────────────────────────────────────────────────────

class ScanWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, skills_dir: Path):
        super().__init__()
        self._dir = skills_dir

    def run(self):
        skills = SkillIO().list_skills(self._dir)
        self.finished.emit(skills)


# ── Per-scope widget (shared between User / Project sub-tabs) ─────────────────

class SkillScopeWidget(QWidget):
    open_in_editor = pyqtSignal(object)   # Path

    def __init__(self, config, scope: str, parent=None):
        super().__init__(parent)
        self.config    = config
        self.scope     = scope
        self.skill_io  = SkillIO()
        self._all_skills: list[dict] = []
        self._skills:     list[dict] = []
        self._worker = None
        self._build_ui()
        self.refresh()

    def _get_dir(self) -> Path | None:
        if self.scope == "user":
            return self.config.get_user_skills_dir()
        return self.config.get_project_skills_dir()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Path bar
        top = QHBoxLayout()
        self._path_label = QLabel("")
        self._path_label.setStyleSheet(f"color: {FG_DIM}; font-size: 11px;")
        self._path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        top.addWidget(self._path_label)

        change_btn = QPushButton("Change…")
        change_btn.setStyleSheet(BTN_STYLE)
        change_btn.setToolTip("Change the skills directory")
        change_btn.clicked.connect(self._change_dir)
        top.addWidget(change_btn)

        folder_btn = QPushButton("Open Folder")
        folder_btn.setStyleSheet(BTN_STYLE)
        folder_btn.setToolTip("Open skills directory in file explorer")
        folder_btn.clicked.connect(self._open_folder)
        top.addWidget(folder_btn)
        layout.addLayout(top)

        # Filter + import buttons
        filter_row = QHBoxLayout()
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter skills…")
        self._filter_edit.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_MEDIUM}; color: {FG_PRIMARY};
                border: 1px solid #3a3a3d; border-radius: 3px;
                padding: 3px 6px; font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self._filter_edit.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._filter_edit, 1)

        for label, tip, slot in [
            ("Import ZIP…", "Import skill(s) from a ZIP file",      self._import_zip),
            ("Import Dir…", "Import skill from a local directory",   self._import_dir),
        ]:
            b = QPushButton(label)
            b.setStyleSheet(BTN_STYLE)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            filter_row.addWidget(b)
        layout.addLayout(filter_row)

        # Splitter: table on top, preview below
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BG_LIGHT}; }}")

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Name", "Description", "Tools", "Files", "Modified"])
        self._table.verticalHeader().hide()
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.setStyleSheet(TABLE_STYLE)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setStretchLastSection(False)
        self._table.setColumnWidth(0, 150)
        self._table.setColumnWidth(1, 280)
        self._table.setColumnWidth(2, 140)
        self._table.setColumnWidth(3,  55)
        self._table.setColumnWidth(4, 130)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.doubleClicked.connect(self._on_double_click)
        splitter.addWidget(self._table)

        # Preview
        preview_wrap = QWidget()
        preview_wrap.setStyleSheet(f"background: {BG_DARK};")
        pw_layout = QVBoxLayout(preview_wrap)
        pw_layout.setContentsMargins(0, 0, 0, 0)
        pw_layout.setSpacing(0)

        preview_hdr = QLabel("Preview")
        preview_hdr.setStyleSheet(
            f"color: {FG_SECONDARY}; font-size: 11px; padding: 3px 8px; "
            f"background: {BG_MEDIUM}; border-top: 1px solid {BG_LIGHT};"
        )
        pw_layout.addWidget(preview_hdr)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setStyleSheet(f"""
            QTextEdit {{
                background: {BG_DARK}; color: {FG_PRIMARY};
                border: none; padding: 8px; font-size: 12px;
            }}
        """)
        self._preview.setFont(QFont("Consolas", 11))
        self._highlighter = SkillHighlighter(self._preview.document())
        pw_layout.addWidget(self._preview)
        splitter.addWidget(preview_wrap)

        splitter.setSizes([400, 180])
        layout.addWidget(splitter, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        for label, tip, slot in [
            ("New",         "Create a new skill",               self._new_skill),
            ("Edit",        "Open selected skill in editor",    self._edit_skill),
            ("Duplicate",   "Duplicate selected skill",         self._duplicate_skill),
            ("Delete",      "Delete selected skill",            self._delete_skill),
            ("Export ZIP",  "Export selected skill to ZIP",     self._export_zip),
            ("Refresh",     "Re-scan skills directory",         self.refresh),
        ]:
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setStyleSheet(BTN_STYLE)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._update_path_label()

    # ── Data ─────────────────────────────────────────────────────────────────

    def _update_path_label(self):
        d = self._get_dir()
        if d:
            display = str(d).replace(str(Path.home()), "~")
            self._path_label.setText(f"{display}  ({len(self._all_skills)} skills)")
        else:
            self._path_label.setText("(no directory configured)")

    def refresh(self):
        d = self._get_dir()
        if not d:
            self._all_skills = []
            self._apply_filter()
            self._update_path_label()
            return
        if self._worker and self._worker.isRunning():
            return
        self._worker = ScanWorker(d)
        self._worker.finished.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, skills: list):
        self._all_skills = skills
        self._apply_filter()
        self._update_path_label()

    def _apply_filter(self, text: str = ""):
        text = (text or self._filter_edit.text()).lower().strip()
        if text:
            self._skills = [
                s for s in self._all_skills
                if text in s["name"].lower() or text in s["description"].lower()
            ]
        else:
            self._skills = list(self._all_skills)
        self._populate_table()

    def _populate_table(self):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for skill in self._skills:
            row = self._table.rowCount()
            self._table.insertRow(row)

            self._table.setItem(row, 0, QTableWidgetItem(skill["name"]))

            desc = skill["description"]
            if len(desc) > 90:
                desc = desc[:87] + "…"
            self._table.setItem(row, 1, QTableWidgetItem(desc))

            tools = skill["frontmatter"].get("allowed-tools", "")
            self._table.setItem(row, 2, QTableWidgetItem(str(tools) if tools else ""))

            n_files = len(skill["extra_files"])
            fi = QTableWidgetItem(str(n_files) if n_files else "")
            fi.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, fi)

            self._table.setItem(row, 4, QTableWidgetItem(
                skill["modified"].strftime("%Y-%m-%d %H:%M")
            ))
        self._table.setSortingEnabled(True)
        self._preview.clear()

    def _selected_skill(self) -> dict | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        # Table may be sorted — look up by name
        name = self._table.item(rows[0].row(), 0).text()
        return next((s for s in self._skills if s["name"] == name), None)

    # ── Events ────────────────────────────────────────────────────────────────

    def _on_selection_changed(self):
        skill = self._selected_skill()
        if skill is None:
            self._preview.clear()
            return
        try:
            data = self.skill_io.read_skill(skill["path"])
            self._preview.setPlainText(data["full_content"])
        except Exception as e:
            self._preview.setPlainText(f"Error reading skill: {e}")

    def _on_double_click(self, _index):
        skill = self._selected_skill()
        if skill:
            self.open_in_editor.emit(skill["path"])

    # ── Actions ───────────────────────────────────────────────────────────────

    def _new_skill(self):
        mw = self.window()
        if hasattr(mw, "tabs") and hasattr(mw, "editor_tab"):
            mw.tabs.setCurrentWidget(mw.editor_tab)
            mw.editor_tab.action_new()

    def _edit_skill(self):
        skill = self._selected_skill()
        if skill:
            self.open_in_editor.emit(skill["path"])

    def _duplicate_skill(self):
        skill = self._selected_skill()
        if not skill:
            return
        d = self._get_dir()
        if not d:
            return
        dest = d / (skill["name"] + "-copy")
        n = 1
        while dest.exists():
            dest = d / f"{skill['name']}-copy{n}"
            n += 1
        try:
            shutil.copytree(skill["path"], dest)
            self.refresh()
            self.open_in_editor.emit(dest)
        except Exception as e:
            QMessageBox.critical(self, "Duplicate Error", f"Failed to duplicate:\n{e}")

    def _delete_skill(self):
        skill = self._selected_skill()
        if not skill:
            return
        reply = QMessageBox.question(
            self, "Delete Skill",
            f"Delete '{skill['name']}'?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if self.skill_io.delete_skill(skill["path"]):
            self.refresh()
            self._set_status(f"Deleted '{skill['name']}'")
        else:
            QMessageBox.critical(self, "Delete Error", "Failed to delete skill.")

    def _export_zip(self):
        skill = self._selected_skill()
        if not skill:
            QMessageBox.information(self, "No selection", "Select a skill to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export ZIP",
            str(Path.home() / f"{skill['name']}.zip"),
            "ZIP files (*.zip)",
        )
        if not path:
            return
        if self.skill_io.export_zip([skill["path"]], Path(path)):
            self._set_status(f"Exported to {path}")
        else:
            QMessageBox.critical(self, "Export Error", "Failed to create ZIP.")

    def _import_zip(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import ZIP", str(Path.home()), "ZIP files (*.zip)"
        )
        if not path:
            return
        d = self._get_dir()
        if not d:
            QMessageBox.warning(self, "No directory", "No skills directory configured.")
            return
        imported = self.skill_io.import_zip(Path(path), d)
        if imported:
            self.refresh()
            self._set_status(f"Imported: {', '.join(imported)}")
        else:
            QMessageBox.information(
                self, "Import",
                "No skills imported (already exist or invalid ZIP)."
            )

    def _import_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select skill directory")
        if not folder:
            return
        source = Path(folder)
        if not (source / "SKILL.md").exists():
            QMessageBox.warning(self, "Not a skill", f"No SKILL.md found in:\n{source}")
            return
        d = self._get_dir()
        if not d:
            return
        ok = self.skill_io.import_from_dir(source, d, overwrite=False)
        if ok:
            self.refresh()
            self._set_status(f"Imported '{source.name}'")
        else:
            reply = QMessageBox.question(
                self, "Already exists",
                f"Skill '{source.name}' already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.skill_io.import_from_dir(source, d, overwrite=True)
                self.refresh()

    def _change_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select skills directory")
        if not folder:
            return
        key = "skills.user_skills_dir" if self.scope == "user" else "skills.project_skills_dir"
        self.config.set(key, folder)
        self.config.save()
        self.refresh()

    def _open_folder(self):
        d = self._get_dir()
        if not d:
            return
        d.mkdir(parents=True, exist_ok=True)
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(["explorer", str(d)], encoding="utf-8", errors="replace")
        elif system == "Darwin":
            subprocess.Popen(["open", str(d)])
        else:
            subprocess.Popen(["xdg-open", str(d)])

    def _set_status(self, msg: str):
        mw = self.window()
        if hasattr(mw, "set_status"):
            mw.set_status(msg)
        if hasattr(mw, "_refresh_skills_status"):
            mw._refresh_skills_status()


# ── Library Tab ───────────────────────────────────────────────────────────────

class LibraryTab(QWidget):

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._user_tab    = SkillScopeWidget(self.config, "user",    parent=self)
        self._project_tab = SkillScopeWidget(self.config, "project", parent=self)

        self._user_tab.open_in_editor.connect(self._open_in_editor)
        self._project_tab.open_in_editor.connect(self._open_in_editor)

        self._tabs.addTab(self._user_tab,    "User Skills  (~/.claude/skills)")
        self._tabs.addTab(self._project_tab, "Project Skills  (.claude/skills)")

        layout.addWidget(self._tabs)

    def _open_in_editor(self, skill_path: Path):
        mw = self.window()
        if hasattr(mw, "tabs") and hasattr(mw, "editor_tab"):
            mw.editor_tab.load_skill(skill_path)
            mw.tabs.setCurrentWidget(mw.editor_tab)

    def refresh(self):
        self._user_tab.refresh()
        self._project_tab.refresh()
