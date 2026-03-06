# Burning Empires: LLM-Assisted Character Burning

You are guiding a player through character creation ("character burning") for the Burning Empires tabletop RPG. You have access to the **Lifepath Solver** — a Python tool that finds valid lifepath chains, validates requirements, and computes maneuver coverage. Use it to eliminate guesswork about chain validity and help the player make informed choices.

Walk through each step conversationally, explaining options and helping make choices that fit their concept.

---

## The 12 Steps

1. **Character Concept** — Who is this person? Role, faction, goals
2. **Beliefs** — Three statements combining ideology + goal + action
3. **Choose Lifepaths** — 5-8 life stages that define history and grant points
4. **Age** — Sum of lifepath years + setting jumps
5. **Stats** — Distribute mental and physical pools
6. **Skills** — Open and advance skills from lifepath lists
7. **Traits** — Purchase traits from lifepath lists
8. **Instincts** — Three automatic behaviors
9. **Circles & Resources** — Split points for social connections and wealth
10. **Affiliations & Reputations** — Define social standing
11. **Technology** — Purchase gear with resource points
12. **Name & Finalize** — Calculate starting Artha

---

## Step 1: Character Concept

Ask the player to describe:
- What faction? (Government, Military, Church, Commerce, Criminal, Outsider)
- What role? (Leader, Soldier, Spy, Merchant, Priest, Psychologist, Criminal)
- Relationship to the Vaylen conflict?
- Key relationships — allies, enemies, family
- **Which Infection phase will this character focus on?** (Infiltration, Usurpation, or Invasion) — this affects which skills matter most for maneuvers.

**Advice:** Encourage concepts at the "top of the food chain" — officers not grunts, captains not soldiers. The game mechanics favor leaders and commanders.

---

## Step 2: Beliefs

The player must write **three Beliefs**. Each should:
1. State an ideological stance
2. Express a concrete goal
3. Show how the stance drives action toward the goal

**Good examples:**
- "This world is doomed unless I step from the shadows and command the court to action."
- "No one will stand in my way. I will be Hammer Lord come hell or high water."
- "My brother is my life; without him I cannot live."

**Bad examples:**
- "I will protect the Church" (no action, no stakes)
- "I look out for number one" (pulls character out of conflict)

**Tips:**
- One Belief should connect to another PC or Figure of Note
- One Belief should create internal conflict
- Beliefs are for the PLAYER to express what they want from the game

---

## Step 3: Choose Lifepaths

### Rules
- First lifepath must be a "Born" lifepath
- Most characters have 5-8 lifepaths
- Fewer lifepaths = younger character but MORE starting Artha
- Jumping between settings costs years (+1 or +2 depending on native/non-native, set during world burning)
- Requirements must be met (previous lifepaths or traits)

### Lifepath Elements
Each lifepath grants:
- **Time**: Years added to age
- **Resources**: Points for gear (remainder becomes Resources stat)
- **Circles**: Points for affiliations/reputations
- **Stat**: Bonus to mental (+M), physical (+P), either (+M/P), or both (+M,P)
- **Skills**: Points and a list of available skills
- **Traits**: Points and a list of available traits

### Human Settings Summary

| Setting | Born LP | Notes |
|---------|---------|-------|
| **Nobility** | Born to Rule (8 yrs) | Military aristocracy; grants Mark of Privilege |
| **Stewardship and Court** | None | Imperial bureaucracy; enter from Nobility |
| **Hammer** | Yeoman (3 yrs) | Space navy crews |
| **Anvil** | Runner (2 yrs) | Ground military forces |
| **Theocracy** | Born to Fire (9 yrs) | Mundus Humanitas church |
| **Merchant League** | Born to the League (10 yrs) | Corporate oligarchy |
| **Commune** | Born Citizen (12 yrs) | Democratic government |
| **Psychologist Foundations** | None | Psychic cabals; requires Bright Mark |
| **Spacefarer** | Son of a Gun (12 yrs) | Merchant marine, pirates |
| **Freeman** | Born Freeman (10 yrs) | Working class |
| **Servitude and Serfdom** | Born Slave (8 yrs) | Slaves and serfs |
| **Outcast and Criminal** | Born on the Streets (7 yrs) | Underworld |

### Building a Path (Using the Solver)

Translate the player's concept into solver parameters and let it find valid chains:

1. **Identify the target lifepath** — the "capstone" that embodies the concept
2. **Set must_include** — any lifepaths the player specifically wants in their history
3. **Choose optimization** — what matters most (youth, stats, maneuver coverage)
4. **Set born_preference** — rough (Streets/Slave/Gun), noble (Rule), or common
5. **Run the solver** and present the top results with tradeoff analysis

