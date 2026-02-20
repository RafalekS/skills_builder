"""
Main Window - Skills Builder application shell
"""

import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel,
    QMenuBar, QMenu, QMessageBox, QApplication
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

from modules.config_manager import ConfigManager
from modules.theme import (
    BG_DARK, BG_MEDIUM, BG_LIGHT,
    FG_PRIMARY, FG_SECONDARY, FG_DIM,
    ACCENT, ACCENT_GREEN, ACCENT_ORANGE, ERROR_RED, WARN_ORANGE,
)

logger = logging.getLogger(__name__)

# Re-export so existing code that did `from modules.main_window import BG_DARK` still works
__all__ = [
    "BG_DARK", "BG_MEDIUM", "BG_LIGHT",
    "FG_PRIMARY", "FG_SECONDARY", "FG_DIM",
    "ACCENT", "ACCENT_GREEN", "ACCENT_ORANGE", "ERROR_RED", "WARN_ORANGE",
    "APP_STYLESHEET", "MainWindow",
]

APP_STYLESHEET = f"""
QMainWindow, QDialog {{
    background-color: {BG_DARK};
    color: {FG_PRIMARY};
}}
QTabWidget::pane {{
    border: 1px solid {BG_LIGHT};
    background-color: {BG_DARK};
}}
QTabBar::tab {{
    background-color: {BG_MEDIUM};
    color: {FG_SECONDARY};
    padding: 8px 18px;
    border: 1px solid {BG_LIGHT};
    border-bottom: none;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {BG_DARK};
    color: {FG_PRIMARY};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    background-color: {BG_LIGHT};
    color: {FG_PRIMARY};
}}
QMenuBar {{
    background-color: {BG_MEDIUM};
    color: {FG_PRIMARY};
    border-bottom: 1px solid {BG_LIGHT};
}}
QMenuBar::item:selected {{
    background-color: {BG_LIGHT};
}}
QMenu {{
    background-color: {BG_MEDIUM};
    color: {FG_PRIMARY};
    border: 1px solid {BG_LIGHT};
}}
QMenu::item:selected {{
    background-color: {ACCENT};
    color: #ffffff;
}}
QStatusBar {{
    background-color: {BG_MEDIUM};
    color: {FG_SECONDARY};
    border-top: 1px solid {BG_LIGHT};
}}
QStatusBar QLabel {{
    padding: 0 8px;
    color: {FG_SECONDARY};
}}
"""


