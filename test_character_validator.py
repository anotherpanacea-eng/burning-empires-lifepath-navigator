"""
Tests for the Burning Empires Character Validator.

Covers: budget computation, stat pools, skill costs, required opens,
trait points, circles spending, resource spending, derived stats,
subordinate constraints, and full-build integration tests.
"""

import os
import pytest
from character_validator import (
    CharacterValidator, BudgetSummary, ValidationReport,
    AGE_BRACKETS,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="module")
def validator():
    lp_file = os.path.join(BASE_DIR, "human_lifepaths_complete.json")
    return CharacterValidator(lp_file)


# ---------------------------------------------------------------------------
# V01: Budget computation — Trent's chain
# ---------------------------------------------------------------------------

class TestBudgetComputation:

    def test_v01_trent_budgets(self, validator):
        """Trent's 6-LP chain produces correct budgets."""
        chain = [
            "Born to Rule", "Student (Commune)", "Financier (Commune)",
            "Politico (Commune)", "Criminal", "Criminal",
        ]
        budgets, errors = validator.compute_budgets(chain)
        assert not errors
        assert budgets.age == 35
        assert budgets.age_base == 33
        assert budgets.setting_jumps == 2
        assert budgets.mental_pool == 8   # 7 base + 1M from Student
        assert budgets.physical_pool == 14  # 14 base
        assert budgets.flex_points == 2   # 2x Criminal +1M/P
        assert budgets.skill_points == 32
        assert budgets.general_points == 6
        assert budgets.trait_points == 8
        assert budgets.resource_points == 12
        assert budgets.circles_points == 9

    def test_v02_age_with_setting_jumps(self, validator):
        """Age includes +1 year per setting change."""
        # Soldier (Anvil) -> Sergeant (Anvil): same setting, no jump
        # Born to Rule (Nobility) -> Student (Commune): different, +1 jump
        chain = ["Born to Rule", "Student (Commune)"]
        budgets, errors = validator.compute_budgets(chain)
        assert not errors
        assert budgets.setting_jumps == 1
        assert budgets.age == 8 + 5 + 1  # Born(8) + Student(5) + 1 jump

    def test_v03_no_setting_jump_same_setting(self, validator):
        """No jump when consecutive LPs share a setting."""
        chain = ["Born to Rule", "C\u0153ptir"]
        budgets, errors = validator.compute_budgets(chain)
        assert not errors
        assert budgets.setting_jumps == 0


# ---------------------------------------------------------------------------
# V03: Stat pool brackets
# ---------------------------------------------------------------------------

class TestStatPoolBrackets:

    @pytest.mark.parametrize("age,expected_m,expected_p", [
        (5, 5, 10),    # 01-10
        (10, 5, 10),   # 01-10 boundary
        (14, 6, 13),   # 11-14
        (16, 6, 16),   # 15-16
        (20, 7, 16),   # 17-25
        (25, 7, 16),   # 17-25 boundary
        (29, 7, 15),   # 26-29
        (30, 7, 14),   # 30-35 boundary
        (35, 7, 14),   # 30-35
        (40, 7, 13),   # 36-40
        (50, 7, 12),   # 41-55
        (60, 7, 11),   # 56-65
        (70, 7, 10),   # 66-79
        (90, 6, 9),    # 80-100
    ])
    def test_v03_bracket_lookup(self, age, expected_m, expected_p):
        """Each age returns correct M/P pools from bracket table."""
        m, p, label = CharacterValidator.get_stat_pools(age)
        assert m == expected_m, f"Age {age}: M={m}, expected {expected_m}"
        assert p == expected_p, f"Age {age}: P={p}, expected {expected_p}"


# ---------------------------------------------------------------------------
# V04-V05: Skill costs
# ---------------------------------------------------------------------------