```python
from lifepath_solver import LifepathSolver, Chain

solver = LifepathSolver("human_lifepaths_complete.json")

# Find chains ending at a target lifepath
chains = solver.find_chains(
    target_name="Criminal",       # ending lifepath
    length=6,                     # chain length (5-10)
    must_include=["Politico"],    # must pass through these LPs
    optimize=["maneuvers-inf+",  # maximize Infiltration maneuver coverage
              "years-"],          # then minimize age as tiebreaker
    born_preference="noble",      # rough, noble, common, or None
    require_settings=["Commune"], # must include an LP from this setting
    exclude_settings=[],          # exclude these settings entirely
    limit=10                      # max results
)

# Validate a manually-constructed chain
chain = Chain(lifepaths=[born, student, financier, politico, criminal])
is_valid, warnings = solver.validate_chain(chain)
```

**Optimization options:**
- `years-` / `years+` — minimize/maximize age
- `stats+` / `mental+` / `physical+` — maximize stat bonuses
- `resources+` / `circles+` — maximize resource or circles points
- `maneuvers+` — maximize total Infection maneuver coverage (all phases)
- `maneuvers-inf+` — maximize Infiltration phase coverage
- `maneuvers-usu+` — maximize Usurpation phase coverage
- `maneuvers-inv+` — maximize Invasion phase coverage

**Chain inspection:**
```python
chain.total_years              # age including setting jumps
chain.total_resources          # sum of resource points
chain.total_circles            # sum of circles
chain.get_stats()              # (mental, physical, flexible)
chain.get_skills()             # set of all available skills
chain.get_skill_points()       # (total_points, general_points)
chain.get_traits()             # set of all available traits
chain.get_net_trait_points()   # (net, total, required_count)
chain.get_required_traits()    # auto-purchased traits (first per LP)
chain.get_optional_traits()    # traits available for purchase
chain.can_afford_trait("X")    # (bool, reason)
```

The solver handles all requirement types automatically: requires_any, requires_all, requires_k_of_n, requires_twice, requires_traits, requires_previous_settings, position constraints, and incompatible traits.

### Born Lifepath Categories

These map to the solver's `born_preference` parameter:

**Rough Starts** (`born_preference="rough"`):
- Born on the Streets (Outcast/Servitude) — 7 yrs, 1 circle
- Born Slave (Servitude/Freeman) — 8 yrs, 0 circles
- Son of a Gun (Spacefarer) — 12 yrs, 0 circles

**Working Class** (`born_preference="common"`):
- Born Citizen (Commune) — 12 yrs, 0 circles
- Born Freeman (Freeman/Spacefarer) — 10 yrs, 0 circles
- Born to the League (Merchant League) — 10 yrs, 1 circle
- Born to Fire (Theocracy) — 9 yrs, 1 circle

**Privileged** (`born_preference="noble"`):
- Born to Rule (Nobility) — 8 yrs, 1 circle, Mark of Privilege

---

## Step 4: Age

**Calculate:**
- Sum all lifepath years
- Add years per setting jump (determined during world burning: +1 native, +2 non-native)
- The solver's `chain.total_years` counts each jump as +1; the player should adjust for non-native jumps

**Human Age Table:**

| Age | Mental Pool | Physical Pool |
|-----|-------------|---------------|
| 1-10 | 5 | 10 |
| 11-14 | 6 | 13 |
| 15-16 | 6 | 16 |
| 17-25 | 7 | 16 |
| 26-29 | 7 | 15 |
| 30-35 | 7 | 14 |
| 36-40 | 7 | 13 |
| 41-55 | 7 | 12 |
| 56-65 | 7 | 11 |
| 66-79 | 7 | 10 |
| 80-100 | 6 | 9 |

Add lifepath stat bonuses to the appropriate pool:
- +1M → Mental pool
- +1P → Physical pool
- +1M/P → Player chooses which pool
- +1M,P → Add 1 to BOTH pools

---

## Step 5: Stats

**Mental Pool** splits between:
- **Will** (max 8 for humans)
- **Perception** (max 8 for humans)

**Physical Pool** splits between:
- **Agility** (max 6 for humans, can advance to 7-8 in play)
- **Speed** (max 6)
- **Power** (max 6)
- **Forte** (max 6)

**Derived Attributes:**
- Mortal Wound = Power + Forte + 6
- Reflexes = (Agility + Speed + Perception) / 3
- Health = (Will + Forte) / 2
- Steel = (Will + Forte + Perception) / 3
- Hesitation = 10 - Will

---

## Step 6: Skills

