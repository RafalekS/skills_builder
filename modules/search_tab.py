"""
Search Tab - GitHub skill discovery and import
Three sub-tabs: Source Repos | GitHub Search | URL Import
"""

import json
import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QLineEdit, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSplitter, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QComboBox, QMessageBox,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from modules.skill_io import SkillIO
from modules.syntax_highlighter import SkillHighlighter
from modules.theme import (
    BG_DARK, BG_MEDIUM, BG_LIGHT,
    FG_PRIMARY, FG_SECONDARY, FG_DIM,
    ACCENT, ERROR_RED, WARN_ORANGE,
)

logger = logging.getLogger(__name__)

# ── Styles ────────────────────────────────────────────────────────────────────

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

INPUT_STYLE = f"""
    QLineEdit {{
        background: {BG_MEDIUM}; color: {FG_PRIMARY};
        border: 1px solid #3a3a3d; border-radius: 3px;
        padding: 4px 8px; font-size: 12px;
    }}
    QLineEdit:focus {{ border-color: {ACCENT}; }}
"""

STATUS_STYLE   = f"color: {FG_DIM}; font-size: 11px;"
SECTION_STYLE  = f"color: {FG_SECONDARY}; font-size: 12px;"


# ── Worker threads ────────────────────────────────────────────────────────────

class FetchRepoWorker(QThread):
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, client, owner: str, repo: str, prefix: str):
        super().__init__()
        self._client = client
        self._owner  = owner
        self._repo   = repo
        self._prefix = prefix

    def run(self):
        try:
            self.finished.emit(
                self._client.list_skills_in_repo(self._owner, self._repo, self._prefix)
            )
        except Exception as e:
            self.error.emit(str(e))


class FetchReadmeWorker(QThread):
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, client, owner: str, repo: str):
        super().__init__()
        self._client = client
        self._owner  = owner
        self._repo   = repo

    def run(self):
        try:
            readme = self._client.get_readme(self._owner, self._repo)
            self.finished.emit(
                self._client.extract_skill_repos_from_readme(readme) if readme else []
            )
        except Exception as e:
            self.error.emit(str(e))


class SearchWorker(QThread):
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, client, query: str, db):
        super().__init__()
        self._client = client
        self._query  = query
        self._db     = db

    def run(self):
        try:
            if self._db:
                cached = self._db.search_results_get(self._query)
                if cached:
                    self.finished.emit(cached)
                    return
            results = self._client.search_code(self._query)
            if self._db and results:
                self._db.search_results_set(self._query, results)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class FetchUrlWorker(QThread):
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, client, url: str):
        super().__init__()
        self._client = client
        self._url    = url

    def run(self):
        try:
            result = self._client.fetch_skill_from_url(self._url)
            if result:
                self.finished.emit(result)
            else:
                self.error.emit("Could not fetch skill from this URL.")
        except Exception as e:
            self.error.emit(str(e))


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_preview() -> QTextEdit:
    p = QTextEdit()
    p.setReadOnly(True)
    p.setStyleSheet(f"""
        QTextEdit {{
            background: {BG_DARK}; color: {FG_PRIMARY};
            border: none; padding: 8px; font-size: 12px;
        }}
    """)
    p.setFont(QFont("Consolas", 11))
    SkillHighlighter(p.document())
    return p


def _make_table(columns: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(columns))
    t.setHorizontalHeaderLabels(columns)
    t.verticalHeader().hide()
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSortingEnabled(True)
    t.setStyleSheet(TABLE_STYLE)
    hdr = t.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    hdr.setStretchLastSection(False)
    return t


def _vsep() -> QWidget:
    f = QWidget()
    f.setFixedWidth(1)
    f.setStyleSheet(f"background: {BG_LIGHT};")
    return f


# ── Import Dialog ─────────────────────────────────────────────────────────────

