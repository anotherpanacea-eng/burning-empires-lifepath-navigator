"""
Burning Empires Character Validator

Validates point-buy calculations for character builds against game rules.
Catches overspends, missing required skills/traits, stat pool mismatches,
and derived stat errors.

Two modes:
  1. Budget mode: compute_budgets(chain) -> BudgetSummary
  2. Validate mode: validate_build(build_dict) -> ValidationReport
"""

import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set, Any

from lifepath_solver import Lifepath, Chain, LifepathSolver


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Human stat pools by age bracket: (max_age, mental, physical)
AGE_BRACKETS = [
    (10,  5, 10),   # 01-10
    (14,  6, 13),   # 11-14
    (16,  6, 16),   # 15-16
    (25,  7, 16),   # 17-25
    (29,  7, 15),   # 26-29
    (35,  7, 14),   # 30-35
    (40,  7, 13),   # 36-40
    (55,  7, 12),   # 41-55
    (65,  7, 11),   # 56-65
    (79,  7, 10),   # 66-79
    (100, 6,  9),   # 80-100
]

STAT_ABBREVS = {
    "Wil": "Will", "Per": "Perception", "Agi": "Agility",
    "Spd": "Speed", "Pow": "Power", "Frt": "Forte", "For": "Forte",
}

MENTAL_STATS = {"Will", "Perception"}
PHYSICAL_STATS = {"Agility", "Speed", "Power", "Forte"}
PROHIBITED_STATS = {"Reflexes"}  # BW-only, not in BE


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BudgetSummary:
    """Computed point pools from a lifepath chain."""
    age: int
    age_base: int
    setting_jumps: int
    mental_pool: int      # base M from bracket + guaranteed M bonuses
    physical_pool: int    # base P from bracket + guaranteed P bonuses
    flex_points: int      # +M/P bonuses (player chooses)
    mental_bonus: int     # guaranteed +M from LPs
    physical_bonus: int   # guaranteed +P from LPs
    skill_points: int     # LP skill points
    general_points: int   # general skill points
    trait_points: int
    resource_points: int
    circles_points: int
    required_skills: List[str]
    required_traits: List[str]
    bracket_label: str