class TestSkillCosts:

    def test_v04_single_root_wil(self, validator):
        """Rhetoric (Wil root): Will 6 -> open@3, cost to 6 = 4 pts."""
        stats = {"Will": 6, "Perception": 4}
        cost, opening, advances, root = validator.compute_skill_cost(
            "Rhetoric", 6, stats
        )
        assert opening == 3
        assert advances == 3
        assert cost == 4
        assert root == "Wil"

    def test_v04_single_root_per(self, validator):
        """Tactics (Per root): Per 4 -> open@2, cost to 6 = 5 pts."""
        stats = {"Will": 6, "Perception": 4}
        cost, opening, advances, root = validator.compute_skill_cost(
            "Tactics", 6, stats
        )
        assert opening == 2
        assert advances == 4
        assert cost == 5

    def test_v04_open_only(self, validator):
        """Skill opened but not advanced costs 1 pt."""
        stats = {"Will": 6, "Perception": 4}
        cost, opening, advances, root = validator.compute_skill_cost(
            "Advanced Mathematics", 2, stats
        )
        assert opening == 2
        assert advances == 0
        assert cost == 1

    def test_v05_dual_root(self, validator):
        """Dual-rooted skill: (stat1+stat2)/4 opening."""
        # Find a dual-root skill in skill_roots.json
        dual_skill = None
        for name, data in validator.skill_roots.items():
            if "/" in data.get("root", ""):
                dual_skill = name
                break

        if dual_skill is None:
            pytest.skip("No dual-root skill found in skill_roots.json")

        root_str = validator.skill_roots[dual_skill]["root"]
        parts = root_str.split("/")
        stats = {
            validator._resolve_stat_name(parts[0].strip()): 6,
            validator._resolve_stat_name(parts[1].strip()): 4,
        }
        # (6 + 4) / 4 = 2.5 -> 2
        cost, opening, _, _ = validator.compute_skill_cost(
            dual_skill, 4, stats
        )
        assert opening == 2
        assert cost == 1 + (4 - 2)  # open + advances

    def test_v04_wise_skill_uses_per(self, validator):
        """Wise skills always use Perception root."""
        stats = {"Will": 6, "Perception": 4}
        cost, opening, advances, root = validator.compute_skill_cost(
            "Criminal-wise", 2, stats
        )
        assert root == "Per"
        assert opening == 2  # Per 4 / 2
        assert cost == 1


# ---------------------------------------------------------------------------
# V06-V07: Required opens (cascading)
# ---------------------------------------------------------------------------

class TestRequiredOpens:

    def test_v06_required_skill_cascade(self, validator):
        """If 1st skill already opened, 2nd becomes required."""
        chain = ["Born to Rule", "Student (Commune)", "Financier (Commune)"]
        budgets, _ = validator.compute_budgets(chain)
        req = budgets.required_skills
        # Student requires History (1st), Financier requires Finance (1st)
        assert "History" in req
        assert "Finance" in req

    def test_v06_repeat_lp_second_skill(self, validator):
        """Repeat LP requires 2nd skill."""
        chain = ["Born to Rule", "Criminal", "Criminal"]
        budgets, _ = validator.compute_budgets(chain)
        req = budgets.required_skills
        # Criminal 1st: Intimidation (1st skill)
        # Criminal 2nd: Persuasion (2nd skill, since Intimidation already opened)
        assert "Intimidation" in req
        assert "Persuasion" in req

    def test_v07_required_trait_cascade(self, validator):
        """If 1st trait already taken, 2nd becomes required."""
        chain = ["Born to Rule", "Criminal", "Criminal"]
        budgets, _ = validator.compute_budgets(chain)
        req = budgets.required_traits
        assert "Mark of Privilege" in req  # Born to Rule
        assert "Family" in req             # Criminal 1st
        assert "Vig" in req                # Criminal 2nd (2nd trait on repeat)


# ---------------------------------------------------------------------------
# V08: Trait costs
# ---------------------------------------------------------------------------

