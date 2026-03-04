---
name: analyze-example
description: Runs an example scoresheet file through the analysis pipeline and shows the result.
---

## Usage

```
/analyze-example <file_path> [division]
```

- `file_path`: path to the example file (e.g. `examples/eepro-example-1.html`)
- `division`: optional division name or substring to select (for multi-division files)

## Instructions

When this skill is invoked to analyze an example scoreseheet, run the following command (substituting the actual file path and division):

```bash
poetry run python3 -c "
import sys, json
from pathlib import Path
sys.path.insert(0, '.')

from core.parsers import scoring_dance, eepro, danceconvention  # noqa
from core.voting import borda, relative_placement, schulze, sequential_irv  # noqa
from core.analyze import analyze_scoresheet

path = Path('FILEPATH')
result = analyze_scoresheet(path.name, path.read_bytes(), division=DIVISION)
print(json.dumps(result.to_dict(), indent=2))
"
```

Where:
- `FILEPATH` is replaced with the file path argument
- `DIVISION` is replaced with the quoted division string if provided, or `None` if not

If the command fails because the file has multiple divisions and no division was specified, show the available divisions from the error message and ask the user which one to use, then re-run with that division.

Display the JSON output to the user.

## Output structure notes

Each item in `final_ranking` has keys `name`, `rank`, and `tied` — not `competitor`.