class ImportDialog(QDialog):
    def __init__(self, config, skill_name: str = "", parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Import Skill")
        self.setModal(True)
        self.setMinimumWidth(430)
        self._build_ui(skill_name)

    def _build_ui(self, skill_name: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Save to:", styleSheet=SECTION_STYLE))
        self.dest_combo = QComboBox()
        self.dest_combo.setStyleSheet(COMBO_STYLE)
        user_dir = self.config.get_user_skills_dir()
        self.dest_combo.addItem("User skills  (~/.claude/skills)", user_dir)
        proj_dir = self.config.get_project_skills_dir()
        if proj_dir:
            self.dest_combo.addItem(f"Project skills  ({proj_dir.name})", proj_dir)
        self.dest_combo.currentIndexChanged.connect(self._update_preview)
        layout.addWidget(self.dest_combo)

        layout.addWidget(QLabel("If skill already exists:", styleSheet=SECTION_STYLE))
        self.conflict_combo = QComboBox()
        self.conflict_combo.setStyleSheet(COMBO_STYLE)
        self.conflict_combo.addItems(["Skip (keep existing)", "Overwrite"])
        layout.addWidget(self.conflict_combo)

        self._preview_lbl = QLabel("")
        self._preview_lbl.setStyleSheet(f"color: {FG_DIM}; font-size: 11px;")
        self._preview_lbl.setWordWrap(True)
        self._skill_name = skill_name
        layout.addWidget(self._preview_lbl)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_preview()

    def _update_preview(self):
        dest = self.dest_combo.currentData()
        if dest and self._skill_name:
            self._preview_lbl.setText(f"→ {dest / self._skill_name / 'SKILL.md'}")
        else:
            self._preview_lbl.setText("")

    def get_result(self) -> tuple[Path | None, bool]:
        return self.dest_combo.currentData(), self.conflict_combo.currentIndex() == 1


# ── Sub-tab 1: Source Repos ───────────────────────────────────────────────────

class SourceReposTab(QWidget):

    def __init__(self, config, client, parent=None):
        super().__init__(parent)
        self.config   = config
        self.client   = client
        self._sources: list[dict] = []
        self._skills:  list[dict] = []
        self._worker = None
        self._build_ui()
        self._load_sources()

    def _load_sources(self):
        sources_path = Path(__file__).parent.parent / "config" / "sources.json"
        self._sources = []
        if sources_path.exists():
            try:
                self._sources = json.loads(sources_path.read_text(encoding="utf-8"))
            except Exception:
                logger.exception("Failed to load sources.json")
        self._source_list.clear()
        for src in self._sources:
            item = QListWidgetItem(f"{src['owner']}/{src['repo']}")
            item.setToolTip(src.get("description", ""))
            self._source_list.addItem(item)

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Left: source list
        left = QWidget()
        left.setMaximumWidth(220)
        left.setMinimumWidth(160)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("Sources:", styleSheet=SECTION_STYLE))

        self._source_list = QListWidget()
        self._source_list.setStyleSheet(f"""
            QListWidget {{
                background: {BG_MEDIUM}; color: {FG_PRIMARY};
                border: 1px solid {BG_LIGHT}; font-size: 12px;
            }}
            QListWidget::item:selected {{ background: {ACCENT}; color: #fff; }}
            QListWidget::item:hover {{ background: {BG_LIGHT}; }}
        """)
        self._source_list.currentRowChanged.connect(self._on_source_changed)
        ll.addWidget(self._source_list, 1)

        fetch_btn = QPushButton("Fetch / Refresh")
        fetch_btn.setStyleSheet(BTN_STYLE)
        fetch_btn.setToolTip("Fetch skills from selected source (bypasses cache)")
        fetch_btn.clicked.connect(self._fetch_selected)
        ll.addWidget(fetch_btn)
        layout.addWidget(left)
        layout.addWidget(_vsep())

        # Right: skills table + preview
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)

        self._status_label = QLabel("Select a source and click Fetch / Refresh")
        self._status_label.setStyleSheet(STATUS_STYLE)
        rl.addWidget(self._status_label)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BG_LIGHT}; }}")

        self._table = _make_table(["Name", "Description", "Stars", "Repo"])
        self._table.setColumnWidth(0, 140)
        self._table.setColumnWidth(1, 300)
        self._table.setColumnWidth(2,  60)
        self._table.setColumnWidth(3, 160)
        self._table.itemSelectionChanged.connect(self._on_skill_selected)
        splitter.addWidget(self._table)

        self._preview = _make_preview()
        splitter.addWidget(self._preview)
        splitter.setSizes([360, 180])
        rl.addWidget(splitter, 1)

        btn_row = QHBoxLayout()
        import_btn = QPushButton("Import Selected")
        import_btn.setStyleSheet(BTN_STYLE)
        import_btn.clicked.connect(self._import_selected)
        btn_row.addWidget(import_btn)
        btn_row.addStretch()
        rl.addLayout(btn_row)

        layout.addWidget(right, 1)

    def _on_source_changed(self, row: int):
        if 0 <= row < len(self._sources):
            src = self._sources[row]
            self._status_label.setText(
                f"{src.get('description', '')} — click Fetch / Refresh to load"
            )
        self._table.setRowCount(0)
        self._preview.clear()
        self._skills = []

    def _fetch_selected(self):
        row = self._source_list.currentRow()
        if row < 0 or row >= len(self._sources):
            QMessageBox.information(self, "No source", "Select a source first.")
            return
        src    = self._sources[row]
        owner  = src["owner"]
        repo   = src["repo"]
        stype  = src.get("type", "direct")
        prefix = src.get("skills_prefix") or ""

        # Clear cache for this source so we get fresh data
        if self.client._db:
            self.client._db.cache_clear(f"{self.client.GITHUB_API if hasattr(self.client, 'GITHUB_API') else 'https://api.github.com'}/repos/{owner}/{repo}")

        self._status_label.setText(f"Fetching {owner}/{repo}…")
        self._table.setRowCount(0)
        self._skills = []

        if stype == "direct":
            self._worker = FetchRepoWorker(self.client, owner, repo, prefix)
            self._worker.finished.connect(self._on_skills_fetched)
            self._worker.error.connect(self._on_error)
        else:
            self._worker = FetchReadmeWorker(self.client, owner, repo)
            self._worker.finished.connect(self._on_repos_from_readme)
            self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_skills_fetched(self, skills: list):
        self._skills = skills
        self._status_label.setText(f"{len(skills)} skills found")
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for s in skills:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(s.get("name", "")))
            desc = s.get("description", "")
            if len(desc) > 80:
                desc = desc[:77] + "…"
            self._table.setItem(r, 1, QTableWidgetItem(desc))
            si = QTableWidgetItem(str(s.get("stars", 0)))
            si.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(r, 2, si)
            self._table.setItem(r, 3, QTableWidgetItem(
                f"{s.get('owner','')}/{s.get('repo','')}"
            ))
        self._table.setSortingEnabled(True)
        self._emit_rate_limit()

    def _on_repos_from_readme(self, repos: list):
        """Awesome-type repo: show linked repos in the table."""
        self._skills = []
        self._status_label.setText(
            f"{len(repos)} linked repos found in README — these are skill repo links, not individual skills"
        )
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for rd in repos:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(rd.get("label", "")))
            self._table.setItem(r, 1, QTableWidgetItem(""))
            self._table.setItem(r, 2, QTableWidgetItem(""))
            self._table.setItem(r, 3, QTableWidgetItem(
                f"{rd['owner']}/{rd['repo']}"
            ))
        self._table.setSortingEnabled(True)

    def _on_error(self, msg: str):
        self._status_label.setText(f"Error: {msg}")
        logger.error("Source fetch error: %s", msg)

    def _on_skill_selected(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._preview.clear()
            return
        idx = rows[0].row()
        if idx < len(self._skills):
            self._preview.setPlainText(self._skills[idx].get("content", ""))
        else:
            self._preview.clear()

    def _import_selected(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "No selection", "Select a skill to import.")
            return
        idx = rows[0].row()
        if idx >= len(self._skills):
            QMessageBox.information(
                self, "No skill data",
                "No content to import — this source shows repo links, not individual skills.\n"
                "Use the GitHub Search tab or URL Import tab to fetch specific skills."
            )
            return
        skill = self._skills[idx]
        self._do_import(skill.get("name", "imported-skill"), skill.get("content", ""))

    def _do_import(self, name: str, content: str):
        dialog = ImportDialog(self.config, name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        dest_dir, overwrite = dialog.get_result()
        if not dest_dir:
            return
        skill_dir = dest_dir / name
        if skill_dir.exists() and not overwrite:
            self._set_status(f"Skipped '{name}' — already exists")
            return
        SkillIO().write_skill(dest_dir, name, content)
        self._set_status(f"Imported '{name}' to {dest_dir}")

    def _emit_rate_limit(self):
        if self.client.rate_limit:
            mw = self.window()
            if hasattr(mw, "set_api_status"):
                mw.set_api_status(str(self.client.rate_limit))

    def _set_status(self, msg: str):
        mw = self.window()
        if hasattr(mw, "set_status"):
            mw.set_status(msg)
        if hasattr(mw, "_refresh_skills_status"):
            mw._refresh_skills_status()


# ── Sub-tab 2: GitHub Search ──────────────────────────────────────────────────

class GitHubSearchTab(QWidget):

    def __init__(self, config, client, db, parent=None):
        super().__init__(parent)
        self.config   = config
        self.client   = client
        self.db       = db
        self._skills: list[dict] = []
        self._worker = None
        self._fetch_worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        search_row = QHBoxLayout()
        self._query_edit = QLineEdit()
        self._query_edit.setPlaceholderText("Search for skills by keyword…")
        self._query_edit.setStyleSheet(INPUT_STYLE)
        self._query_edit.returnPressed.connect(self._search)
        search_row.addWidget(self._query_edit, 1)

        search_btn = QPushButton("Search")
        search_btn.setStyleSheet(BTN_STYLE)
        search_btn.clicked.connect(self._search)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        note = QLabel(
            "GitHub code search requires authentication for reliable results. "
            "Add a Personal Access Token in Settings for 5000 requests/hour."
        )
        note.setStyleSheet(f"color: {FG_DIM}; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(STATUS_STYLE)
        layout.addWidget(self._status_label)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BG_LIGHT}; }}")

        self._table = _make_table(["Name", "Repo", "Description", "Stars", "URL"])
        self._table.setColumnWidth(0, 130)
        self._table.setColumnWidth(1, 150)
        self._table.setColumnWidth(2, 220)
        self._table.setColumnWidth(3,  60)
        self._table.setColumnWidth(4, 200)
        self._table.itemSelectionChanged.connect(self._on_skill_selected)
        splitter.addWidget(self._table)

        self._preview = _make_preview()
        splitter.addWidget(self._preview)
        splitter.setSizes([360, 180])
        layout.addWidget(splitter, 1)

        btn_row = QHBoxLayout()
        import_btn = QPushButton("Import Selected")
        import_btn.setStyleSheet(BTN_STYLE)
        import_btn.clicked.connect(self._import_selected)
        btn_row.addWidget(import_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _search(self):
        query = self._query_edit.text().strip()
        if not query:
            return
        self._status_label.setText(f"Searching for '{query}'…")
        self._table.setRowCount(0)
        self._skills = []
        self._preview.clear()

        self._worker = SearchWorker(self.client, query, self.db)
        self._worker.finished.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_results(self, results: list):
        self._skills = results
        self._status_label.setText(f"{len(results)} results")
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for s in results:
            r = self._table.rowCount()
            self._table.insertRow(r)
            # skill name comes from the path part before SKILL.md
            url = s.get("url", "")
            name = s.get("skill_name", "")
            if name == "SKILL.md" and url:
                # Extract skill dir name from URL
                parts = url.rstrip("/").split("/")
                name = parts[-2] if len(parts) >= 2 else name
            self._table.setItem(r, 0, QTableWidgetItem(name))
            self._table.setItem(r, 1, QTableWidgetItem(
                f"{s.get('owner','')}/{s.get('repo','')}"
            ))
            desc = s.get("description", "")
            if len(desc) > 60:
                desc = desc[:57] + "…"
            self._table.setItem(r, 2, QTableWidgetItem(desc))
            si = QTableWidgetItem(str(s.get("stars", 0)))
            si.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(r, 3, si)
            self._table.setItem(r, 4, QTableWidgetItem(url))
        self._table.setSortingEnabled(True)

        if self.client.rate_limit:
            mw = self.window()
            if hasattr(mw, "set_api_status"):
                mw.set_api_status(str(self.client.rate_limit))

    def _on_error(self, msg: str):
        self._status_label.setText(f"Error: {msg}")

    def _on_skill_selected(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._preview.clear()
            return
        idx = rows[0].row()
        if idx >= len(self._skills):
            return
        url = self._skills[idx].get("url", "")
        if not url:
            return
        self._preview.setPlainText("Fetching preview…")
        self._fetch_worker = FetchUrlWorker(self.client, url)
        self._fetch_worker.finished.connect(
            lambda d: self._preview.setPlainText(d.get("content", ""))
        )
        self._fetch_worker.error.connect(
            lambda e: self._preview.setPlainText(f"Preview unavailable: {e}")
        )
        self._fetch_worker.start()

    def _import_selected(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "No selection", "Select a skill to import.")
            return
        idx = rows[0].row()
        if idx >= len(self._skills):
            return
        s   = self._skills[idx]
        url = s.get("url", "")
        if not url:
            return
        result = self.client.fetch_skill_from_url(url)
        if not result:
            QMessageBox.warning(self, "Fetch Failed", "Could not fetch skill content.")
            return
        name = result.get("name") or s.get("skill_name") or "imported-skill"
        if name == "SKILL.md":
            name = "imported-skill"
        dialog = ImportDialog(self.config, name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        dest_dir, overwrite = dialog.get_result()
        if not dest_dir:
            return
        SkillIO().write_skill(dest_dir, name, result.get("content", ""))
        mw = self.window()
        if hasattr(mw, "set_status"):
            mw.set_status(f"Imported '{name}' to {dest_dir}")
        if hasattr(mw, "_refresh_skills_status"):
            mw._refresh_skills_status()

    def _on_error(self, msg: str):
        self._status_label.setText(f"Error: {msg}")


# ── Sub-tab 3: URL Import ─────────────────────────────────────────────────────

class UrlImportTab(QWidget):

    def __init__(self, config, client, parent=None):
        super().__init__(parent)
        self.config   = config
        self.client   = client
        self._fetched: dict | None = None
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        layout.addWidget(QLabel(
            "Paste a GitHub URL to a skill's SKILL.md file:",
            styleSheet=SECTION_STYLE,
        ))

        url_row = QHBoxLayout()
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText(
            "https://github.com/owner/repo/blob/main/skills/my-skill/SKILL.md"
        )
        self._url_edit.setStyleSheet(INPUT_STYLE)
        self._url_edit.returnPressed.connect(self._fetch)
        url_row.addWidget(self._url_edit, 1)

        fetch_btn = QPushButton("Fetch")
        fetch_btn.setStyleSheet(BTN_STYLE)
        fetch_btn.clicked.connect(self._fetch)
        url_row.addWidget(fetch_btn)
        layout.addLayout(url_row)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(STATUS_STYLE)
        layout.addWidget(self._status_label)

        layout.addWidget(QLabel("Preview:", styleSheet=SECTION_STYLE))
        self._preview = _make_preview()
        layout.addWidget(self._preview, 1)

        btn_row = QHBoxLayout()
        self._import_btn = QPushButton("Import")
        self._import_btn.setStyleSheet(BTN_STYLE)
        self._import_btn.setEnabled(False)
        self._import_btn.clicked.connect(self._import)
        btn_row.addWidget(self._import_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _fetch(self):
        url = self._url_edit.text().strip()
        if not url:
            return
        self._status_label.setText("Fetching…")
        self._fetched = None
        self._import_btn.setEnabled(False)
        self._preview.clear()

        self._worker = FetchUrlWorker(self.client, url)
        self._worker.finished.connect(self._on_fetched)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_fetched(self, result: dict):
        self._fetched = result
        self._preview.setPlainText(result.get("content", ""))
        self._status_label.setText(f"Fetched skill '{result.get('name', '?')}'")
        self._import_btn.setEnabled(True)

    def _on_error(self, msg: str):
        self._status_label.setText(f"Error: {msg}")

    def _import(self):
        if not self._fetched:
            return
        name = self._fetched.get("name") or "imported-skill"
        dialog = ImportDialog(self.config, name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        dest_dir, overwrite = dialog.get_result()
        if not dest_dir:
            return
        SkillIO().write_skill(dest_dir, name, self._fetched.get("content", ""))
        mw = self.window()
        if hasattr(mw, "set_status"):
            mw.set_status(f"Imported '{name}' to {dest_dir}")
        if hasattr(mw, "_refresh_skills_status"):
            mw._refresh_skills_status()
        self._import_btn.setEnabled(False)


# ── Main Search Tab ───────────────────────────────────────────────────────────

class SearchTab(QWidget):

    def __init__(self, config, db, parent=None):
        super().__init__(parent)
        self.config = config
        self.db     = db
        self._client = None
        self._build_ui()

    def _get_client(self):
        if self._client is None:
            from modules.github_client import GitHubClient
            self._client = GitHubClient(
                token=self.config.get("github.token", ""),
                timeout=self.config.get("github.search_timeout", 10),
                cache_hours=self.config.get("github.cache_hours", 24),
                db=self.db,
            )
        return self._client

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        client = self._get_client()

        self._sub = QTabWidget()
        self._sub.setDocumentMode(True)

        self._source_tab  = SourceReposTab(self.config, client, parent=self)
        self._search_tab  = GitHubSearchTab(self.config, client, self.db, parent=self)
        self._url_tab     = UrlImportTab(self.config, client, parent=self)

        self._sub.addTab(self._source_tab, "Source Repos")
        self._sub.addTab(self._search_tab, "GitHub Search")
        self._sub.addTab(self._url_tab,    "URL Import")

        layout.addWidget(self._sub)

    def refresh_client(self):
        """Call when token/settings change — forces client recreation."""
        self._client = None
        client = self._get_client()
        self._source_tab.client  = client
        self._search_tab.client  = client
        self._url_tab.client     = client

    def clear_cache(self):
        if self.db:
            self.db.cache_clear()
            self.db.search_results_clear()
        mw = self.window()
        if hasattr(mw, "set_status"):
            mw.set_status("GitHub cache cleared")