@dataclass
class ValidationReport:
    """Results of validating a character build."""
    name: str
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    budgets: Optional[BudgetSummary] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def format_report(self) -> str:
        """Human-readable validation report."""
        lines = []
        lines.append(f"=== Validation Report: {self.name} ===")

        if self.budgets:
            b = self.budgets
            chain_str = " -> ".join(self.details.get("chain_display", []))
            lines.append(f"CHAIN: {chain_str}")

            base_m = b.mental_pool - b.mental_bonus
            base_p = b.physical_pool - b.physical_bonus
            lines.append(
                f"AGE: {b.age} ({b.age_base} base + {b.setting_jumps} jumps) "
                f"-- bracket {b.bracket_label}: M{base_m} P{base_p}"
            )
            lines.append("")

            # Stats
            m_total = self.details.get("mental_spent", "?")
            p_total = self.details.get("physical_spent", "?")
            m_target = self.details.get("mental_target", "?")
            p_target = self.details.get("physical_target", "?")
            stat_ok = not any("pool mismatch" in e.lower() or "stat" in e.lower()
                             for e in self.errors)
            s_mark = "OK" if stat_ok else "FAIL"
            lines.append(f"STATS: Mental {m_total}/{m_target} | Physical {p_total}/{p_target} [{s_mark}]")
            lines.append("")

            # Skills
            total_skill = b.skill_points + b.general_points
            skill_spent = self.details.get("skill_points_spent", "?")
            sk_mark = "OK" if skill_spent == total_skill else "FAIL"
            lines.append(
                f"SKILLS: {skill_spent}/{total_skill} pts [{sk_mark}] "
                f"({b.skill_points} LP + {b.general_points} general)"
            )
            for sd in self.details.get("skill_details", []):
                mark = "  ok" if sd.get("valid") else "  FAIL"
                lines.append(
                    f"  {sd['name']}: open@{sd['opening']} +{sd['advances']} "
                    f"= {sd['cost']} pts -> exponent {sd['exponent']}{mark}"
                )
            req_skills = self.details.get("required_skills_status", {})
            if req_skills:
                missing = [k for k, v in req_skills.items() if not v]
                if missing:
                    lines.append(f"  Required skills MISSING: {', '.join(missing)}")
                else:
                    lines.append("  Required skills: all opened")
            lines.append("")

            # Traits
            trait_spent = self.details.get("trait_points_spent", "?")
            t_mark = "OK" if trait_spent == b.trait_points else "FAIL"
            lines.append(f"TRAITS: {trait_spent}/{b.trait_points} pts [{t_mark}]")
            req_traits = self.details.get("required_traits_status", {})
            if req_traits:
                missing = [k for k, v in req_traits.items() if not v]
                if missing:
                    lines.append(f"  Required traits MISSING: {', '.join(missing)}")
                else:
                    lines.append("  Required traits: all taken")
            lines.append("")

            # Circles
            circles_spent = self.details.get("circles_spent", "?")
            c_mark = "OK" if circles_spent == b.circles_points else "FAIL"
            lines.append(f"CIRCLES: {circles_spent}/{b.circles_points} pts [{c_mark}]")

            # Resources
            rp_ok = not any("resource" in e.lower() for e in self.errors)
            r_mark = "OK" if rp_ok else "FAIL"
            lines.append(f"RESOURCES: {b.resource_points} rp [{r_mark}]")
            lines.append("")

            # Derived
            derived = self.details.get("derived", {})
            if derived:
                parts = []
                for dname, vals in derived.items():
                    if vals.get("expected") is not None:
                        check = "OK" if vals.get("match") else "FAIL"
                        parts.append(f"{dname} {vals.get('declared','?')} [{check}]")
                    else:
                        parts.append(f"{dname} {vals.get('declared','?')}")
                lines.append(f"DERIVED: {' | '.join(parts)}")
                lines.append("")

        result = "PASS" if self.passed else "FAIL"
        lines.append(
            f"RESULT: {result} ({len(self.errors)} errors, {len(self.warnings)} warnings)"
        )

        if self.errors:
            lines.append("")
            lines.append("ERRORS:")
            for e in self.errors:
                lines.append(f"  * {e}")

        if self.warnings:
            lines.append("")
            lines.append("WARNINGS:")
            for w in self.warnings:
                lines.append(f"  - {w}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class CharacterValidator:
    """Validates Burning Empires character builds against game rules."""

    def __init__(self, lp_file: str,
                 skill_roots_file: str = None,
                 trait_list_file: str = None):
        """Initialize with reference data files.

        Args:
            lp_file: Path to human_lifepaths_complete.json
            skill_roots_file: Path to skill_roots.json (auto-detected if None)
            trait_list_file: Path to trait_list.json (auto-detected if None)
        """
        self.solver = LifepathSolver(lp_file)
        base_dir = os.path.dirname(os.path.abspath(lp_file))

        sr_path = skill_roots_file or os.path.join(base_dir, "skill_roots.json")
        self.skill_roots: Dict[str, Dict] = {}
        if os.path.exists(sr_path):
            with open(sr_path) as f:
                self.skill_roots = json.load(f)

        tl_path = trait_list_file or os.path.join(base_dir, "trait_list.json")
        self.trait_list: Dict[str, Dict] = {}
        if os.path.exists(tl_path):
            with open(tl_path) as f:
                self.trait_list = json.load(f)

    # ------------------------------------------------------------------
    # Chain resolution
    # ------------------------------------------------------------------

    def _resolve_chain(self, chain_names: List[str]) -> Tuple[List[Lifepath], List[str]]:
        """Resolve LP names to Lifepath objects.

        Handles setting-qualified names like 'Student (Commune)' and
        repeat LPs.
        """
        resolved = []
        errors = []

        for i, name in enumerate(chain_names):
            setting = None
            clean_name = name
            if "(" in name and ")" in name:
                idx = name.index("(")
                clean_name = name[:idx].strip()
                setting = name[idx + 1:name.index(")")].strip()

            candidates = self.solver.by_name.get(clean_name, [])
            if not candidates:
                for lp_name, lps in self.solver.by_name.items():
                    if lp_name.lower() == clean_name.lower():
                        candidates = lps
                        break

            if not candidates:
                errors.append(f"LP not found: '{name}'")
                continue

            if setting:
                filtered = [lp for lp in candidates
                            if lp.setting.lower() == setting.lower()]
                if filtered:
                    candidates = filtered
                else:
                    errors.append(
                        f"LP '{clean_name}' not found in setting '{setting}'"
                    )
                    continue

            if i == 0:
                born = [lp for lp in candidates if lp.is_born]
                if born:
                    candidates = born

            resolved.append(candidates[0])

        return resolved, errors

    # ------------------------------------------------------------------
    # Budget computations
    # ------------------------------------------------------------------

    @staticmethod
    def get_stat_pools(age: int) -> Tuple[int, int, str]:
        """Look up base Mental and Physical pools for an age bracket.

        Returns: (mental, physical, bracket_label)
        """
        prev_max = 0
        for max_age, mental, physical in AGE_BRACKETS:
            if age <= max_age:
                low = prev_max + 1
                label = f"{low:02d}-{max_age}"
                return mental, physical, label
            prev_max = max_age
        return 6, 9, "80-100"

    @staticmethod
    def _parse_stat_bonuses(lifepaths: List[Lifepath]) -> Tuple[int, int, int]:
        """Parse stat bonuses, respecting 3rd+ repeat penalty (no stat).

        Returns: (mental_bonus, physical_bonus, flex_bonus)
        """
        mental = physical = flex = 0
        counts: Dict[int, int] = {}

        for lp in lifepaths:
            counts[lp.uid] = counts.get(lp.uid, 0) + 1
            if counts[lp.uid] >= 3:
                continue
            stat = (lp.stat or "").strip()
            if stat in ("", "\u2014", "-"):
                continue
            if stat in ("+1M", "+1 M"):
                mental += 1
            elif stat in ("+1P", "+1 P"):
                physical += 1
            elif stat in ("+1M/P", "+1 M/P"):
                flex += 1
            elif stat in ("+1M,P", "+1 M,P", "+1M, P", "+1 M, P"):
                mental += 1
                physical += 1

        return mental, physical, flex

    @staticmethod
    def _compute_skill_points(lifepaths: List[Lifepath]) -> Tuple[int, int]:
        """Total (lp_skill_points, general_points), with 3rd+ repeat penalty."""
        lp_pts = gen_pts = 0
        counts: Dict[int, int] = {}

        for lp in lifepaths:
            counts[lp.uid] = counts.get(lp.uid, 0) + 1
            pts = lp.skills.get("points", 0)
            gen = lp.skills.get("general", 0)
            if counts[lp.uid] >= 3:
                pts = pts // 2
                gen = gen // 2
            lp_pts += pts
            gen_pts += gen

        return lp_pts, gen_pts

    @staticmethod
    def _compute_trait_points(lifepaths: List[Lifepath]) -> int:
        """Total trait points (not reduced on repeats)."""
        return sum(lp.traits.get("points", 0) for lp in lifepaths)

    @staticmethod
    def _compute_resource_points(lifepaths: List[Lifepath]) -> int:
        """Total resource points, with 3rd+ repeat penalty (half)."""
        total = 0
        counts: Dict[int, int] = {}
        for lp in lifepaths:
            counts[lp.uid] = counts.get(lp.uid, 0) + 1
            rp = lp.resources
            if counts[lp.uid] >= 3:
                rp = rp // 2
            total += rp
        return total

    @staticmethod
    def _compute_circles_points(lifepaths: List[Lifepath]) -> int:
        """Total circles points, with 3rd+ repeat penalty (none)."""
        total = 0
        counts: Dict[int, int] = {}
        for lp in lifepaths:
            counts[lp.uid] = counts.get(lp.uid, 0) + 1
            if counts[lp.uid] >= 3:
                continue
            total += lp.circles
        return total

    @staticmethod
    def _compute_age(lifepaths: List[Lifepath]) -> Tuple[int, int, int]:
        """Returns (total_age, base_years, setting_jumps)."""
        base = sum(lp.time for lp in lifepaths)
        jumps = sum(
            1 for i in range(1, len(lifepaths))
            if lifepaths[i].setting != lifepaths[i - 1].setting
        )
        return base + jumps, base, jumps

    @staticmethod
    def _compute_required_skills(lifepaths: List[Lifepath]) -> List[str]:
        """Required skills: 1st per LP (cascading), 2nd on repeats."""
        required: List[str] = []
        opened: Set[str] = set()
        counts: Dict[int, int] = {}

        for lp in lifepaths:
            counts[lp.uid] = counts.get(lp.uid, 0) + 1
            skill_list = lp.skills.get("list", [])
            # Filter out "General" pseudo-entries
            skill_list = [s for s in skill_list if s != "General"]
            if not skill_list:
                continue

            start = 1 if counts[lp.uid] >= 2 else 0
            for idx in range(start, len(skill_list)):
                skill = skill_list[idx]
                if skill not in opened:
                    required.append(skill)
                    opened.add(skill)
                    break

        return required

    @staticmethod
    def _compute_required_traits(lifepaths: List[Lifepath]) -> List[str]:
        """Required traits: 1st per LP (cascading), 2nd on repeats."""
        required: List[str] = []
        taken: Set[str] = set()
        counts: Dict[int, int] = {}

        for lp in lifepaths:
            counts[lp.uid] = counts.get(lp.uid, 0) + 1
            trait_list = lp.traits.get("list", [])
            if not trait_list:
                continue

            start = 1 if counts[lp.uid] >= 2 else 0
            for idx in range(start, len(trait_list)):
                trait = trait_list[idx]
                if trait not in taken:
                    required.append(trait)
                    taken.add(trait)
                    break

        return required

    @staticmethod
    def _get_all_lp_traits(lifepaths: List[Lifepath]) -> Set[str]:
        """All traits on any LP's trait list."""
        return {t for lp in lifepaths for t in lp.traits.get("list", [])}

    @staticmethod
    def _get_all_lp_skills(lifepaths: List[Lifepath]) -> Set[str]:
        """All skills on any LP's skill list (excluding 'General')."""
        return {
            s for lp in lifepaths
            for s in lp.skills.get("list", [])
            if s != "General"
        }

    def _resolve_stat_name(self, abbrev: str) -> str:
        return STAT_ABBREVS.get(abbrev, abbrev)

    def _compute_opening_exponent(
        self, skill_name: str, stats: Dict[str, int]
    ) -> Tuple[int, str]:
        """Compute opening exponent for a skill.

        Returns: (opening_exponent, root_description)
        """
        # Wise skills always use Perception
        if skill_name.endswith("-wise") or skill_name.endswith("-wise."):
            per_val = stats.get("Perception", 4)
            return max(per_val // 2, 1), "Per"

        # Look up in skill_roots
        root_data = self.skill_roots.get(skill_name)
        if not root_data:
            # Try case-insensitive, strip trailing punctuation
            clean = skill_name.rstrip(".")
            for k, v in self.skill_roots.items():
                if k.lower() == clean.lower():
                    root_data = v
                    break

        if not root_data:
            per_val = stats.get("Perception", 4)
            return max(per_val // 2, 1), "unknown"

        root_str = root_data.get("root", "Per")
        if "/" in root_str:
            parts = root_str.split("/")
            s1 = self._resolve_stat_name(parts[0].strip())
            s2 = self._resolve_stat_name(parts[1].strip())
            v1 = stats.get(s1, 4)
            v2 = stats.get(s2, 4)
            opening = (v1 + v2) // 4
            return max(opening, 1), root_str
        else:
            stat_name = self._resolve_stat_name(root_str.strip())
            val = stats.get(stat_name, 4)
            return max(val // 2, 1), root_str

    def compute_skill_cost(
        self, skill_name: str, exponent: int, stats: Dict[str, int]
    ) -> Tuple[int, int, int, str]:
        """Compute point cost for a skill at given exponent.

        Returns: (total_cost, opening_exponent, advances, root_description)
        """
        opening, root = self._compute_opening_exponent(skill_name, stats)
        advances = max(exponent - opening, 0)
        total = 1 + advances
        return total, opening, advances, root

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_budgets(
        self, chain_names: List[str]
    ) -> Tuple[Optional[BudgetSummary], List[str]]:
        """Compute all point budgets from a lifepath chain.

        Returns: (BudgetSummary or None, list of errors)
        """
        lifepaths, errors = self._resolve_chain(chain_names)
        if errors:
            return None, errors

        age, age_base, jumps = self._compute_age(lifepaths)
        base_m, base_p, bracket = self.get_stat_pools(age)
        m_bonus, p_bonus, flex = self._parse_stat_bonuses(lifepaths)
        lp_skill, gen_skill = self._compute_skill_points(lifepaths)
        trait_pts = self._compute_trait_points(lifepaths)
        rp = self._compute_resource_points(lifepaths)
        circles = self._compute_circles_points(lifepaths)
        req_skills = self._compute_required_skills(lifepaths)
        req_traits = self._compute_required_traits(lifepaths)

        budget = BudgetSummary(
            age=age,
            age_base=age_base,
            setting_jumps=jumps,
            mental_pool=base_m + m_bonus,
            physical_pool=base_p + p_bonus,
            flex_points=flex,
            mental_bonus=m_bonus,
            physical_bonus=p_bonus,
            skill_points=lp_skill,
            general_points=gen_skill,
            trait_points=trait_pts,
            resource_points=rp,
            circles_points=circles,
            required_skills=req_skills,
            required_traits=req_traits,
            bracket_label=bracket,
        )
        return budget, []

    def validate_build(self, build: Dict) -> ValidationReport:
        """Validate a complete character build.

        Args:
            build: Character build dict with keys:
                chain, stats, skills, traits, circles, resources, derived,
                subordinate (bool), stat_flex (optional)
        """
        name = build.get("name", "Unknown")
        report = ValidationReport(name=name, passed=True)

        chain_names = build.get("chain", [])
        lifepaths, chain_errors = self._resolve_chain(chain_names)
        if chain_errors:
            report.errors.extend(chain_errors)
            report.passed = False
            return report

        report.details["chain_display"] = [lp.key for lp in lifepaths]

        budgets, budget_errors = self.compute_budgets(chain_names)
        if budget_errors:
            report.errors.extend(budget_errors)
            report.passed = False
            return report
        report.budgets = budgets

        self._check_chain(lifepaths, build, report)

        stats = build.get("stats", {})
        if stats:
            self._check_stats(stats, budgets, build, report)

        skills = build.get("skills", [])
        if skills:
            self._check_skills(skills, stats, lifepaths, budgets, build, report)

        traits = build.get("traits", [])
        if traits:
            self._check_traits(traits, lifepaths, budgets, report)

        circles = build.get("circles")
        if circles:
            self._check_circles(circles, stats, budgets, report)

        resources = build.get("resources")
        if resources:
            self._check_resources(resources, budgets, report)

        derived = build.get("derived")
        if derived:
            self._check_derived(derived, stats, report)
            for prohibited in PROHIBITED_STATS:
                if prohibited.lower() in {k.lower() for k in derived}:
                    report.errors.append(
                        f"Prohibited stat '{prohibited}' "
                        f"(BW-only, not in Burning Empires)"
                    )

        report.passed = len(report.errors) == 0
        return report

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_chain(self, lifepaths, build, report):
        if not lifepaths:
            report.errors.append("Empty lifepath chain")
            return
        if not lifepaths[0].is_born:
            report.errors.append(
                f"First LP '{lifepaths[0].name}' is not a Born lifepath"
            )
        is_sub = build.get("subordinate", False)
        min_len = 3 if is_sub else 5
        max_len = 6 if is_sub else 8
        if len(lifepaths) < min_len:
            report.warnings.append(
                f"Chain length {len(lifepaths)} below minimum ({min_len})"
            )
        if len(lifepaths) > max_len:
            report.warnings.append(
                f"Chain length {len(lifepaths)} exceeds maximum ({max_len})"
            )

    def _check_stats(self, stats, budgets, build, report):
        for sname, val in stats.items():
            if val < 1:
                report.errors.append(f"{sname} is {val} -- minimum is 1")
            if val > 8:
                report.errors.append(f"{sname} is {val} -- maximum is 8")

        will = stats.get("Will", 0)
        per = stats.get("Perception", 0)
        mental_spent = will + per

        agi = stats.get("Agility", 0)
        spd = stats.get("Speed", 0)
        pow_ = stats.get("Power", 0)
        forte = stats.get("Forte", 0)
        physical_spent = agi + spd + pow_ + forte

        flex = budgets.flex_points
        stat_flex = build.get("stat_flex", {})
        flex_m = stat_flex.get("mental", 0)
        flex_p = stat_flex.get("physical", 0)

        # If flex allocation not specified, try to infer
        if flex > 0 and (flex_m + flex_p) != flex:
            for m in range(flex + 1):
                p = flex - m
                if (mental_spent == budgets.mental_pool + m and
                        physical_spent == budgets.physical_pool + p):
                    flex_m, flex_p = m, p
                    break
            else:
                report.errors.append(
                    f"Stat pools don't match any flex allocation. "
                    f"Mental: {mental_spent} (base {budgets.mental_pool}), "
                    f"Physical: {physical_spent} (base {budgets.physical_pool}), "
                    f"flex: {flex}"
                )
                report.details["mental_spent"] = mental_spent
                report.details["physical_spent"] = physical_spent
                report.details["mental_target"] = f"{budgets.mental_pool}+?"
                report.details["physical_target"] = f"{budgets.physical_pool}+?"
                return

        target_m = budgets.mental_pool + flex_m
        target_p = budgets.physical_pool + flex_p

        report.details["mental_spent"] = mental_spent
        report.details["physical_spent"] = physical_spent
        report.details["mental_target"] = target_m
        report.details["physical_target"] = target_p

        if mental_spent != target_m:
            report.errors.append(
                f"Mental pool mismatch: Will {will} + Per {per} = {mental_spent}, "
                f"expected {target_m} "
                f"(base {budgets.mental_pool - budgets.mental_bonus} "
                f"+ {budgets.mental_bonus}M bonus + {flex_m} flex)"
            )
        if physical_spent != target_p:
            report.errors.append(
                f"Physical pool mismatch: Agi {agi} + Spd {spd} + Pow {pow_} "
                f"+ Forte {forte} = {physical_spent}, expected {target_p} "
                f"(base {budgets.physical_pool - budgets.physical_bonus} "
                f"+ {budgets.physical_bonus}P bonus + {flex_p} flex)"
            )

    def _check_skills(self, skills, stats, lifepaths, budgets, build, report):
        is_sub = build.get("subordinate", False)
        max_exp = 4 if is_sub else 6

        total_cost = 0
        skill_details = []
        skill_names: Set[str] = set()

        for skill in skills:
            s_name = skill.get("name", "?")
            s_exp = skill.get("exponent", 0)
            skill_names.add(s_name)

            if s_exp > max_exp:
                report.errors.append(
                    f"Skill '{s_name}' exponent {s_exp} exceeds max {max_exp}"
                )
            if s_exp < 1:
                report.errors.append(
                    f"Skill '{s_name}' exponent {s_exp} below minimum 1"
                )
                continue

            cost, opening, advances, root = self.compute_skill_cost(
                s_name, s_exp, stats
            )
            total_cost += cost

            if root == "unknown":
                report.warnings.append(
                    f"Skill '{s_name}' not in skill_roots.json "
                    f"-- using Per root as default"
                )

            skill_details.append({
                "name": s_name,
                "exponent": s_exp,
                "opening": opening,
                "advances": advances,
                "cost": cost,
                "root": root,
                "valid": True,
            })

        report.details["skill_details"] = skill_details
        report.details["skill_points_spent"] = total_cost

        total_available = budgets.skill_points + budgets.general_points
        if total_cost != total_available:
            direction = "overspent" if total_cost > total_available else "underspent"
            diff = abs(total_cost - total_available)
            report.errors.append(
                f"Skill points {direction} by {diff}: "
                f"spent {total_cost}, available {total_available} "
                f"({budgets.skill_points} LP + {budgets.general_points} general)"
            )

        # Required skills
        req_status = {}
        for req_skill in budgets.required_skills:
            found = req_skill in skill_names
            if not found:
                found = any(s.lower() == req_skill.lower() for s in skill_names)
            req_status[req_skill] = found
            if not found:
                report.errors.append(f"Required skill '{req_skill}' not opened")
        report.details["required_skills_status"] = req_status

    def _check_traits(self, traits, lifepaths, budgets, report):
        required_set = set(budgets.required_traits)
        lp_traits = self._get_all_lp_traits(lifepaths)

        total_cost = 0
        for trait_name in traits:
            if trait_name in required_set:
                total_cost += 1
            elif trait_name in lp_traits:
                total_cost += 1
            else:
                trait_data = self.trait_list.get(trait_name)
                if trait_data:
                    total_cost += trait_data.get("cost", 1)
                else:
                    total_cost += 1
                    report.warnings.append(
                        f"Trait '{trait_name}' not in trait_list.json "
                        f"-- assuming cost 1"
                    )

        report.details["trait_points_spent"] = total_cost

        if total_cost > budgets.trait_points:
            report.errors.append(
                f"Trait points overspent: {total_cost} spent, "
                f"{budgets.trait_points} available"
            )
        elif total_cost < budgets.trait_points:
            report.warnings.append(
                f"Trait points underspent: {total_cost}/{budgets.trait_points} "
                f"({budgets.trait_points - total_cost} unspent)"
            )

        req_status = {}
        trait_set = set(traits)
        for req in budgets.required_traits:
            found = req in trait_set
            if not found:
                found = any(t.lower() == req.lower() for t in trait_set)
            req_status[req] = found
            if not found:
                report.errors.append(f"Required trait '{req}' not taken")
        report.details["required_traits_status"] = req_status

    def _check_circles(self, circles, stats, budgets, report):
        will = stats.get("Will", 4)
        base_circles = will // 2
        report.details["base_circles"] = base_circles

        base_bonus = circles.get("base_bonus_dice", 0) * 3
        rep_cost = sum(circles.get("reputations", []))
        aff_cost = sum(circles.get("affiliations", []))
        paid_rel = circles.get("paid_relationships", 0) * 2
        comp_rel = circles.get("complicated_relationships", 0) * 1
        total_spent = base_bonus + rep_cost + aff_cost + paid_rel + comp_rel

        report.details["circles_spent"] = total_spent

        for rep in circles.get("reputations", []):
            if rep > 3:
                report.errors.append(f"Reputation {rep}D exceeds max 3D")
        for aff in circles.get("affiliations", []):
            if aff > 3:
                report.errors.append(f"Affiliation {aff}D exceeds max 3D")

        if total_spent > budgets.circles_points:
            report.errors.append(
                f"Circles overspent: {total_spent} spent, "
                f"{budgets.circles_points} available"
            )
        elif total_spent < budgets.circles_points:
            report.warnings.append(
                f"Circles underspent: {total_spent}/{budgets.circles_points}"
            )

    def _check_resources(self, resources, budgets, report):
        gear_cost = resources.get("gear_cost", 0)
        stat = resources.get("stat", 0)
        expected = budgets.resource_points - gear_cost
        if stat != expected:
            report.errors.append(
                f"Resources stat: declared {stat}, expected {expected} "
                f"({budgets.resource_points} rp - {gear_cost} gear)"
            )

    def _check_derived(self, derived, stats, report):
        will = stats.get("Will", 0)
        forte = stats.get("Forte", 0)
        power = stats.get("Power", 0)

        derived_details = {}

        if "hesitation" in derived:
            expected = 10 - will
            declared = derived["hesitation"]
            match = declared == expected
            derived_details["Hesitation"] = {
                "expected": expected, "declared": declared, "match": match,
            }
            if not match:
                report.errors.append(
                    f"Hesitation: declared {declared}, "
                    f"expected {expected} (10 - Will {will})"
                )

        if "health" in derived:
            expected = (will + forte) // 2
            declared = derived["health"]
            match = declared == expected
            derived_details["Health"] = {
                "expected": expected, "declared": declared, "match": match,
            }
            if not match:
                report.errors.append(
                    f"Health: declared {declared}, "
                    f"expected {expected} ((Will {will} + Forte {forte}) / 2)"
                )

        if "mortal_wound" in derived:
            expected_num = (power + forte) // 2 + 6
            expected = f"H{expected_num}"
            declared = derived["mortal_wound"]
            match = declared == expected
            derived_details["MW"] = {
                "expected": expected, "declared": declared, "match": match,
            }
            if not match:
                report.errors.append(
                    f"Mortal Wound: declared {declared}, expected {expected} "
                    f"((Power {power} + Forte {forte}) / 2 + 6)"
                )

        if "steel" in derived:
            declared = derived["steel"]
            if declared < 1 or declared > 10:
                report.errors.append(
                    f"Steel {declared} out of plausible range (1-10)"
                )
            derived_details["Steel"] = {
                "expected": None, "declared": declared, "match": None,
            }

        report.details["derived"] = derived_details


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python character_validator.py <build.json>")
        print("  python character_validator.py --budgets <LP1> <LP2> ...")
        sys.exit(1)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    lp_file = os.path.join(base_dir, "human_lifepaths_complete.json")
    validator = CharacterValidator(lp_file)

    if sys.argv[1] == "--budgets":
        chain = sys.argv[2:]
        budgets, errors = validator.compute_budgets(chain)
        if errors:
            for e in errors:
                print(f"  ERROR: {e}")
            sys.exit(1)
        b = budgets
        print("=== Budget Summary ===")
        print(f"Chain: {' -> '.join(chain)}")
        print(f"Age: {b.age} ({b.age_base} base + {b.setting_jumps} jumps)")
        print(f"Bracket: {b.bracket_label} -- M{b.mental_pool - b.mental_bonus} P{b.physical_pool - b.physical_bonus}")
        print(f"Stat bonuses: +{b.mental_bonus}M +{b.physical_bonus}P +{b.flex_points}flex")
        print(f"Skills: {b.skill_points} LP + {b.general_points} gen = {b.skill_points + b.general_points}")
        print(f"Traits: {b.trait_points} pts")
        print(f"Resources: {b.resource_points} rp")
        print(f"Circles: {b.circles_points} pts")
        print(f"Required skills: {', '.join(b.required_skills) or '(none)'}")
        print(f"Required traits: {', '.join(b.required_traits) or '(none)'}")
    else:
        with open(sys.argv[1]) as f:
            build = json.load(f)
        report = validator.validate_build(build)
        print(report.format_report())
        sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