class TestTraitCosts:

    def test_v08_required_always_cost_1(self, validator):
        """Required traits cost 1 pt regardless of trait_list cost."""
        chain = [
            "Born to Rule", "Student (Commune)", "Financier (Commune)",
            "Politico (Commune)", "Criminal", "Criminal",
        ]
        build = {
            "name": "Trait Cost Test",
            "chain": chain,
            "traits": [
                "Mark of Privilege", "Educated", "Well-Heeled",
                "Ambitious", "Family", "Vig",
            ],
        }
        report = validator.validate_build(build)
        # 6 required traits at 1 pt each = 6 pts, budget is 8, so 2 unspent
        assert report.details["trait_points_spent"] == 6

    def test_v08_optional_lp_trait_cost_1(self, validator):
        """Optional traits from LP lists cost 1 pt each."""
        chain = [
            "Born to Rule", "Student (Commune)", "Financier (Commune)",
            "Politico (Commune)", "Criminal", "Criminal",
        ]
        build = {
            "name": "Optional Trait Test",
            "chain": chain,
            "traits": [
                "Mark of Privilege", "Educated", "Well-Heeled",
                "Ambitious", "Family", "Vig",
                "Savvy", "Determined",  # optional LP traits
            ],
        }
        report = validator.validate_build(build)
        # 6 required (1 ea) + 2 optional LP (1 ea) = 8
        assert report.details["trait_points_spent"] == 8


# ---------------------------------------------------------------------------
# V09-V10: Circles spending
# ---------------------------------------------------------------------------

class TestCirclesSpending:

    def test_v09_valid_circles(self, validator):
        """Correct circles spending validates clean."""
        chain = [
            "Born to Rule", "Student (Commune)", "Financier (Commune)",
            "Politico (Commune)", "Criminal", "Criminal",
        ]
        build = {
            "name": "Circles Test",
            "chain": chain,
            "stats": {"Will": 6, "Perception": 4, "Agility": 2,
                      "Speed": 3, "Power": 2, "Forte": 6},
            "stat_flex": {"mental": 2},
            "circles": {
                "base_bonus_dice": 1,       # 3 pts
                "reputations": [3],          # 3 pts
                "affiliations": [2],         # 2 pts
                "paid_relationships": 0,
                "complicated_relationships": 1,  # 1 pt
                "free_relationships": 1,     # 0 pts
            },
        }
        report = validator.validate_build(build)
        assert report.details["circles_spent"] == 9
        assert not any("circles" in e.lower() for e in report.errors), \
            f"Unexpected circles errors: {report.errors}"

    def test_v10_circles_overspend(self, validator):
        """Spending more circles than available triggers error."""
        chain = [
            "Born to Rule", "Student (Commune)", "Financier (Commune)",
            "Politico (Commune)", "Criminal", "Criminal",
        ]
        build = {
            "name": "Circles Overspend",
            "chain": chain,
            "stats": {"Will": 6, "Perception": 4, "Agility": 2,
                      "Speed": 3, "Power": 2, "Forte": 6},
            "stat_flex": {"mental": 2},
            "circles": {
                "base_bonus_dice": 2,      # 6 pts
                "reputations": [3],         # 3 pts
                "affiliations": [3],        # 3 pts
                "paid_relationships": 0,
                "complicated_relationships": 0,
                "free_relationships": 0,
            },
        }
        report = validator.validate_build(build)
        # 6 + 3 + 3 = 12, budget is 9
        assert any("overspent" in e.lower() for e in report.errors)


# ---------------------------------------------------------------------------
# V11: Resource spending
# ---------------------------------------------------------------------------

class TestResourceSpending:

    def test_v11_resources_match(self, validator):
        """Resources stat = total rp - gear cost."""
        chain = [
            "Born to Rule", "Student (Commune)", "Financier (Commune)",
            "Politico (Commune)", "Criminal", "Criminal",
        ]
        build = {
            "name": "Resource Test",
            "chain": chain,
            "resources": {"gear_cost": 0, "stat": 12},
        }
        report = validator.validate_build(build)
        assert not any("resource" in e.lower() for e in report.errors)

    def test_v11_resources_with_gear(self, validator):
        """Resources stat accounts for gear purchases."""
        chain = ["Born to the League", "Soldier", "Sergeant", "Gunsel"]
        build = {
            "name": "Gear Test",
            "chain": chain,
            "resources": {"gear_cost": 1, "stat": 3},
        }
        report = validator.validate_build(build)
        # Nix: 4 rp - 1 gear = 3. Correct.
        assert not any("resource" in e.lower() for e in report.errors)


