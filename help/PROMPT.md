# Original Requirements

## User Request (20/02/2026)

Create a Claude Skills Builder — a visual tool for creating Claude Code skills with:

- Correct SKILL.md frontmatter generation
- Functional editor with syntax highlighting
- Search across GitHub (awesome-claude-skills repos and GitHub search)
- Import skills into user config (~/.claude/skills) or project scope
- Cross-platform: Windows and Linux aware
- No hardcoded values — everything configurable
- PyQt6 with coding skill standards

## Reference Sources

### Skill Format Specs
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- https://agentskills.io/specification

### Official Skills Examples
- https://github.com/anthropics/skills

### Community Skill Collections
- https://github.com/ComposioHQ/awesome-claude-skills
- https://github.com/BehiSecc/awesome-claude-skills
- https://github.com/hesreallyhim/awesome-claude-code
- https://github.com/VoltAgent/awesome-agent-skills
- https://github.com/travisvn/awesome-claude-skills

### Reference Implementation (private — author's Claude_DB project)
- skills_tab.py — skill editor and list UI pattern
- skill_library_dialog.py — library/template dialog pattern

## Target Repo
https://github.com/RafalekS/skills_builder (empty — commit to this)
