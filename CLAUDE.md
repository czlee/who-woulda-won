# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Who Woulda Won?** compares voting systems on West Coast Swing competition scoresheets. It parses scoresheets from multiple sources, applies four voting systems (Borda Count, Relative Placement, Schulze Method, Sequential IRV), and displays comparative results in a web interface.

## Commands

```bash
# Install dependencies
poetry install

# Run all tests
poetry run pytest

# Run a specific test file
poetry run pytest tests/test_voting/test_borda.py
```

CI runs `pytest` via GitHub Actions on every push.

If you're on the user's local machine, the development environment is not set up to run `flask` locally. If making modifications to the frontend, skip verifying frontend changes and leave these for the user to do manually.

## Architecture

```
core/               # Backend business logic
  models.py         # Dataclasses: Scoresheet, Placement, VotingResult, AnalysisResult
  analyze.py        # Orchestrator: parse scoresheet → run all voting systems
  parsers/          # Scoresheet parsers (plugin architecture)
    base.py         # Abstract ScoresheetParser base class
  voting/           # Voting system implementations (plugin architecture)
    base.py         # Abstract VotingSystem base class

api/analyze.py      # Flask serverless endpoint: POST /api/analyze

public/             # Frontend (vanilla HTML/CSS/JS, served statically)
  index.html
  app.js
  styles.css

tests/              # Mirrors source structure (test_voting/, test_parsers/)
  conftest.py       # Shared fixtures (make_scoresheet, ranking_names)
```

### Plugin registration

Both parsers and voting systems use a decorator-based registration pattern:
- `@register_parser` in `core/parsers/__init__.py` — parser auto-detected by URL or content
- `@register_voting_system` in `core/voting/__init__.py` — all registered systems run on every analysis

To add a new parser or voting system, implement the base class and apply the registration decorator.

### Data flow

1. Frontend sends scoresheet URL or file → `POST /api/analyze`
2. API auto-detects parser → parses into `Scoresheet` model
3. Orchestrator runs all registered voting systems → returns `AnalysisResult` as JSON
4. Frontend renders comparison of all voting outcomes

## Deployment

Hosted on Vercel: Python serverless functions in `api/`, static files in `public/`. Poetry is used for local development only, not in production.

## Git Conventions

Prefix Claude-created branches with `claude/` (not `czlee/`).