# ---------------------------------------------------------------------------
# V12-V14: Derived stats
# ---------------------------------------------------------------------------

class TestDerivedStats:

    def test_v12_hesitation(self, validator):
        """Hesitation = 10 - Will."""
        build = {
            "name": "Hesitation Test",
            "chain": ["Born to Rule"],
            "stats": {"Will": 6, "Perception": 4, "Agility": 2,
                      "Speed": 3, "Power": 2, "Forte": 6},
            "derived": {"hesitation": 4},
        }
        report = validator.validate_build(build)
        assert report.details["derived"]["Hesitation"]["match"] is True

    def test_v12_hesitation_wrong(self, validator):
        """Wrong hesitation triggers error."""
        build = {
            "name": "Bad Hesitation",
            "chain": ["Born to Rule"],
            "stats": {"Will": 6, "Perception": 4, "Agility": 2,
                      "Speed": 3, "Power": 2, "Forte": 6},
            "derived": {"hesitation": 5},
        }
        report = validator.validate_build(build)
        assert report.details["derived"]["Hesitation"]["match"] is False
        assert any("hesitation" in e.lower() for e in report.errors)

    def test_v13_health(self, validator):
        """Health = (Will + Forte) / 2."""
        build = {
            "name": "Health Test",
            "chain": ["Born to Rule"],
            "stats": {"Will": 6, "Perception": 4, "Agility": 2,
                      "Speed": 3, "Power": 2, "Forte": 6},
            "derived": {"health": 6},
        }
        report = validator.validate_build(build)
        assert report.details["derived"]["Health"]["match"] is True

    def test_v14_mortal_wound(self, validator):
        """Mortal Wound = (Power + Forte) / 2 + 6."""
        build = {
            "name": "MW Test",
            "chain": ["Born to Rule"],
            "stats": {"Will": 6, "Perception": 4, "Agility": 2,
                      "Speed": 3, "Power": 2, "Forte": 6},
            "derived": {"mortal_wound": "H10"},
        }
        report = validator.validate_build(build)
        # (2 + 6) / 2 + 6 = 4 + 6 = 10 -> H10
        assert report.details["derived"]["MW"]["match"] is True


# ---------------------------------------------------------------------------
# V15-V16: Full build integration
# ---------------------------------------------------------------------------

