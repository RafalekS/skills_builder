"""
Skills Builder - Visual editor and manager for Claude Code Skills
"""

import logging
import sys
import traceback
from pathlib import Path

# ── App identity ──────────────────────────────────────────────────────────────
APP_NAME    = "Skills Builder"
APP_VERSION = "0.1.0"

# ── Logging setup (before any Qt import) ─────────────────────────────────────
def _setup_logging():
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "skills_builder.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

_setup_logging()
logger = logging.getLogger(__name__)

# ── Qt imports ────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

from modules.config_manager import ConfigManager
from modules.main_window import MainWindow


# ── Dark theme ────────────────────────────────────────────────────────────────
def _apply_dark_theme(app: QApplication):
    app.setStyle("Fusion")
    palette = QPalette()

    dark   = QColor("#1e1e1e")
    medium = QColor("#252526")
    light  = QColor("#2d2d30")
    text   = QColor("#d4d4d4")
    dim    = QColor("#9d9d9d")
    accent = QColor("#569cd6")
    white  = QColor("#ffffff")
    error  = QColor("#f44747")

    palette.setColor(QPalette.ColorRole.Window,          dark)
    palette.setColor(QPalette.ColorRole.WindowText,      text)
    palette.setColor(QPalette.ColorRole.Base,            medium)
    palette.setColor(QPalette.ColorRole.AlternateBase,   light)
    palette.setColor(QPalette.ColorRole.Text,            text)
    palette.setColor(QPalette.ColorRole.BrightText,      white)
    palette.setColor(QPalette.ColorRole.Button,          medium)
    palette.setColor(QPalette.ColorRole.ButtonText,      text)
    palette.setColor(QPalette.ColorRole.Highlight,       accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, white)
    palette.setColor(QPalette.ColorRole.Link,            accent)
    palette.setColor(QPalette.ColorRole.ToolTipBase,     light)
    palette.setColor(QPalette.ColorRole.ToolTipText,     text)
    palette.setColor(QPalette.ColorRole.PlaceholderText, dim)

    # Disabled colours
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       dim)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, dim)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, dim)

    app.setPalette(palette)

    from modules.main_window import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)


# ── Unhandled exception hook ──────────────────────────────────────────────────
def _handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )
    # Try to show an error dialog if QApplication is running
    app = QApplication.instance()
    if app:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Unhandled Error")
        msg.setText(f"An unexpected error occurred:\n\n{exc_type.__name__}: {exc_value}")
        msg.setDetailedText("".join(traceback.format_tb(exc_traceback)))
        msg.exec()

sys.excepthook = _handle_exception


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    _apply_dark_theme(app)

    icon_path = Path(__file__).parent / "resources" / "skills_builder.png"
    if icon_path.exists():
        from PyQt6.QtGui import QIcon
        app.setWindowIcon(QIcon(str(icon_path)))

    config = ConfigManager()
    window = MainWindow(config)
    window.show()

    logger.info("%s v%s started", APP_NAME, APP_VERSION)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
