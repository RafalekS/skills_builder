# Skills Builder — Claude Code Project Specification

**Project Name:** Skills Builder
**Type:** Standalone PyQt6 GUI Desktop Application
**Purpose:** Visual editor and manager for Claude Code Skills (SKILL.md files), with GitHub search, import, and deploy capabilities.
**Author:** Rafal Staska
**Version:** Track in `main.py` as `APP_VERSION = "0.1.0"` — increment on every meaningful change.
**Target Platforms:** Windows 11 (primary), Linux (secondary)
**Coding Standards:** Follow `coding` skill standards at `~/.claude/skills/coding/SKILL.md`

---

## Context: What Are Claude Skills?

Claude Skills are modular, filesystem-based capabilities that extend Claude's behaviour. Each skill is a **directory** containing a `SKILL.md` file (required) and optional supporting files. Skills use a **progressive disclosure** architecture:

| Level | Content | When Loaded | Cost |
|-------|---------|-------------|------|
| Level 1: Metadata | YAML frontmatter (`name` + `description`) | Always, at startup | ~100 tokens per skill |
| Level 2: Instructions | SKILL.md body (Markdown) | When skill triggers | < 5,000 tokens |
| Level 3: Resources | `scripts/`, `references/`, `assets/` | On demand | Unlimited (not in context until accessed) |

### SKILL.md File Format

```
skill-name/
├── SKILL.md          ← Required
├── scripts/          ← Optional: Python/Bash/JS scripts Claude can run
├── references/       ← Optional: Additional .md reference docs
└── assets/           ← Optional: Templates, images, data files
```

SKILL.md structure:
```
---
name: skill-name
description: What this skill does and when Claude should use it.
license: MIT
compatibility: Designed for Claude Code
metadata:
  author: your-name
  version: "1.0"
allowed-tools: Read Bash(git:*) Grep
---

# Skill Title

## Instructions
...

## Examples
...
```

### Frontmatter Field Constraints

| Field | Required | Rules |
|-------|----------|-------|
| `name` | Yes | 1-64 chars. Only `a-z`, `0-9`, `-`. No `--`. No leading/trailing `-`. Must match parent directory name. No "anthropic" or "claude". |
| `description` | Yes | 1-1024 chars. Non-empty. Must describe WHAT it does AND WHEN to use it. |
| `license` | No | License name or reference to bundled LICENSE file. |
| `compatibility` | No | 1-500 chars. Environment requirements. Most skills don't need this. |
| `metadata` | No | Arbitrary key-value string map. |
| `allowed-tools` | No | Space-delimited list. Experimental. Example: `Read Bash(git:*) Grep Glob` |

### Where Skills Live (Claude Code)

- **User scope:** `~/.claude/skills/skill-name/SKILL.md` — personal, all projects
- **Project scope:** `./.claude/skills/skill-name/SKILL.md` — project-specific, git-shareable

On **Windows**: `~` expands to `C:\Users\<username>` (use `pathlib.Path.home()` — NEVER hardcode, NEVER use literal `~` in Python file ops).

---

## Purpose of This Application

**Skills Builder** solves the problem of creating, managing, discovering, and deploying Claude Skills. Users currently have to manually write SKILL.md files, hunt GitHub repos for community skills, and manually copy files to the right directories.

Skills Builder provides:
1. A **visual editor** — create skills with form-based frontmatter + syntax-highlighted Markdown body
2. A **local library** — browse, edit, delete, and export skills from user and project scopes
3. A **GitHub searcher** — search curated community repos and import skills with one click
4. A **validator** — real-time frontmatter validation with clear error messages
5. **Export/Import** — ZIP export for claude.ai upload, import from ZIP or directory

---

## Application Architecture

### Platform Detection

```python
import platform, pathlib, os

def is_windows() -> bool:
    return platform.system() == 'Windows'

def get_user_skills_dir() -> pathlib.Path:
    return pathlib.Path.home() / '.claude' / 'skills'

def get_config_dir() -> pathlib.Path:
    """App config stored alongside the executable"""
    return pathlib.Path(__file__).parent / 'config'
```

**CRITICAL:** Always use `pathlib.Path.home()` (not `~`). Always `expanduser()` on any path from config. NEVER hardcode any path.

### Technology Stack

