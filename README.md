# Burning Empires Lifepath Navigator

A reverse-flow character building tool for [Burning Empires](https://www.burningwheel.com/burning-empires/), the sci-fi tabletop RPG by Luke Crane. Making complicated things MORE complicated. For fun.

## What It Does

Instead of building a character forward from birth, this tool lets you **start with your destination and work backwards**. Specify where you want to end up, and the navigator finds all valid paths to get there.

Features:
- Find all valid lifepath chains ending at your target lifepath
- Optimize for stats, circles, resources, or youth
- **Optimize for Infection maneuver coverage** (total or per-phase)
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
| `lifepath_solver.py` | Chain-finding engine, validation logic, and `ManeuverData` class |
| `human_lifepaths_complete.json` | 222 lifepaths with pre-parsed structured requirements |
| `maneuver_skills.json` | Infection maneuver-to-skill mapping (3 phases x 8 maneuvers) |
| `character_burning_prompt.md` | LLM system prompt for AI-assisted character burning |
| `character_validator.py` | Point-buy verification: stats, skills, traits, circles, resources, derived stats |
| `test_lifepath_solver.py` | 132-test suite (data integrity, requirements, search, regressions, maneuver coverage) |
| `test_character_validator.py` | 45-test suite (budget computation, skill costs, required opens, full build validation) |
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
| `optimize` | Sort criteria: `years-`, `years+`, `stats+`, `mental+`, `physical+`, `resources+`, `circles+`, `maneuvers+`, `maneuvers-inf+`, `maneuvers-usu+`, `maneuvers-inv+` |
| `require_settings` | Settings that must have at least one LP in the chain |
| `exclude_settings` | Settings to exclude entirely |
| `born_preference` | `rough`, `noble`, `common`, or `None` |
| `limit` | Max results to return (default: 10) |

## Maneuver Coverage

Burning Empires Infection mechanics require specific skills for each maneuver in each phase (Infiltration, Usurpation, Invasion). The solver can optimize lifepath chains to maximize the number of maneuvers a character can participate in.

```python
from lifepath_solver import LifepathSolver

solver = LifepathSolver("human_lifepaths_complete.json")

# Maximize total maneuver coverage across all phases
chains = solver.find_chains(
    target_name="Smuggler",
    length=6,
    optimize=["maneuvers+"],
    limit=5
)

# Specialize in a single phase
chains = solver.find_chains(
    target_name="Politico",
    length=6,
    optimize=["maneuvers-usu+"],  # Usurpation specialist
    limit=5
)
```

Coverage is reported as slots covered out of 24 total (8 per phase). A character with coverage in 18/24 slots can roll for 18 of the 24 phase-maneuver combinations.

The four maneuver optimization options:
| Option | Maximizes |
|--------|-----------|
| `maneuvers+` | Total coverage across all three phases |
| `maneuvers-inf+` | Infiltration phase coverage |
| `maneuvers-usu+` | Usurpation phase coverage |
| `maneuvers-inv+` | Invasion phase coverage |

The `ManeuverData` class can also be used standalone:

```python
from lifepath_solver import ManeuverData

md = ManeuverData("maneuver_skills.json")
coverage = md.compute_coverage({"Tactics", "Strategy", "Propaganda", "Logistics"})
print(md.format_coverage(coverage))  # e.g. "15/24 (5/8 Inf, 5/8 Usu, 5/8 Inv)"
```

## Character Validator

After finding a lifepath chain with the solver, use the **CharacterValidator** to verify that all point-buy math adds up. It catches the cascading arithmetic errors that plague hand-built characters.

### Budget Mode

Compute available pools before the player makes spending decisions:

```bash
python character_validator.py --budgets "Born to Rule" "Student (Commune)" \
    "Financier (Commune)" "Politico (Commune)" "Criminal" "Criminal"
```

Output shows age, stat pools (mental/physical), skill points (LP + general), trait points, resource points, circles points, and all required skill/trait opens.

### Validate Mode

Check a complete build against its chain's budgets:

```bash
python character_validator.py build.json
```

The build JSON specifies stats, skills (with exponents), traits, circles spending, resources, and derived stats. The validator checks every pool, flags overspends, verifies required opens, and confirms derived stat calculations.

### As a Library

```python
from character_validator import CharacterValidator

validator = CharacterValidator(
    "human_lifepaths_complete.json",
    "skill_roots.json",
    "trait_list.json"
)

# Budget mode
budget = validator.compute_budgets(["Born to Rule", "Student (Commune)", ...])

# Validate mode
report = validator.validate_build(build_dict)
print(report.format_report())
```

See `character_burning_prompt.md` for the full build schema and integration guidance.

## LLM-Assisted Character Burning

`character_burning_prompt.md` is a system prompt for using an LLM (e.g., Claude) as an interactive character burning assistant. It walks players through the full Burning Empires character creation process and uses the solver API to find and validate lifepath chains. Load the prompt as a system message, attach the solver and data files, and the LLM handles the rest.

## Running Tests

```bash
pytest test_lifepath_solver.py test_character_validator.py -v
```

177 tests total: 132 covering data integrity, requirement satisfaction, lifepath ordering, k-of-n requirements, trait paths, complex conjunctions, position constraints, edge cases, hard negatives, search correctness, real-world integration scenarios, canonical chain regressions, and maneuver coverage; plus 45 covering budget computation, stat pool brackets, skill cost calculation, required opens, trait costs, circles/resource spending, derived stats, full build validation, and edge cases.

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
