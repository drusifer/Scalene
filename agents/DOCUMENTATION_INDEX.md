# BobProtocol Documentation Index

**Last Updated:** 2026-07-09

## Quick Access

Type `*help` for complete command reference with examples.

---

## Primary Documentation

### Getting Started
- **[README.md](../README.md)** - Project overview and team reference
- **[HELP.md](bob/HELP.md)** - Quick reference for all 8 personas and commands

### Tools
- **[tools/](tools/)** - Agent tooling scripts (`chat.py`, `mkf.py`, `setup_agent_links.py`)

---

## Project Documentation (Scalene)

- **[../docs/BRD.md](../docs/BRD.md)** - Business Requirements Document (source of truth for scope)
- **[../docs/PRD.md](../docs/PRD.md)** - Product Requirements Document (Cypher)
- **[../docs/USER_STORIES.md](../docs/USER_STORIES.md)** - User stories + acceptance criteria (9 stories, Sprint 1)
- **[../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)** - System architecture (Morpheus)
- **[../docs/SETUP.md](../docs/SETUP.md)** - Install + hook registration instructions
- **[../docs/STORY_TRACEABILITY.md](../docs/STORY_TRACEABILITY.md)** - AC-to-test traceability (Sprint 1 close)
- **[../task.md](../task.md)** - Sprint task board (Mouse, single source of truth for sprint status)

---

## Persona Documentation

### Active Personas (8)

| Persona | Role | SKILL.md | Prefix |
|---------|------|----------|--------|
| Bob | Prompt Engineering Expert | [bob/SKILL.md](bob/SKILL.md) | `*new` / `*reprompt` / `*learn` |
| Cypher | Product Manager | [cypher/SKILL.md](cypher/SKILL.md) | `*pm` |
| Morpheus | Tech Lead / Architect | [morpheus/SKILL.md](morpheus/SKILL.md) | `*lead` |
| Neo | Senior Software Engineer | [neo/SKILL.md](neo/SKILL.md) | `*swe` |
| Oracle | Knowledge Officer | [oracle/SKILL.md](oracle/SKILL.md) | `*ora` |
| Trin | QA / Guardian | [trin/SKILL.md](trin/SKILL.md) | `*qa` |
| Mouse | Scrum Master | [mouse/SKILL.md](mouse/SKILL.md) | `*sm` |
| Smith | Expert User & UX Advocate | [smith/SKILL.md](smith/SKILL.md) | `*user` |

---

## Team Communication

- **[CHAT.md](CHAT.md)** - Team communication log (append-only)
- Each persona maintains state in their `<name>/` folder:
  - `context.md` - Working memory
  - `current_task.md` - Active work
  - `next_steps.md` - Resume plan

---

## Template Files

Located in `agents/templates/`:

- `_template_ARCH.md` - Architecture decision record
- `_template_CHAT.md` - CHAT.md message format
- `_template_context.md` - Agent context.md
- `_template_current_task.md` - Agent current_task.md
- `_template_finding.md` - Research finding
- `_template_LESSON.md` - Lesson learned
- `_template_next_steps.md` - Agent next_steps.md
- `_template_tldr.md` - TLDR block formats

---

## Tools Directory

**Location:** `agents/tools/`

- `chat.py` - Post messages to CHAT.md
- `mkf.py` - Build output filter (routes make output)
- `setup_agent_links.py` - Create `.claude/skills/` symlinks (run once on setup)

---

## Archived Documentation

Files prefixed with `.archive_` are historical and no longer active:
- `oracle/.archive_COMMANDS.md` - (Consolidated into HELP.md)

---

## Documentation Standards

### File Naming
- Persona definitions: `[PersonaName]_[ROLE]_AGENT.md`
- State files: `context.md`, `current_task.md`, `next_steps.md`
- MCP tools: `[toolname]_mcp.md`
- Templates: `_template_*.md`
- Archived: `.archive_*.md`

### Structure
- All persona docs in `agents/[persona]/`
- All MCP tool docs in `agents/tools/`
- Team communication in `agents/CHAT.md`
- Primary references in `agents/bob/`

### Maintenance
- Update `*help` when adding commands
- Update tool docs when changing MCPs
- Archive outdated docs with `.archive_` prefix
- Keep `bob/HELP.md` in sync with the persona table above

---

## Quick Command Reference

```bash
*help                          # Show complete help
*chat                          # Activate Bob System
*prompt <desc>                 # Create agent (Bob)
*swe impl <task>              # Implement (Neo)
*qa test <scope>              # Test (Trin)
*ora ask <question>           # Query knowledge (Oracle)
*lead plan <epic>             # Plan (Morpheus)
*pm doc <type>                # Create PRD (Cypher)
*sm status                    # Sprint status (Mouse)
```

---

**For Help:** Type `*help` or read `agents/bob/HELP.md`