- **Python 3.11+**
- **PyQt6** — GUI framework
- **QSyntaxHighlighter** — syntax highlighting for SKILL.md editor
- **requests** — GitHub API calls (with timeout, error handling)
- **SQLite** (stdlib `sqlite3`) — cache GitHub search results and skill library index
- **pathlib** — all file path operations (cross-platform)
- **yaml** (PyYAML) — parse/write SKILL.md frontmatter
- **zipfile** (stdlib) — export/import skill ZIPs

---

## File Structure

```
skills_builder/
├── CLAUDE.md               ← This file
├── main.py                 ← Entry point, APP_VERSION, QApplication setup
├── requirements.txt        ← PyQt6, requests, PyYAML
├── help/
│   ├── PROMPT.md           ← Original requirements (do not modify)
│   └── TODO.md             ← Task tracker (keep updated)
├── config/
│   ├── config.json         ← User preferences (auto-created on first run)
│   └── sources.json        ← GitHub skill source repos (editable via settings)
├── modules/
│   ├── main_window.py      ← MainWindow class, tab setup, status bar
│   ├── config_manager.py   ← JSON config load/save with dot-notation
│   ├── database.py         ← SQLite: search cache, skill index
│   ├── editor_tab.py       ← Skill creator/editor tab (main feature)
│   ├── library_tab.py      ← Local skill library browser
│   ├── search_tab.py       ← GitHub search + import
│   ├── settings_tab.py     ← App settings
│   ├── validator.py        ← SKILL.md frontmatter validator (pure logic)
│   ├── skill_io.py         ← File I/O: read/write/delete skill dirs
│   ├── github_client.py    ← GitHub API wrapper (rate limit aware)
│   └── syntax_highlighter.py ← QSyntaxHighlighter for YAML + Markdown
├── backup/                 ← Auto-backups of edited skills
└── logs/                   ← Application logs (skills_builder.log)
```

---

## Module Specifications

### `main.py`
Entry point. Sets up `QApplication`, applies theme, creates `MainWindow`, shows it.
```python
APP_VERSION = "0.1.0"
APP_NAME = "Skills Builder"
```
- `QApplication` with Fusion style
- Dark theme via stylesheet (see Coding Standards)
- Catch unhandled exceptions → log to file + show error dialog (do NOT silently swallow)
- Window title: `f"{APP_NAME} v{APP_VERSION}"`

---

### `modules/config_manager.py`
Simple JSON config with dot-notation get/set. Creates config file with defaults on first run.

**Default config structure:**
```json
{
  "app": {
    "theme": "dark",
    "window_width": 1200,
    "window_height": 800,
    "last_project_dir": ""
  },
  "skills": {
    "user_skills_dir": "",
    "project_skills_dir": ""
  },
  "github": {
    "token": "",
    "search_timeout": 10,
    "cache_hours": 24
  },
  "editor": {
    "font_family": "Consolas",
    "font_size": 13,
    "tab_width": 2,
    "wrap_lines": true
  }
}
```

`user_skills_dir` empty string → auto-detect: `Path.home() / '.claude' / 'skills'`
`project_skills_dir` empty string → no project scope shown

Methods:
- `get(key, default=None)` — dot-notation: `config.get("github.token")`
- `set(key, value)` — dot-notation set, creates nested dicts
- `load()` → bool
- `save()` → bool

---

### `modules/validator.py`
Pure logic module. No Qt imports. Validates a skill's frontmatter dict and name.

```python
class ValidationResult:
    valid: bool
    errors: list[str]   # blocking errors
    warnings: list[str] # non-blocking warnings

class SkillValidator:
    def validate_name(self, name: str) -> ValidationResult
    def validate_description(self, description: str) -> ValidationResult
    def validate_frontmatter(self, frontmatter: dict) -> ValidationResult
    def validate_skill_dir(self, skill_dir: Path) -> ValidationResult
    def parse_frontmatter(self, skill_md_content: str) -> dict | None
```

**Name validation rules:**
- 1-64 chars
- Only `[a-z0-9-]`
- No leading/trailing `-`
- No `--`
- No "anthropic" or "claude" as part of name
- Must not be empty

**Description validation rules:**
- 1-1024 chars
- Non-empty
- Warn if < 50 chars (probably too vague)
- Warn if doesn't contain "use when" or similar trigger phrase

**allowed-tools validation:**
- Split on spaces
- Each must be one of the known tools or a `Bash(*)` pattern
- Known tools: `Read Write Edit MultiEdit Grep Glob Bash WebFetch WebSearch Task TodoWrite NotebookEdit AskUserQuestion Skill`

