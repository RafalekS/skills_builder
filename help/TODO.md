# Skills Builder — TODO

## Status: Planning Phase

---

## Phase 1: Project Skeleton [BUILT — NEEDS USER TEST]
- [x] `main.py` — QApplication, dark theme, empty MainWindow, unhandled exception hook
- [x] `modules/main_window.py` — 4 tabs, menu bar, status bar (3 segments), colour constants
- [x] `modules/config_manager.py` — JSON config with dot-notation, deep merge with defaults
- [x] `requirements.txt` — PyQt6, requests, PyYAML
- [x] `config/config.json` — default config
- [x] `config/sources.json` — 8 pre-populated skill source repos
- [x] Stub tabs: editor, library, search, settings
- [ ] **USER: run `python main.py` — verify window opens, tabs visible, status bar shows skills dir**

## Phase 2: Core Logic [PENDING]
- [ ] `modules/validator.py` — frontmatter validation rules
- [ ] `modules/skill_io.py` — read/write/list/export/import skill dirs
- [ ] `modules/syntax_highlighter.py` — QSyntaxHighlighter for YAML+Markdown

## Phase 3: Editor Tab [PENDING]
- [ ] `modules/editor_tab.py` — form panel + raw editor + highlighter
- [ ] Template gallery (built-in templates as embedded strings)
- [ ] Live validation display
- [ ] Save / Save As / Backup & Save / Revert

## Phase 4: Library Tab [PENDING]
- [ ] `modules/library_tab.py` — user + project sub-tabs
- [ ] CRUD + export/import + open-in-editor

## Phase 5: GitHub Search [PENDING]
- [ ] `modules/database.py` — SQLite with cache schema
- [ ] `modules/github_client.py` — API wrapper, rate limit aware, caching
- [ ] `modules/search_tab.py` — 3 sub-tabs + import dialog
- [ ] Rate limit display in status bar

## Phase 6: Settings [PENDING]
- [ ] `modules/settings_tab.py` — paths, GitHub, editor, sources, about

## Phase 7: Polish [PENDING]
- [ ] State persistence (window size, tab, column widths)
- [ ] Error handling review
- [ ] Logging to file
- [ ] Cross-platform path testing
- [ ] Export ZIP for claude.ai upload

---

## Decisions Needed
- None currently

## Issues
- None yet

## Mistakes / Lessons
- None yet