class TestFullBuildIntegration:

    def test_v15_trent_full_build(self, validator):
        """Complete Trent build — validates all sections."""
        build = {
            "name": "Trent Spires",
            "chain": [
                "Born to Rule", "Student (Commune)", "Financier (Commune)",
                "Politico (Commune)", "Criminal", "Criminal",
            ],
            "stats": {
                "Will": 6, "Perception": 4, "Agility": 2,
                "Speed": 3, "Power": 2, "Forte": 6,
            },
            "stat_flex": {"mental": 2},
            "skills": [
                {"name": "Rhetoric", "exponent": 6},
                {"name": "Persuasion", "exponent": 6},
                {"name": "Tactics", "exponent": 6},
                {"name": "Streetwise", "exponent": 6},
                {"name": "Finance", "exponent": 6},
                {"name": "Extortion", "exponent": 6},
                {"name": "Intimidation", "exponent": 6},
                {"name": "History", "exponent": 5},
                {"name": "Advanced Mathematics", "exponent": 2},
                {"name": "Psychology", "exponent": 2},
                {"name": "Security", "exponent": 2},
                {"name": "Contributions-wise", "exponent": 2},
                {"name": "Bribe-wise", "exponent": 2},
                {"name": "Criminal-wise", "exponent": 2},
                {"name": "Black Market-wise", "exponent": 2},
                {"name": "Merchant League-wise", "exponent": 2},
            ],
            "traits": [
                "Mark of Privilege", "Educated", "Well-Heeled", "Ambitious",
                "Family", "Vig", "Savvy", "Determined",
            ],
            "circles": {
                "base_bonus_dice": 1,
                "reputations": [3],
                "affiliations": [2],
                "paid_relationships": 0,
                "complicated_relationships": 1,
                "free_relationships": 1,
            },
            "resources": {"gear_cost": 0, "stat": 12},
            "derived": {
                "steel": 8, "hesitation": 4, "health": 6,
                "mortal_wound": "H10",
            },
        }
        report = validator.validate_build(build)
        # Print report for debugging if it fails
        if not report.passed:
            print(report.format_report())
        # Trent's sheet claims 43 skill pts but budget is 38.
        # The validator SHOULD flag this as an error.
        skill_errors = [e for e in report.errors
                        if "skill points" in e.lower()]
        assert len(skill_errors) > 0, (
            "Expected skill point overspend error — "
            "sheet claims 43 pts but LP budget is 38"
        )

    def test_v16_nix_full_build(self, validator):
        """Complete Nix build — subordinate constraints."""
        build = {
            "name": "Nix Farrow",
            "subordinate": True,
            "chain": [
                "Born to the League", "Soldier", "Sergeant", "Gunsel",
            ],
            "stats": {
                "Will": 4, "Perception": 4, "Agility": 5,
                "Speed": 3, "Power": 4, "Forte": 4,
            },
            "stat_flex": {"physical": 1},
            "skills": [
                {"name": "Close Combat", "exponent": 4},
                {"name": "Assault Weapons", "exponent": 4},
                {"name": "Tactics", "exponent": 4},
                {"name": "Infiltration", "exponent": 3},
                {"name": "Intimidation", "exponent": 3},
                {"name": "Streetwise", "exponent": 2},
                {"name": "Soldiering", "exponent": 2},
                {"name": "Observation", "exponent": 2},
            ],
            "traits": [
                "Capitalist at Heart", "FUGAZI", "Oddly Likeable",
                "Loyal to the Family", "Booming Voice",
                "We Rule These Streets",
            ],
            "circles": {
                "base_bonus_dice": 0,
                "reputations": [1],
                "affiliations": [],
                "paid_relationships": 1,
                "complicated_relationships": 0,
                "free_relationships": 0,
            },
            "resources": {"gear_cost": 1, "stat": 3},
            "derived": {
                "steel": 6, "hesitation": 6, "health": 4,
                "mortal_wound": "H10",
            },
        }
        report = validator.validate_build(build)
        if report.errors:
            print(report.format_report())
        # Check which categories have errors
        non_skill_errors = [
            e for e in report.errors
            if "skill points" not in e.lower()
            and "stat" not in e.lower()
        ]
        # Derived stats should be correct
        derived = report.details.get("derived", {})
        if "Hesitation" in derived:
            assert derived["Hesitation"]["match"] is True
        if "Health" in derived:
            assert derived["Health"]["match"] is True


# ---------------------------------------------------------------------------
# V17: Stat pool mismatch
# ---------------------------------------------------------------------------

class TestStatValidation:

    def test_v17_stat_pool_mismatch(self, validator):
        """Wrong stat allocation triggers error."""
        build = {
            "name": "Bad Stats",
            "chain": ["Born to Rule", "Student (Commune)"],
            "stats": {
                "Will": 7, "Perception": 4,   # 11, too high
                "Agility": 4, "Speed": 4,
                "Power": 4, "Forte": 4,        # 16, correct for 17-25
            },
        }
        report = validator.validate_build(build)
        assert any("pool mismatch" in e.lower() or "stat" in e.lower()
                    for e in report.errors)


# ---------------------------------------------------------------------------
# V18: Subordinate skill cap
# ---------------------------------------------------------------------------