---

### `modules/skill_io.py`
File I/O for skills. All paths via `pathlib.Path`. All file ops with UTF-8 encoding.

```python
class SkillIO:
    def list_skills(self, skills_dir: Path) -> list[dict]
        # Returns: [{"name": str, "path": Path, "description": str, "has_scripts": bool, ...}]

    def read_skill(self, skill_dir: Path) -> dict
        # Returns: {"frontmatter": dict, "body": str, "full_content": str, "files": list}

    def write_skill(self, skills_dir: Path, name: str, content: str) -> Path
        # Creates skill_dir/name/SKILL.md, returns path

    def delete_skill(self, skill_dir: Path) -> bool

    def export_zip(self, skill_dirs: list[Path], zip_path: Path) -> bool
        # ZIP structure: skill-name/SKILL.md (+ any bundled files)

    def import_zip(self, zip_path: Path, target_dir: Path) -> list[str]
        # Returns list of imported skill names

    def import_from_dir(self, source_dir: Path, target_dir: Path) -> bool
        # Copies a skill directory
```

---

### `modules/github_client.py`
GitHub API wrapper. Uses `requests`. Rate limit aware. Caches responses in SQLite.

```python
class GitHubClient:
    def __init__(self, token: str = "", timeout: int = 10, cache_hours: int = 24)

    def get_rate_limit(self) -> dict
        # Returns: {"remaining": int, "reset_at": datetime, "limit": int}

    def fetch_skill_from_repo(self, owner: str, repo: str, skill_path: str) -> dict | None
        # Returns: {"name": str, "description": str, "content": str, "url": str, "stars": int}

    def list_skills_in_repo(self, owner: str, repo: str, skills_prefix: str = "skills/") -> list[dict]
        # Scans repo for directories containing SKILL.md

    def search_github(self, query: str) -> list[dict]
        # GitHub code search: filename:SKILL.md + user query

    def get_readme(self, owner: str, repo: str) -> str
        # Fetches README.md content

    def extract_skill_repos_from_readme(self, readme_content: str) -> list[str]
        # Parses markdown links, extracts GitHub repo URLs that likely contain skills
```

**Auth header:** `{"Authorization": f"token {token}"}` if token set, else anonymous (60 req/hr limit)

**Cache:** Store responses in SQLite `github_cache` table with `url`, `content`, `fetched_at`. Expire after `cache_hours`.

**Rate limit display:** Show `{remaining}/{limit} API calls remaining, resets {time}` in status bar.

---

### `modules/database.py`
SQLite database. Stored at `config/skills_builder.db`.

```python
class Database:
    def __init__(self, db_path: Path)
    def init_schema(self)

# Tables:
# github_cache: (url TEXT PK, content TEXT, fetched_at TIMESTAMP)
# search_results: (id, query, owner, repo, skill_name, description, url, stars, cached_at)
# skill_index: (id, name, description, scope TEXT, path TEXT, last_modified)
```

Methods for each table: `get`, `set`, `delete`, `clear_expired`, `search`.

---

### `modules/syntax_highlighter.py`
`QSyntaxHighlighter` subclass for SKILL.md files. Highlights:

**YAML Frontmatter (between `---` delimiters):**
- `---` delimiter lines → bold accent colour
- Keys (`name:`, `description:`, etc.) → primary accent
- Values → secondary colour
- Comments (`#`) → muted/dim colour

**Markdown Body:**
- `# ## ###` headings → bright accent, bold
- `` `code` `` and ```` ```code blocks``` ```` → highlight background
- `**bold**` `*italic*` → respective formatting
- URLs `[text](url)` → blue/link colour
- List markers `- * +` → accent dot colour

```python
class SkillHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument)
    def highlightBlock(self, text: str)
```

Use format objects: `QTextCharFormat` with `setForeground()`, `setFontWeight()`, `setBackground()`.
Track frontmatter state across lines using `setCurrentBlockState()` / `previousBlockState()`.

---

### `modules/editor_tab.py`
The primary tab. Split-panel layout: **Form panel** (left) + **Raw editor** (right) with toggle.

