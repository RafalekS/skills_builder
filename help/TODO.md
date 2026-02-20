# Skills Builder — TODO

## Status: Planning Phase

---

## Phase 1: Project Skeleton [PENDING]
- [ ] `main.py` — QApplication, dark theme, empty MainWindow
- [ ] `modules/main_window.py` — 4 tabs, menu bar, status bar
- [ ] `modules/config_manager.py` — JSON config with dot-notation
- [ ] `requirements.txt` — PyQt6, requests, PyYAML
- [ ] `config/config.json` — default config
- [ ] `config/sources.json` — pre-populated skill source repos

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