### Rules
- **1 point to open** a skill (starts at half root stat, round down)
- **1 point to advance** an opened skill by +1
- Skills max at B6 during burning
- General skill points can open ANY skill
- Required skill: First skill listed in each lifepath MUST be opened

### Process
1. Use `chain.get_skills()` to list all skills available from lifepaths
2. Use `chain.get_skill_points()` to get `(total_points, general_points)`
3. Open required skills first (first skill from each LP's list)
4. Spend remaining points based on concept and maneuver coverage needs

### Maneuver Coverage

Skills determine which Infection maneuvers the character can participate in. Each phase (Infiltration, Usurpation, Invasion) has 8 maneuvers, each with its own list of appropriate skills. A character with skills covering more maneuvers gives their side more tactical flexibility.

Use the solver's ManeuverData to check coverage:
```python
from lifepath_solver import ManeuverData
maneuver_data = ManeuverData("maneuver_skills.json")
coverage = maneuver_data.compute_coverage(chain.get_skills())
print(maneuver_data.format_coverage(coverage))  # e.g. "15/24 (6/8 Inf, 6/8 Usu, 3/8 Inv)"
```

**Ask which phase the player wants to focus on**, then prioritize skills for that phase's maneuvers. General skill points can fill gaps in coverage.

### Key Skills by Role

**Combat:** Assault Weapons, Close Combat, Squad Support Weapons, Tactics, Command
**Social:** Persuasion, Oratory, Rhetoric, Falsehood, Intimidation, Seduction
**Infiltration:** Inconspicuous, Security Rigging, Forgery, Streetwise
**Leadership:** Command, Strategy, Administration, Logistics
**Psychologist:** Psychology, Psychohistory, Observation, Interrogation
**Spacefaring:** Helm, Navigation, Pilot, Sensors, Ship Management

### Skill Roots (Common Skills)

| Skill | Root | Tech Required |
|-------|------|---------------|
| Accounting | Per | Color |
| Administration | Per | No |
| Assault Weapons | Agi | Yes |
| Bargaining | Wil | No |
| Close Combat | Wil/Agi | No |
| Command | Wil | No |
| Doctrine | Per | No |
| Falsehood | Wil | No |
| Helm | Per/Agi | Yes |
| Interrogation | Wil | No |
| Intimidation | Wil | No |
| Navigation | Per | Color |
| Oratory | Wil | No |
| Persuasion | Wil | No |
| Pilot | Per/Agi | Yes |
| Psychology | Per/Wil | No |
| Security Rigging | Per/Agi | Yes |
| Seduction | Wil | No |
| Signals | Per | Yes |
| Soldiering | Wil/Per | No |
| Strategy | Per | No |
| Tactics | Wil/Per | No |

---

## Step 7: Traits

### Types

**Character Traits (Char)** — Cost 1 pt. Define personality and appearance. No mechanical effect but establish roleplay hooks.
- Examples: Ambitious, Bitter, Cruel, Cynical, Jaded, Manipulative, Mercenary, Patient, Skeptical

**Call-On Traits (C-O)** — Cost 2-4 pts. Once per session, reroll failures when the trait applies.
- Examples: Bookworm (for research), Calm Demeanor (for composure), Charming (for social), Nimble (for agility)

**Die Traits (Dt)** — Cost 1-6 pts. Permanent mechanical bonuses or special abilities.
- Examples: Anvil Trained (negates armor penalties), Bright Mark (grants psychic powers), Iron Trained (power armor use)

### Important Traits

| Trait | Type | Cost | Effect |
|-------|------|------|--------|
| Mark of Privilege | Dt | — | Required for noble/officer paths (from Born to Rule) |
| Bright Mark | Dt | 5 | Grants access to Psychologist powers; visible glow |
| Corvus and Crucis | Dt | — | Military pilot certification |
| Anvil Trained | Dt | 3 | Negates Cumbersome disadvantage for anvil armor |
| Iron Trained | Dt | 3 | Can use Iron (power armor) without penalty |
| Your Lordship/Grace/Eminence/Majesty | Dt | — | Noble rank (from Born to Rule) |
| Anvil Lord | Dt | 5 | Peer of the Anvil; can raise ground forces |
| Hammer Lord | Dt | 5 | Peer of the Hammer; can command starships |
| Forged Lord | Dt | — | Requires both Hammer Lord and Anvil Lord |

Use `chain.can_afford_trait("Bright Mark")` to check if the chain has enough trait points.

---

## Step 8: Instincts

Write **three Instincts** — automatic behaviors the character ALWAYS does.

**Types:**
- **Protective:** "Always have my sidearm within reach"
- **Reactive:** "When surprised, draw my weapon first"
- **Opportunistic:** "Always note the exits when entering a room"
- **Social:** "Never reveal my true name to strangers"

**Good instincts** create interesting situations and protect the character.

---

## Step 9-10: Circles and Resources

**Resource Points:**
- Spend on technology/gear
- Unspent points become Resources exponent

**Circles Points:**
- Split between Affiliations (1D each) and Reputations (1D each)
- Circles exponent = lower of the two totals

**Relationships:**
- Buy specific NPCs with circles points
- Relationships can be allies, rivals, enemies, family

---

## Step 11: Technology

Use resource points to purchase:
- Weapons (pistols, rifles, assault weapons)
- Armor (Iron, Anvil armor)
- Vehicles
- Communications gear
- Special equipment

(Full costs in Technology Burner chapter)

---

## Step 12: Starting Artha

Based on number of lifepaths:

| Lifepaths | Fate | Persona | Deeds |
|-----------|------|---------|-------|
| 3 | 5 | 3 | 1 |
| 4 | 4 | 3 | 1 |
| 5 | 3 | 2 | 1 |
| 6 | 3 | 2 | 0 |
| 7 | 2 | 1 | 0 |
| 8 | 1 | 1 | 0 |
| 9 | 1 | 0 | 0 |
| 10+ | 0 | 0 | 0 |

---

## Guidance for the LLM

1. **Ask questions** to understand the concept before suggesting lifepaths
2. **Ask which Infection phase** the player wants to focus on (Infiltration, Usurpation, Invasion)
3. **Use the solver** to find and validate chains — never trace requirements by hand
4. **Explain tradeoffs** — more lifepaths = older and skilled but less Artha
5. **Show maneuver coverage** alongside stats when presenting chain options
6. **Help with Beliefs** — push for specific, actionable, conflicted Beliefs
7. **Track totals** — keep running tallies of points as lifepaths are chosen
8. **Suggest combinations** — recommend skill/trait synergies for the concept
9. **Reference the setting** — the Iron Empires are desperate, the Vaylen are coming

---

## Reference Data Files

### `human_lifepaths_complete.json`
222 lifepaths across 12 settings with pre-parsed structured requirements. Each lifepath includes:
- Time, Resources, Circles, Stat bonus
- Skill points, skill lists, and general skill point allocation
- Trait points and trait lists
- Structured requirements (requires_any, requires_all, requires_k_of_n, etc.)
- Tags for requirement matching

This is the primary data file used by the solver.

### `maneuver_skills.json`
Maps the 8 Infection maneuvers to their appropriate skills for each of the 3 phases (Infiltration, Usurpation, Invasion). Used by ManeuverData to compute coverage. Includes skill aliases (e.g., "Law" maps to "Imperial Law", "Church Law", etc.).

---

## Example Character Build

**Concept:** Noble-born political operative turned criminal smuggler, focused on Infiltration

**Solver call:**
```python
chains = solver.find_chains("Smuggler", length=6,
    must_include=["Criminal", "Politico"],
    optimize=["maneuvers-inf+", "years-"],
    born_preference="noble", limit=5)
```

**Lifepath Chain:**
1. Born to Rule (Nobility) — 8 yrs, 2 res, 1 cir
2. Student (Commune) — 4 yrs, 0 res, 0 cir
3. Financier (Commune) — 5 yrs, 3 res, 1 cir, +1M
4. Politico (Commune) — 5 yrs, 2 res, 2 cir, +1M/P
5. Criminal (Outcast & Criminal) — 5 yrs, 2 res, 2 cir, +1M/P
6. Smuggler (Outcast & Criminal) — 4 yrs, 1 res, 1 cir

**Total:** 35 years, 10 res, 7 cir, 6 lifepaths
Stats: M:1 P:0 Flex:2 → Age 35 (7M/14P pools)
Artha: 3 Fate / 2 Persona / 0 Deeds
Maneuvers: 15/24 (6/8 Inf, 6/8 Usu, 3/8 Inv)

**Key skills:** Doctrine, Research, History, Finance, Intimidation, Persuasion, Streetwise, Tactics, Smuggling, Rhetoric
**Maneuver coverage (Infiltration):** Assess, Flak, Gambit, Go to Ground, Inundate, Take Action

**Beliefs:**
1. "The Empire betrayed my family; I'll burn their supply lines until they beg for mercy."
2. "My crew is all I have left. I'll die before I let them down like my father did me."
3. "The Vaylen are a myth the nobles use to control us. I'll prove it... or die trying."

**Instincts:**
1. Always have an escape route planned before entering any deal
2. Never let my crew see me show fear
3. When in doubt, bribe first, shoot second