**Left panel — Frontmatter form:**
- `name` — QLineEdit with live validation indicator (green/red border)
- `description` — QTextEdit (3-4 rows) with char counter `(42/1024)`
- `license` — QLineEdit, optional
- `compatibility` — QLineEdit, optional
- `metadata` — key-value table (QTableWidget, 2 cols: Key, Value). Add/remove rows.
- `allowed-tools` — Checkboxes grid (all known tools). Read, Grep, Glob default-checked.
- **Validation summary** — QLabel area showing errors/warnings in red/orange
- **Buttons:** New | Save | Save As | Backup & Save | Revert | Export ZIP

**Right panel — Raw SKILL.md editor:**
- QTextEdit with monospace font
- `SkillHighlighter` applied
- Toggle button: "Form View ↔ Raw View" — syncs form↔editor bidirectionally
- Line/column indicator in panel footer
- Word wrap toggle

**Bottom panel — Preview (collapsible):**
- Shows rendered preview of the SKILL.md body (use QTextEdit in read-only mode with markdown — Qt supports basic markdown via `setMarkdown()`)
- Toggle show/hide

**Template Gallery** (toolbar button opens dialog):
- Pre-loaded templates: blank, minimal, with-scripts, with-references, web-scraping, code-review, documentation, etc.
- Each template is a starting SKILL.md content string stored in code (not external files)
- User can add custom templates
- Double-click to load into editor

**Sync logic:**
- When form changes → regenerate SKILL.md frontmatter section, keep body unchanged
- When raw editor changes (after 800ms debounce) → parse frontmatter, update form fields
- Do NOT fight the user — if raw edit produces unparseable frontmatter, show warning but don't revert

**File operations:**
- Save → write to `self.current_skill_path` (or prompt if None)
- Save As → ask for skills dir + name, validate name, create dir + SKILL.md
- Backup → copy to `backup/skill-name-YYYYMMDD-HHMMSS.md` before saving

---

### `modules/library_tab.py`
Browses skills on disk. Two sub-tabs: **User Skills** | **Project Skills**

**Layout (per sub-tab):**
- Path label: `~/.claude/skills/` + change button
- Search/filter QLineEdit
- QTableWidget: columns `Name | Description | Tools | Files | Modified`
  - All columns resizable (NO `setStretchLastSection`)
  - Sortable headers
  - Hide vertical header (row numbers)
- Action buttons: `New | Edit | Delete | Duplicate | Export ZIP | Refresh`
- Bottom panel: preview of selected skill's SKILL.md content (read-only, monospace)

**Behaviours:**
- Double-click row → open in Editor tab
- Delete → confirm dialog → `shutil.rmtree`
- Duplicate → copy dir, append `-copy`, open in editor
- Export ZIP → `skill_io.export_zip()` → file save dialog
- `Refresh` → re-scan directory
- "Open Folder" button → `subprocess` to open file manager at skills dir (cross-platform)

**Import section (toolbar):**
- `Import from ZIP` → file dialog → `skill_io.import_zip()`
- `Import from Directory` → folder dialog → `skill_io.import_from_dir()`

---

### `modules/search_tab.py`
GitHub search and import. Three modes accessible via QTabWidget sub-tabs:

#### Sub-tab 1: Source Repos
Browse skills from curated source repos. Pre-configured list in `config/sources.json`.

Pre-populated sources (stored in `config/sources.json`):
```json
[
  {
    "owner": "anthropics", "repo": "skills",
    "description": "Official Anthropic example skills (16 skills: docx, pdf, pptx, xlsx, algorithmic-art, canvas-design, frontend-design, mcp-builder, skill-creator, webapp-testing, etc.)",
    "skills_prefix": "skills/", "type": "direct"
  },
  {
    "owner": "VoltAgent", "repo": "awesome-agent-skills",
    "description": "383+ skills from official engineering teams: Vercel, Cloudflare, Stripe, Supabase, Google, Microsoft, Hugging Face, Trail of Bits, Expo, Sentry, Anthropic, etc.",
    "skills_prefix": null, "type": "awesome"
  },
  {
    "owner": "travisvn", "repo": "awesome-claude-skills",
    "description": "Curated community skills list with architecture docs and comparison tables",
    "skills_prefix": null, "type": "awesome"
  },
  {
    "owner": "ComposioHQ", "repo": "awesome-claude-skills",
    "description": "78 SaaS app integrations (Salesforce, Jira, Slack, GitHub, Stripe, etc.) + curated community skills",
    "skills_prefix": null, "type": "awesome"
  },
  {
    "owner": "hesreallyhim", "repo": "awesome-claude-code",
    "description": "Broader Claude Code ecosystem: skills, hooks, slash commands, orchestrators, tooling",
    "skills_prefix": null, "type": "awesome"
  },
  {
    "owner": "BehiSecc", "repo": "awesome-claude-skills",
    "description": "Community skills with scientific, security, and health domains",
    "skills_prefix": null, "type": "awesome"
  },
  {
    "owner": "obra", "repo": "superpowers-skills",
    "description": "20+ battle-tested skills: TDD, debugging, code review, git worktrees, systematic root-cause tracing",
    "skills_prefix": "skills/", "type": "direct"
  },
  {
    "owner": "trailofbits", "repo": "skills",
    "description": "22 professional security skills: CodeQL, Semgrep, variant analysis, code auditing, vulnerability detection",
    "skills_prefix": "skills/", "type": "direct"
  }
]
```

