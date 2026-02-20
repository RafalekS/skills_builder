"""
Syntax Highlighter - QSyntaxHighlighter for SKILL.md (YAML frontmatter + Markdown body)
"""

import re
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt6.QtCore import Qt

# ── Colour palette ────────────────────────────────────────────────────────────
_C = {
    "delimiter":   "#569cd6",   # --- lines
    "fm_key":      "#9cdcfe",   # YAML keys
    "fm_value":    "#ce9178",   # YAML values
    "fm_comment":  "#6a9955",   # # comments in YAML
    "md_h1":       "#4ec9b0",   # # heading
    "md_h2":       "#4ec9b0",   # ## heading
    "md_h3":       "#9cdcfe",   # ### heading
    "md_code_bg":  "#2d2d30",   # inline code background
    "md_code_fg":  "#ce9178",   # inline code text
    "md_bold":     "#dcdcaa",   # **bold**
    "md_italic":   "#c586c0",   # *italic*
    "md_link":     "#569cd6",   # [text](url)
    "md_bullet":   "#569cd6",   # list markers
    "md_fence":    "#2d2d30",   # fenced code block bg
    "md_fence_fg": "#d4d4d4",   # fenced code block text
    "md_hr":       "#5a5a5a",   # --- horizontal rule (in body)
}

STATE_BODY        = 0
STATE_FRONTMATTER = 1
STATE_FENCED_CODE = 2   # ``` code block in markdown body


def _fmt(fg=None, bg=None, bold=False, italic=False) -> QTextCharFormat:
    f = QTextCharFormat()
    if fg:
        f.setForeground(QColor(fg))
    if bg:
        f.setBackground(QColor(bg))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f


class SkillHighlighter(QSyntaxHighlighter):

    def __init__(self, document):
        super().__init__(document)
        self._build_formats()
        self._build_patterns()

    def _build_formats(self):
        self.fmt = {
            "delimiter":  _fmt(_C["delimiter"],  bold=True),
            "fm_key":     _fmt(_C["fm_key"]),
            "fm_value":   _fmt(_C["fm_value"]),
            "fm_comment": _fmt(_C["fm_comment"], italic=True),
            "md_h1":      _fmt(_C["md_h1"],      bold=True),
            "md_h2":      _fmt(_C["md_h2"],      bold=True),
            "md_h3":      _fmt(_C["md_h3"],      bold=True),
            "md_bold":    _fmt(_C["md_bold"],     bold=True),
            "md_italic":  _fmt(_C["md_italic"],   italic=True),
            "md_link":    _fmt(_C["md_link"]),
            "md_bullet":  _fmt(_C["md_bullet"],   bold=True),
            "md_code":    _fmt(_C["md_code_fg"],  bg=_C["md_code_bg"]),
            "md_fence_fg":_fmt(_C["md_fence_fg"], bg=_C["md_fence"]),
            "md_hr":      _fmt(_C["md_hr"]),
        }

    def _build_patterns(self):
        # (regex, format_key)
        self.md_patterns = [
            (re.compile(r'^#{3}\s.*$'),            "md_h3"),
            (re.compile(r'^#{2}\s.*$'),            "md_h2"),
            (re.compile(r'^#\s.*$'),               "md_h1"),
            (re.compile(r'\*\*[^*]+\*\*'),         "md_bold"),
            (re.compile(r'\*[^*\s][^*]*\*'),       "md_italic"),
            (re.compile(r'\[.*?\]\(.*?\)'),         "md_link"),
            (re.compile(r'`[^`]+`'),               "md_code"),
            (re.compile(r'^[-*+]\s'),              "md_bullet"),
            (re.compile(r'^\d+\.\s'),              "md_bullet"),
            (re.compile(r'^---+$|^\*\*\*+$'),      "md_hr"),
        ]
        self.fm_key_re    = re.compile(r'^(\s*[\w-]+)\s*:')
        self.fm_value_re  = re.compile(r':\s*(.+)$')
        self.fm_comment_re = re.compile(r'#.*$')

    # ── Core ──────────────────────────────────────────────────────────────────

    def highlightBlock(self, text: str):
        prev = self.previousBlockState()

        # --- delimiter line
        if text.strip() == "---":
            if prev == STATE_FRONTMATTER:
                self.setCurrentBlockState(STATE_BODY)
            else:
                self.setCurrentBlockState(STATE_FRONTMATTER)
            self.setFormat(0, len(text), self.fmt["delimiter"])
            return

        if prev == STATE_FRONTMATTER:
            self.setCurrentBlockState(STATE_FRONTMATTER)
            self._highlight_yaml(text)
            return

        # Fenced code block handling (``` ... ```)
        if prev == STATE_FENCED_CODE:
            if text.strip().startswith("```"):
                self.setCurrentBlockState(STATE_BODY)
                self.setFormat(0, len(text), self.fmt["md_fence_fg"])
            else:
                self.setCurrentBlockState(STATE_FENCED_CODE)
                self.setFormat(0, len(text), self.fmt["md_fence_fg"])
            return

        if text.strip().startswith("```"):
            self.setCurrentBlockState(STATE_FENCED_CODE)
            self.setFormat(0, len(text), self.fmt["md_fence_fg"])
            return

        self.setCurrentBlockState(STATE_BODY)
        self._highlight_markdown(text)

    def _highlight_yaml(self, text: str):
        # Whole-line comment
        if text.strip().startswith("#"):
            self.setFormat(0, len(text), self.fmt["fm_comment"])
            return
        # key: value
        m = self.fm_key_re.match(text)
        if m:
            self.setFormat(m.start(1), m.end(1) - m.start(1), self.fmt["fm_key"])
            colon_pos = m.end(1)
            val_m = self.fm_value_re.search(text)
            if val_m:
                self.setFormat(val_m.start(1), len(text) - val_m.start(1), self.fmt["fm_value"])
        else:
            # continuation / list item value
            if text.strip():
                self.setFormat(0, len(text), self.fmt["fm_value"])

    def _highlight_markdown(self, text: str):
        for pattern, fmt_key in self.md_patterns:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), self.fmt[fmt_key])
