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

# Run a python command
poetry run python3 ...
```

Anything involving python must be run via `poetry`.

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

## Writing Tests

Sometimes, test cases for rare tiebreak situations can be difficult to construct. If it takes more than five attempts to generate a scoresheet that would trigger a planned test case, STOP, instead write notes of your thinking so far to a Markdown file, and inform the user. The user will take over constructing the test case from there.

## Mobile Responsiveness

Mobile layout is handled with a single `@media (max-width: 600px)` breakpoint at the bottom of `styles.css`. It reduces padding, font sizes, and adjusts minor layout details (e.g., floated elements become block-level). The main results table uses `width: 100%` with `table-layout: fixed`, so it compresses columns to fit the screen. Detail tables (RP, Borda, Schulze working tables) use `white-space: nowrap` without a fixed width, so they scroll horizontally via `overflow-x: auto` wrappers on narrow screens.

## Deployment

Hosted on Vercel: Python serverless functions in `api/`, static files in `public/`. Poetry is used for local development only, not in production.

## Git Conventions

Prefix Claude-created branches with `claude/` (not `czlee/`).

## Personally Identifiable Information

The `examples/` directory may contain real examples of scoresheets with personal data. While they're technically publicly accessible, we should treat them as sensitive and never commit them to the repository.