**Source `type` field:**
- `"direct"` — repo directly contains skill directories with SKILL.md files. Scan `skills_prefix` path.
- `"awesome"` — repo contains a README that links to external skill repos. Parse README → extract linked GitHub repos → offer as expandable tree in UI.

Layout:
- Left: source repos list (QListWidget) with Add/Remove buttons
- Right: skills found in selected repo (QTableWidget: Name | Description | Stars | Repo)
- Bottom: SKILL.md preview for selected skill
- `Import` button → imports selected skill to user or project scope
- `Fetch` button → re-fetches repo contents (clears cache for this repo)
- Rate limit indicator: `API: 58/60 remaining` (in status bar)

**"awesome-" repo handling:** For repos like `travisvn/awesome-claude-skills` that contain README linking to external skill repos rather than skill dirs, parse the README to extract linked GitHub repos, then offer them in an expandable tree.

#### Sub-tab 2: GitHub Search
Direct GitHub code search.
- Query field: `QLineEdit` with placeholder `"Search for skills by keyword..."`
- Filters: scope (all/specific repo), min stars
- Results: QTableWidget (Name | Repo | Description | Stars | URL)
- Preview panel below
- Import button
- `Note:` GitHub code search requires auth for high volume. Show unauthenticated rate limit warning if no token configured.

#### Sub-tab 3: URL Import
Direct URL input for importing a single skill:
- URL field (GitHub repo URL or raw SKILL.md URL)
- `Fetch` button → detect URL type, fetch content
- Preview panel
- Import button

**Import dialog** (shared by all sub-tabs):
- Destination: dropdown `User skills (~/.claude/skills)` | `Project skills (./.claude/skills)` | `Custom...`
- Conflict handling: `Skip | Overwrite | Rename`
- Preview of what will be imported
- `Import` button

---

### `modules/settings_tab.py`
Configuration UI. All settings read from / written to `config_manager`.

Sections:
1. **Paths**
   - User skills directory (with Browse + Reset to default button)
   - Project skills directory (with Browse + Clear button)
   - Verify both dirs: show `✓ exists` or `⚠ not found. Create?`

2. **GitHub**
   - Personal access token (QLineEdit with show/hide toggle — eye button)
   - Test button → fetch rate limit → show `Authenticated: 5000/hr` or `Anonymous: 60/hr`
   - Search timeout (seconds, QSpinBox)
   - Cache duration (hours, QSpinBox)
   - Clear cache button

3. **Editor**
   - Font family (QComboBox with monospace fonts)
   - Font size (QSpinBox)
   - Tab width (QSpinBox)
   - Word wrap (QCheckBox)

4. **Search Sources**
   - Editable table of source repos (owner, repo, description, skills_prefix)
   - Add / Edit / Remove / Reset to defaults buttons
   - This table populates `config/sources.json`

5. **About**
   - Version, description, links to spec docs

---

### `modules/main_window.py`
Main application window.

```python
class MainWindow(QMainWindow):
    def __init__(self, config: ConfigManager, db: Database)
```

Layout:
```
┌─ Menu Bar ─────────────────────────────────────────────────┐
│ File | Tools | Help                                         │
├─ Tab Bar ──────────────────────────────────────────────────┤
│ [Editor]  [Library]  [Search]  [Settings]                  │
├────────────────────────────────────────────────────────────┤
│  (Tab content area)                                         │
├─ Status Bar ───────────────────────────────────────────────┤
│ Ready  |  API: 58/60 remaining  |  ~/.claude/skills/ (5)   │
└────────────────────────────────────────────────────────────┘
```

