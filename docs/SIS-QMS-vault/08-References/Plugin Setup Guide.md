---
tags: [reference, setup, plugins]
created: 2026-02-10
---

# Plugin Setup Guide

Step-by-step guide for installing and configuring the recommended Obsidian community plugins for the QMS Second Brain.

## How to Install Community Plugins

1. Open Obsidian Settings (gear icon or `Ctrl+,`)
2. Go to **Community plugins** in the left sidebar
3. Click **Turn on community plugins** (first time only)
4. Click **Browse** to open the plugin marketplace
5. Search for the plugin name, click **Install**, then **Enable**

---

## Essential Plugins (Install First)

### 1. Dataview
**What:** Query your notes like a database using inline code blocks.
**Why:** Powers all the dynamic tables on the [[Home]] dashboard and [[Module Index]].

**Install:** Search "Dataview" by Michael Brenan

**Configuration:**
- Settings → Dataview → Enable JavaScript Queries: **ON**
- Settings → Dataview → Enable Inline Queries: **ON**

**Test it works:** Open [[Home]] — you should see module tables rendered dynamically.

**Example query (already in your vault):**
````
```dataview
TABLE status, cli_name, length(commands) AS "Commands"
FROM "01-QMS-Modules"
WHERE contains(tags, "qms-module")
```
````

---

### 2. Templater
**What:** Advanced templates with variables, dates, and logic.
**Why:** Auto-fills dates, module names, and boilerplate when creating new notes.

**Install:** Search "Templater" by SilentVoid

**Configuration:**
- Settings → Templater → Template folder location: `Templates`
- Settings → Templater → Trigger Templater on new file creation: **ON**

**Usage:**
1. `Ctrl+N` to create a new note
2. `Alt+E` to insert a template (or use the Templater icon)
3. Select the appropriate template (Module, CLI Command, ADR, etc.)

---

### 3. Obsidian Git
**What:** Automatic Git backup of your vault.
**Why:** Version control for your documentation — never lose work.

**Install:** Search "Obsidian Git" by Vinzent

**Configuration:**
- Settings → Obsidian Git → Auto backup interval: `10` minutes
- Settings → Obsidian Git → Auto pull on startup: **ON**
- Settings → Obsidian Git → Commit message: `vault backup: {{date}}`

**Setup (one-time):**
```bash
cd D:\SIS-QMS
git init
git add -A
git commit -m "Initial vault setup"
# Optionally push to GitHub:
# gh repo create SIS-QMS-Vault --private --source=. --push
```

> Note: You chose not to set up Git initially, but this plugin makes it easy to add later.

---

## Recommended Plugins

### 4. Excalidraw
**What:** Draw diagrams, flowcharts, and architecture sketches inside Obsidian.
**Why:** Create visual system diagrams, module dependency graphs, and data flow charts.

**Install:** Search "Excalidraw" by Zsolt Viczián

**Usage:**
- Create `.excalidraw.md` files in the `Attachments` folder
- Embed in notes with `![[diagram.excalidraw]]`
- Great for: architecture diagrams, ER diagrams, process flows

---

### 5. Kanban
**What:** Kanban boards as markdown files.
**Why:** Track documentation progress, module completion, and development tasks.

**Install:** Search "Kanban" by mgmeyers

**Example board for QMS docs:**
```
## Backlog
- [ ] reporting module docs
- [ ] CLI command reference pages

## In Progress
- [ ] Database table detail pages

## Done
- [x] Module docs (all 11)
- [x] Architecture overview
- [x] API overview
```

---

### 6. Graph Analysis
**What:** Enhanced graph view with clustering, orphan detection, and centrality analysis.
**Why:** Visualize which modules are most interconnected, find orphan notes, spot missing links.

**Install:** Search "Graph Analysis" by SkepticMystic

---

### 7. Calendar
**What:** Calendar widget linked to daily notes.
**Why:** Navigate dev journal entries by date.

**Install:** Search "Calendar" by Liam Cain

**Configuration:**
- Settings → Calendar → Daily note folder: `06-Dev-Journal`
- Settings → Calendar → Daily note template: `Templates/Dev Journal Template`

---

### 8. Advanced Tables
**What:** Tab-key table navigation and formatting.
**Why:** Makes editing the many markdown tables in module docs much easier.

**Install:** Search "Advanced Tables" by Tony Grosinger

---

## Optional / Power-User Plugins

| Plugin | Purpose |
|--------|---------|
| **Breadcrumbs** | Define parent/child relationships between notes |
| **DB Folder** | Database-like table views of notes in a folder |
| **Smart Second Brain** | AI-powered chat with your vault using RAG |
| **Mermaid Tools** | Enhanced Mermaid diagram editor |
| **Tag Wrangler** | Rename, merge, and manage tags |
| **Linter** | Auto-format markdown on save |

## Core Plugin Settings

These are built-in Obsidian plugins — enable them in Settings → Core plugins:

| Plugin | Enable? | Why |
|--------|---------|-----|
| Templates | **ON** | Basic template insertion (Templater supersedes but both work) |
| Daily notes | **ON** | Quick dev journal creation |
| Graph view | **ON** | Visualize note connections |
| Backlinks | **ON** | See what links to current note |
| Tag pane | **ON** | Browse all tags |
| Page preview | **ON** | Hover preview of linked notes |
| Outgoing links | **ON** | See what current note links to |

---

## After Installing Plugins

1. Open [[Home]] — verify Dataview tables render
2. Open the Graph View (`Ctrl+G`) — you should see the module interconnection web
3. Try creating a new note with `Ctrl+N`, then apply a template
4. Check that Mermaid diagrams render in [[Architecture Overview]]

## Related Notes
- [[Home]] — Dashboard (uses Dataview)
- [[Architecture Overview]] — Uses Mermaid diagrams
