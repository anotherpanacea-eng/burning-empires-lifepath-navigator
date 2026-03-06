# Burning Empires Lifepath Navigator

A reverse-flow character building tool for [Burning Empires](https://www.burningwheel.com/burning-empires/), the sci-fi tabletop RPG by Luke Crane. Making complicated things MORE complicated. For fun.

## What It Does

Instead of building a character forward from birth, this tool lets you **start with your destination and work backwards**. Specify where you want to end up, and the navigator finds all valid paths to get there.

Features:
- Find all valid lifepath chains ending at your target lifepath
- Optimize for stats, circles, resources, or youth
- Require specific lifepaths to pass through
- Filter by starting background (rough, noble, or common origins)
- Require or exclude specific settings
- Validates ordinal constraints ("must be second lifepath")
- Handles complex requirements: k-of-n, requires-twice, tag-based, trait paths
- Warns about trait requirements (Mark of Privilege, etc.)
- Shows canonical path templates for capstone lifepaths

## Requirements

- Python 3.7+
- No external dependencies (uses only standard library)
- pytest (for running tests only)

## Quick Start

```bash
python lifepath_cli.py
```

This launches an interactive questionnaire that walks you through:
1. Target lifepath (with fuzzy name matching)
2. Canonical path suggestion (if available)
3. Chain length (5-10 lifepaths)
4. Primary and secondary optimization
5. Must-include lifepaths
6. Setting filters (require or exclude)
7. Starting background preference

## Example Session

```
╔══════════════════════════════════════════════════════════════╗
║        BURNING EMPIRES LIFEPATH NAVIGATOR                    ║
║                  Interactive Chain Builder                    ║
╚══════════════════════════════════════════════════════════════╝

What lifepath do you want to end at?
Target lifepath: Speaker

💡 Path template (43 years):
   [Any Born] → Foundation Student → Psychologist → Psychologist → Speaker
   Key LPs: Foundation Student, Psychologist
   (+5M/P, +6C, +7R)

How many lifepaths in the chain?
Chain length [5]: 5

Found 12 chain(s):
────────────────────────────────────────────────────────────────

1. Born to Rule → Foundation Student → Psychologist → Psychologist → Speaker
   Stats: M:2 P:1 Flex:2  Res: 7  Circ: 6  Traits: 3 net  Years: 38
```

## Files

| File | Purpose |
|------|---------|
| `lifepath_cli.py` | Interactive terminal interface |
| `lifepath_solver.py` | Chain-finding engine and validation logic |
| `human_lifepaths_complete.json` | 222 lifepaths with pre-parsed structured requirements |
| `test_lifepath_solver.py` | 119-test suite (data integrity, requirements, search, regressions) |
| `generate_canonical_chains.py` | Generates canonical chain templates for capstone lifepaths |
| `canonical_test_fixtures.json` | Pre-computed test fixtures for regression testing |

## Using the Solver as a Library

```python
from lifepath_solver import LifepathSolver

solver = LifepathSolver("human_lifepaths_complete.json")

# Find 6-LP chains ending at Criminal, optimized for youngest character
chains = solver.find_chains(
    target_name="Criminal",
    length=6,
    optimize=["years-"],
    limit=5
)

for chain in chains:
    path = " → ".join(lp.name for lp in chain.lifepaths)
    print(f"{path}  ({chain.total_years} years)")
```

### Solver Options

| Parameter | Description |
|-----------|-------------|
| `target_name` | Name of the ending lifepath |
| `length` | Exact chain length (5-10) |
| `must_include` | List of lifepath names that must appear in the chain |
| `optimize` | Sort criteria: `years-`, `years+`, `stats+`, `mental+`, `physical+`, `resources+`, `circles+` |
| `require_settings` | Settings that must have at least one LP in the chain |
| `exclude_settings` | Settings to exclude entirely |
| `born_preference` | `rough`, `noble`, `common`, or `None` |
| `limit` | Max results to return (default: 10) |

## Running Tests

```bash
pytest test_lifepath_solver.py -v
```

119 tests covering data integrity, requirement satisfaction, lifepath ordering, k-of-n requirements, trait paths, complex conjunctions, position constraints, edge cases, hard negatives, search correctness, real-world integration scenarios, and canonical chain regressions.

## Data

`human_lifepaths_complete.json` contains 222 human lifepaths across 12 settings:

| Setting | Count |
|---------|-------|
| Anvil | 16 |
| Commune | 21 |
| Freeman | 21 |
| Hammer | 17 |
| Merchant League | 16 |
| Nobility | 13 |
| Outcast and Criminal | 36 |
| Psychologist Foundations | 8 |
| Servitude and Serfdom | 13 |
| Spacefarer | 16 |
| Stewardship and Court | 21 |
| Theocracy | 24 |

## Credits

**Burning Empires** is © Luke Crane and published by [Burning Wheel HQ](https://www.burningwheel.com/). This tool is an unofficial fan project and is not affiliated with or endorsed by Burning Wheel HQ.

All lifepath data is derived from the Burning Empires rulebook. If you enjoy this tool, please support the creators by purchasing the game!

## License

This tool is provided for personal, non-commercial use by the Burning Empires community. The lifepath data remains the intellectual property of Luke Crane / Burning Wheel HQ.