**Menu:**
- `File` → New Skill | Open Skill | Save | Save As | Import ZIP | Export ZIP | Exit
- `Tools` → Validate Current | Clear GitHub Cache | Open Skills Folder | Refresh Library
- `Help` → About | View Spec | GitHub Repos

**Status bar sections (3 segments):**
1. Message area (left, stretching)
2. GitHub rate limit: `API: 58/60` (centre)
3. User skills dir + count: `~/.claude/skills/ (5 skills)` (right)

**Tab communication:**
- Editor tab exposes `load_skill(path)` method → Library/Search can open skills in editor
- `set_status(message, timeout_ms=3000)` on main window for transient status messages

---

## Config Files

### `config/config.json` (auto-created)
See config_manager default structure above. Created with defaults on first run if missing.

### `config/sources.json` (bundled)
Initial list of GitHub source repos. User-editable via Settings tab. This file ships with the app and is read by `search_tab.py`.

---

## Coding Standards (CRITICAL — follow exactly)

1. **No hardcoded values.** All configurable values in `config.json`. All paths via `pathlib.Path`. Always `Path.home()` + `expanduser()`.

2. **No error suppression.** No `except: pass`. No broad catches without logging. Use `logging.exception()` to log with traceback.

3. **QThread for all network/file ops.** Never block the GUI thread. GitHub API calls, directory scans, ZIP operations → all in QThread workers. Emit signals for progress/results.

4. **Tables — all columns resizable.** NEVER `setStretchLastSection(True)`. Hide vertical headers (`table.verticalHeader().hide()`). All tables sortable.

5. **Buttons must have visible captions.** Never use `setFixedWidth` on QPushButton.

6. **Paths:**
   - Python file I/O: `pathlib.Path` everywhere, `open(..., encoding='utf-8')`
   - Cross-platform: `Path.home()`, NOT `~` or `C:\Users\...`
   - subprocess on Windows: use `encoding='utf-8', errors='replace'`

7. **Version increment.** After each change, increment `APP_VERSION` in `main.py`.

8. **Dark theme.** App uses Fusion style + dark palette. Define colours as constants at top of `main_window.py`:
   ```python
   BG_DARK = "#1e1e1e"
   BG_MEDIUM = "#252526"
   BG_LIGHT = "#2d2d30"
   FG_PRIMARY = "#d4d4d4"
   FG_SECONDARY = "#9d9d9d"
   ACCENT = "#569cd6"
   ACCENT_GREEN = "#4ec9b0"
   ACCENT_ORANGE = "#ce9178"
   ERROR_RED = "#f44747"
   WARN_ORANGE = "#dcdcaa"
   ```

9. **Logging.** `logging.basicConfig` to `logs/skills_builder.log` + console. Use module-level loggers: `logger = logging.getLogger(__name__)`.

10. **State persistence.** Save window size/position, last open tab, table column widths to config on close. Restore on open.

---

## Built-in Skill Templates

These are embedded in `editor_tab.py` as a dict of template strings, NOT external files.

| Template Name | Description |
|--------------|-------------|
| `blank` | Minimal skeleton — name + description frontmatter + empty body |
| `minimal` | Standard skill with Usage and Examples sections |
| `with-scripts` | Skill that references scripts/ directory |
| `with-references` | Skill with references/ directory docs |
| `code-review` | Code review skill (based on obra/superpowers pattern) |
| `documentation` | Documentation generation skill |
| `testing` | TDD/test writing and execution skill |
| `git-workflow` | Git operations skill (commit, PR, worktrees) |
| `web-research` | Web research + article extraction skill |
| `data-analysis` | CSV/data analysis skill |
| `security-audit` | Security review skill (OWASP, static analysis pattern) |
| `custom-tool` | Custom tool/MCP integration template |
| `devops` | CI/CD, cloud deployment, Docker skill template |
| `frontend-design` | UI/UX and frontend design constraints skill |
| `database` | Database query and schema skill (read-only SQL pattern) |
| `api-integration` | Third-party API integration skill |

---

## Known Tool Names for allowed-tools

```python
ALLOWED_TOOLS = [
    "Read", "Write", "Edit", "MultiEdit",
    "Grep", "Glob", "Bash",
    "WebFetch", "WebSearch",
    "Task", "TodoWrite", "NotebookEdit",
    "AskUserQuestion", "Skill"
]
```

Also accept patterns like `Bash(git:*)`, `Bash(npm:*)`, `mcp__*`.

---

## Validation Rules Summary (for `validator.py`)