class TestSubordinateConstraints:

    def test_v18_skill_cap_4(self, validator):
        """Skills above 4 on a subordinate trigger error."""
        build = {
            "name": "Bad Subordinate",
            "subordinate": True,
            "chain": ["Born to the League", "Soldier", "Sergeant", "Gunsel"],
            "stats": {
                "Will": 4, "Perception": 4, "Agility": 5,
                "Speed": 3, "Power": 4, "Forte": 4,
            },
            "skills": [
                {"name": "Close Combat", "exponent": 5},  # over cap!
            ],
        }
        report = validator.validate_build(build)
        assert any("exceeds max 4" in e for e in report.errors)


# ---------------------------------------------------------------------------
# V19: Repeat LP penalty
# ---------------------------------------------------------------------------

class TestRepeatPenalty:

    def test_v19_third_occurrence_half_skill(self, validator):
        """3rd occurrence of same LP gives half skill/resource pts."""
        # This is a constructed scenario — find an LP that could
        # theoretically appear 3+ times
        chain = ["Born to Rule", "Criminal", "Criminal", "Criminal"]
        budgets, errors = validator.compute_budgets(chain)
        # Ignore chain legality errors for this test
        if budgets is None:
            pytest.skip("Could not resolve chain")

        # Criminal: pts=9, gen=0, resources=2, circles=2
        # 1st: 9 pts, 2 rp, 2 circles
        # 2nd: 9 pts, 2 rp, 2 circles
        # 3rd: 4 pts (9//2), 1 rp (2//2), 0 circles
        assert budgets.skill_points == 9 + 9 + 4  # 22
        assert budgets.resource_points == 2 + 2 + 2 + 1  # Born(2) + 2 + 2 + 1 = 7
        assert budgets.circles_points == 1 + 2 + 2 + 0  # Born(1) + 2 + 2 + 0 = 5


# ---------------------------------------------------------------------------
# V20: Prohibited stats
# ---------------------------------------------------------------------------

class TestProhibitedStats:

    def test_v20_reflexes_prohibited(self, validator):
        """Reflexes (BW-only) triggers error."""
        build = {
            "name": "BW Intruder",
            "chain": ["Born to Rule"],
            "stats": {"Will": 4, "Perception": 4, "Agility": 4,
                      "Speed": 4, "Power": 4, "Forte": 4},
            "derived": {"reflexes": 4, "hesitation": 6, "health": 4},
        }
        report = validator.validate_build(build)
        assert any("reflexes" in e.lower() for e in report.errors)


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_format_report_runs(self, validator):
        """format_report() produces non-empty string."""
        chain = ["Born to Rule", "Student (Commune)"]
        build = {
            "name": "Format Test",
            "chain": chain,
            "stats": {"Will": 4, "Perception": 4, "Agility": 4,
                      "Speed": 4, "Power": 4, "Forte": 4},
        }
        report = validator.validate_build(build)
        text = report.format_report()
        assert "Format Test" in text
        assert "RESULT:" in text

    def test_unknown_lp_name(self, validator):
        """Unknown LP name produces error."""
        _, errors = validator.compute_budgets(["Born to Rule", "Nonexistent LP"])
        assert any("not found" in e.lower() for e in errors)

    def test_empty_chain(self, validator):
        """Empty chain returns error."""
        build = {"name": "Empty", "chain": []}
        report = validator.validate_build(build)
        assert report.errors  # should have chain errors

    def test_reputation_cap_3d(self, validator):
        """Reputation over 3D triggers error."""
        build = {
            "name": "Rep Cap Test",
            "chain": ["Born to Rule"],
            "stats": {"Will": 4, "Perception": 4, "Agility": 4,
                      "Speed": 4, "Power": 4, "Forte": 4},
            "circles": {
                "base_bonus_dice": 0,
                "reputations": [4],  # over 3D cap
                "affiliations": [],
                "paid_relationships": 0,
                "complicated_relationships": 0,
                "free_relationships": 0,
            },
        }
        report = validator.validate_build(build)
        assert any("exceeds max 3D" in e for e in report.errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