class MainWindow(QMainWindow):
    def __init__(self, config: ConfigManager, db=None):
        super().__init__()
        self.config = config
        self.db = db  # None until Phase 5

        self._build_window()
        self._build_menu()
        self._build_tabs()
        self._build_status_bar()
        self._restore_state()

        logger.info("MainWindow initialised")

    # ── Window setup ─────────────────────────────────────────────────────────

    def _build_window(self):
        from main import APP_NAME, APP_VERSION
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(900, 600)
        w = self.config.get("app.window_width", 1200)
        h = self.config.get("app.window_height", 800)
        self.resize(w, h)
        x = self.config.get("app.window_x", -1)
        y = self.config.get("app.window_y", -1)
        if x >= 0 and y >= 0:
            self.move(x, y)

    # ── Menu bar ─────────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu("File")
        self._add_action(file_menu, "New Skill",        "Ctrl+N", self._on_new_skill)
        self._add_action(file_menu, "Open Skill...",    "Ctrl+O", self._on_open_skill)
        file_menu.addSeparator()
        self._add_action(file_menu, "Save",             "Ctrl+S", self._on_save)
        self._add_action(file_menu, "Save As...",       "Ctrl+Shift+S", self._on_save_as)
        file_menu.addSeparator()
        self._add_action(file_menu, "Import ZIP...",    None, self._on_import_zip)
        self._add_action(file_menu, "Export ZIP...",    None, self._on_export_zip)
        file_menu.addSeparator()
        self._add_action(file_menu, "Exit",             "Ctrl+Q", self.close)

        # Tools
        tools_menu = menubar.addMenu("Tools")
        self._add_action(tools_menu, "Validate Skill",  "Ctrl+Shift+V", self._on_validate)
        tools_menu.addSeparator()
        self._add_action(tools_menu, "Clear GitHub Cache", None, self._on_clear_cache)
        self._add_action(tools_menu, "Open Skills Folder", None, self._on_open_skills_folder)
        self._add_action(tools_menu, "Refresh Library",    "F5",  self._on_refresh_library)

        # Help
        help_menu = menubar.addMenu("Help")
        self._add_action(help_menu, "About",            None, self._on_about)
        self._add_action(help_menu, "Skills Specification", None, self._on_open_spec)

    @staticmethod
    def _add_action(menu: QMenu, text: str, shortcut: str | None, slot) -> QAction:
        action = QAction(text)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    # ── Tabs ─────────────────────────────────────────────────────────────────

    def _build_tabs(self):
        # Deferred imports break the circular dependency
        from modules.editor_tab   import EditorTab
        from modules.library_tab  import LibraryTab
        from modules.search_tab   import SearchTab
        from modules.settings_tab import SettingsTab

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.editor_tab   = EditorTab(self.config, parent=self)
        self.library_tab  = LibraryTab(self.config, parent=self)
        self.search_tab   = SearchTab(self.config, self.db, parent=self)
        self.settings_tab = SettingsTab(self.config, parent=self)

        self.tabs.addTab(self.editor_tab,   "Editor")
        self.tabs.addTab(self.library_tab,  "Library")
        self.tabs.addTab(self.search_tab,   "Search")
        self.tabs.addTab(self.settings_tab, "Settings")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)

    # ── Status bar ───────────────────────────────────────────────────────────

    def _build_status_bar(self):
        sb = self.statusBar()

        self.status_message = QLabel("Ready")
        self.status_api     = QLabel("API: --")
        self.status_skills  = QLabel("")

        sb.addWidget(self.status_message, 1)         # left, stretching
        sb.addPermanentWidget(self._vsep())
        sb.addPermanentWidget(self.status_api)       # centre-right, permanent
        sb.addPermanentWidget(self._vsep())
        sb.addPermanentWidget(self.status_skills)    # right, permanent

        self._refresh_skills_status()

    @staticmethod
    def _vsep() -> QLabel:
        sep = QLabel("|")
        sep.setStyleSheet(f"color: {BG_LIGHT}; padding: 0 2px;")
        return sep

    def _refresh_skills_status(self):
        skills_dir = self.config.get_user_skills_dir()
        count = 0
        if skills_dir.exists():
            count = sum(
                1 for d in skills_dir.iterdir()
                if d.is_dir() and (d / "SKILL.md").exists()
            )
        display = str(skills_dir).replace(str(Path.home()), "~")
        self.status_skills.setText(f"{display} ({count} skills)")

    def set_status(self, message: str, timeout_ms: int = 3000):
        """Show a transient status message."""
        self.status_message.setText(message)
        if timeout_ms > 0:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(timeout_ms, lambda: self.status_message.setText("Ready"))

    def set_api_status(self, text: str):
        self.status_api.setText(text)

    # ── State save/restore ───────────────────────────────────────────────────

    def _restore_state(self):
        last_tab = self.config.get("app.last_tab", 0)
        if 0 <= last_tab < self.tabs.count():
            self.tabs.setCurrentIndex(last_tab)

    def _save_state(self):
        geo = self.geometry()
        self.config.set("app.window_width",  geo.width())
        self.config.set("app.window_height", geo.height())
        self.config.set("app.window_x",      geo.x())
        self.config.set("app.window_y",      geo.y())
        self.config.set("app.last_tab",      self.tabs.currentIndex())
        self.config.save()

    def closeEvent(self, event):
        self._save_state()
        logger.info("Application closing")
        event.accept()

    # ── Tab event ────────────────────────────────────────────────────────────

    def _on_tab_changed(self, index: int):
        self._refresh_skills_status()

    # ── Menu handlers (stubs — filled in later phases) ───────────────────────

    def _on_new_skill(self):
        self.tabs.setCurrentWidget(self.editor_tab)
        self.editor_tab.action_new()

    def _on_open_skill(self):
        self.tabs.setCurrentWidget(self.editor_tab)
        self.editor_tab._open_skill()

    def _on_save(self):
        self.tabs.setCurrentWidget(self.editor_tab)
        self.editor_tab.action_save()

    def _on_save_as(self):
        self.tabs.setCurrentWidget(self.editor_tab)
        self.editor_tab.action_save_as()

    def _on_import_zip(self):
        self.tabs.setCurrentWidget(self.library_tab)
        self.library_tab._user_tab._import_zip()

    def _on_export_zip(self):
        self.tabs.setCurrentWidget(self.library_tab)
        self.library_tab._user_tab._export_zip()

    def _on_validate(self):
        self.tabs.setCurrentWidget(self.editor_tab)
        self.editor_tab._run_validation()

    def _on_clear_cache(self):
        if hasattr(self, "search_tab"):
            self.search_tab.clear_cache()

    def _on_open_skills_folder(self):
        import subprocess
        import platform
        skills_dir = self.config.get_user_skills_dir()
        skills_dir.mkdir(parents=True, exist_ok=True)
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(["explorer", str(skills_dir)], encoding="utf-8", errors="replace")
        elif system == "Darwin":
            subprocess.Popen(["open", str(skills_dir)])
        else:
            subprocess.Popen(["xdg-open", str(skills_dir)])
        self.set_status(f"Opened {skills_dir}")

    def _on_refresh_library(self):
        if hasattr(self, "library_tab"):
            self.library_tab.refresh()
        self._refresh_skills_status()
        self.set_status("Library refreshed")

    def _on_about(self):
        from main import APP_NAME, APP_VERSION
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<b>{APP_NAME}</b> v{APP_VERSION}<br><br>"
            "Visual editor and manager for Claude Code Skills.<br><br>"
            "Create, browse, search, and import SKILL.md files.<br><br>"
            "<a href='https://agentskills.io/specification'>Skills Specification</a>"
        )

    def _on_open_spec(self):
        import webbrowser
        webbrowser.open("https://agentskills.io/specification")