### Name Rules (all must pass):
- `[a-z0-9-]+` regex match
- Length 1-64
- Not start with `-`
- Not end with `-`
- Not contain `--`
- Not contain `anthropic`
- Not contain `claude`
- Not empty

### Description Rules:
- Length 1-1024 (error if exceeded)
- Not empty (error)
- Warn if < 50 chars
- Warn if doesn't contain trigger keywords ("use when", "when user", "for", "when working with")

### Body Rules:
- Warn if empty (no instructions)
- Warn if > 500 lines (performance)
- Warn if total SKILL.md > 5000 tokens (estimated: chars/4)

---

## GitHub API Usage

Base URL: `https://api.github.com`

Key endpoints:
- `GET /repos/{owner}/{repo}/contents/{path}` — list dir or get file
- `GET /repos/{owner}/{repo}` — repo info (stars, description)
- `GET /search/code?q=filename:SKILL.md+{query}&per_page=30` — code search
- `GET /rate_limit` — check remaining requests

Auth header: `Authorization: token {token}` (if set)

**Rate limit handling:**
- Check `X-RateLimit-Remaining` header on each response
- If remaining < 5, warn user in status bar
- If 0 (403 response), show dialog: "GitHub rate limit reached. Add a token in Settings for 5000/hr, or wait until {reset_time}."
- Cache all responses in SQLite to reduce API calls

---

## Implementation Order

This order allows progressive testing. Each phase should be syntax-checked with `python -m py_compile` and tested by user before proceeding.

### Phase 1: Project Skeleton
- `main.py` with version, QApplication, dark theme, empty MainWindow
- `modules/main_window.py` — 4 empty tabs, menu bar, status bar
- `modules/config_manager.py` — JSON config with defaults
- `requirements.txt`
- `config/config.json` defaults
- `config/sources.json` with pre-populated source list

### Phase 2: Core Logic (no GUI)
- `modules/validator.py` — complete with all rules
- `modules/skill_io.py` — read/write/list/export/import
- `modules/syntax_highlighter.py` — complete highlighter

### Phase 3: Editor Tab
- `modules/editor_tab.py` — full editor with form + raw editor + highlighter
- Template gallery dialog
- Live validation display
- Save / Save As / Backup

### Phase 4: Library Tab
- `modules/library_tab.py` — user + project scope sub-tabs
- Full CRUD + export/import
- Open-in-editor integration

### Phase 5: GitHub Search
- `modules/database.py` — SQLite schema + queries
- `modules/github_client.py` — API wrapper + caching
- `modules/search_tab.py` — all 3 sub-tabs + import dialog
- Rate limit display in status bar

### Phase 6: Settings
- `modules/settings_tab.py` — full settings UI
- Source repos editable table
- GitHub token test
- Path verification

### Phase 7: Polish
- State persistence (window size, last tab, column widths)
- Error handling review (no suppressed errors)
- Logging to file
- Test on both Windows and Linux paths
- Export ZIP fully working (for claude.ai upload)

---

## Reference Links

- Official Skills Spec: https://agentskills.io/specification
- Validation CLI: https://github.com/agentskills/agentskills/tree/main/skills-ref (`skills-ref validate ./my-skill`)
- Anthropic Skills Overview: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- Anthropic Skills Examples: https://github.com/anthropics/skills
- VoltAgent (383+ official team skills): https://github.com/VoltAgent/awesome-agent-skills
- ComposioHQ (SaaS integrations): https://github.com/ComposioHQ/awesome-claude-skills
- travisvn (curated + docs): https://github.com/travisvn/awesome-claude-skills
- hesreallyhim (full ecosystem): https://github.com/hesreallyhim/awesome-claude-code
- BehiSecc (scientific/security): https://github.com/BehiSecc/awesome-claude-skills
- Superpowers Skills: https://github.com/obra/superpowers-skills
- Trail of Bits Security: https://github.com/trailofbits/skills

---

## Development Notes

- **Do NOT run the GUI** during syntax checking — `python -m py_compile` only
- **Ask user to test** all GUI and visual functionality
- **Git repo:** https://github.com/RafalekS/skills_builder — commit regularly
- **Windows paths in file tool parameters:** use backslashes (e.g. `C:\Scripts\AI\skills_builder\main.py`)
- **Bash commands:** use forward slashes (e.g. `/c/Scripts/AI/skills_builder/`)
- **NEVER mark anything complete** until user has tested it
