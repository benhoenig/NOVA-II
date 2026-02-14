# Ben's Agentic Automation

A 3-layer architecture system for reliable AI-powered automation.

## Architecture Overview

This system separates concerns across three layers to maximize reliability and maintainability:

1. **Directives** (`directives/`) - Natural language SOPs defining what to do
2. **Orchestration** (AI Agent) - Intelligent decision-making and routing
3. **Execution** (`execution/`) - Deterministic Python scripts that do the work

## Quick Start

1. **Set up Python environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   - Copy `.env` and add your API keys
   - Add Google OAuth credentials (`credentials.json`) if using Google APIs

3. **Create your first directive:**
   - Add a new `.md` file in `directives/` describing your workflow
   - AI agent will read it and execute the corresponding scripts

## Directory Structure

- `directives/` - Workflow instructions (SOPs in Markdown)
- `execution/` - Python scripts (deterministic tools)
- `.tmp/` - Temporary/intermediate files (auto-generated, not committed)
- `.env` - Environment variables and API keys
- `GEMINI.md` - Agent operating instructions

## Key Principles

- **Self-annealing**: When errors occur, fix the script, test, and update the directive
- **Deterministic execution**: Push complexity into Python scripts, not AI decisions
- **Cloud deliverables**: Final outputs go to Google Sheets/Slides, not local files
- **Living documentation**: Continuously update directives with learnings

## File Organization

- **Local files** are only for processing
- **Deliverables** live in cloud services (Google Sheets, Slides, etc.)
- Everything in `.tmp/` can be deleted and regenerated

For detailed agent instructions, see `GEMINI.md`.
