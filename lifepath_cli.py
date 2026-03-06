#!/usr/bin/env python3
"""
Burning Empires Lifepath Navigator - Interactive CLI

An interactive questionnaire for finding optimal lifepath chains.
"""

import os
import sys
import json
from typing import List, Optional, Tuple, Dict
from lifepath_solver import LifepathSolver, Chain, ManeuverData


def load_canonical_chains(solver=None) -> Dict:
    """Load pre-computed canonical chains (from solver or separate file)"""
    # First try to get from solver (consolidated format)
    if solver and hasattr(solver, 'canonical_chains') and solver.canonical_chains:
        return solver.canonical_chains

    # Fall back to separate file
    canonical_path = os.path.join(os.path.dirname(__file__), "canonical_chains.json")
    if os.path.exists(canonical_path):
        try:
            with open(canonical_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Print the application header"""
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║{Colors.BOLD}        BURNING EMPIRES LIFEPATH NAVIGATOR                    {Colors.RESET}{Colors.CYAN}║
║{Colors.DIM}                  Interactive Chain Builder                    {Colors.RESET}{Colors.CYAN}║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
""")


def print_divider():
    print(f"{Colors.DIM}{'─' * 64}{Colors.RESET}")


def get_input(prompt: str, default: str = None) -> str:
    """Get user input with optional default"""
    if default:
        prompt = f"{prompt} [{Colors.DIM}{default}{Colors.RESET}]: "
    else:
        prompt = f"{prompt}: "

    result = input(f"{Colors.YELLOW}{prompt}{Colors.RESET}").strip()
    return result if result else (default or "")


def get_choice(prompt: str, options: List[Tuple[str, str]], allow_none: bool = False) -> Optional[str]:
    """Display numbered options and get user choice"""
    print(f"\n{Colors.BOLD}{prompt}{Colors.RESET}")

    for i, (value, description) in enumerate(options, 1):
        print(f"  {Colors.CYAN}{i}.{Colors.RESET} {description}")

    if allow_none:
        print(f"  {Colors.DIM}Enter = skip{Colors.RESET}")

    while True:
        choice = input(f"{Colors.YELLOW}Choice: {Colors.RESET}").strip()

        if not choice and allow_none:
            return None

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        except ValueError:
            pass

        print(f"{Colors.RED}Please enter 1-{len(options)}{Colors.RESET}")


def get_settings_list(prompt: str, available: List[str], max_count: int = 3) -> List[str]:
    """Get a list of settings from user (up to max_count)"""
    print(f"\n{Colors.BOLD}{prompt}{Colors.RESET}")
    print(f"{Colors.DIM}Available: {', '.join(available[:12])}...{Colors.RESET}")
    print(f"{Colors.DIM}Enter up to {max_count}, comma-separated, or press Enter to skip{Colors.RESET}")

    result = input(f"{Colors.YELLOW}Settings: {Colors.RESET}").strip()

    if not result:
        return []

    settings = [s.strip() for s in result.split(',')][:max_count]

    # Validate against available settings (partial match)
    validated = []
    for s in settings:
        matches = [a for a in available if s.lower() in a.lower()]
        if matches:
            validated.append(s)
        else:
            print(f"{Colors.RED}Warning: '{s}' doesn't match any setting, skipping{Colors.RESET}")

    return validated


def get_lifepath_list(prompt: str, solver, max_count: int = 3) -> List[str]:
    """Get a list of lifepaths from user (up to max_count) with fuzzy matching"""
    print(f"\n{Colors.BOLD}{prompt}{Colors.RESET}")
    print(f"{Colors.DIM}Examples: Criminal, Soldier, Merchant, Cotar{Colors.RESET}")
    print(f"{Colors.DIM}Enter up to {max_count}, comma-separated, or press Enter to skip{Colors.RESET}")

    result = input(f"{Colors.YELLOW}Lifepaths: {Colors.RESET}").strip()

    if not result:
        return []

    requested = [s.strip() for s in result.split(',')][:max_count]
    validated = []

    for name in requested:
        # Exact match first
        if name in solver.by_name:
            validated.append(name)
            continue

        # Fuzzy match
        matches = [n for n in solver.by_name.keys() if name.lower() in n.lower()]
        if len(matches) == 1:
            validated.append(matches[0])
            print(f"{Colors.DIM}  '{name}' → {matches[0]}{Colors.RESET}")
        elif len(matches) > 1:
            print(f"\n{Colors.YELLOW}'{name}' matches multiple lifepaths:{Colors.RESET}")
            for i, m in enumerate(matches[:5], 1):
                print(f"  {i}. {m}")
            choice = input(f"{Colors.YELLOW}Choice (or Enter to skip): {Colors.RESET}").strip()
            try:
                validated.append(matches[int(choice) - 1])
            except (ValueError, IndexError):
                print(f"{Colors.DIM}Skipping '{name}'{Colors.RESET}")
        else:
            print(f"{Colors.RED}Warning: '{name}' not found, skipping{Colors.RESET}")

    return validated


def display_chain(chain: Chain, index: int, show_details: bool = True, maneuver_data=None):
    """Display a single chain result"""
    path = ' → '.join(f"{lp.name}" for lp in chain.lifepaths)
    m, p, f = chain.get_stats()
    net_traits, total_traits, req_traits = chain.get_net_trait_points()

    print(f"\n{Colors.GREEN}{Colors.BOLD}{index}.{Colors.RESET} {path}")

    if show_details:
        stats_str = f"M:{m} P:{p} Flex:{f}"
        print(f"   {Colors.CYAN}Stats:{Colors.RESET} {stats_str}  "
              f"{Colors.CYAN}Res:{Colors.RESET} {chain.total_resources}  "
              f"{Colors.CYAN}Circ:{Colors.RESET} {chain.total_circles}  "
              f"{Colors.CYAN}Traits:{Colors.RESET} {net_traits} net  "
              f"{Colors.CYAN}Years:{Colors.RESET} {chain.total_years}")

        if maneuver_data:
            skills = chain.get_skills()
            coverage = maneuver_data.compute_coverage(skills)
            _, general_pts = chain.get_skill_points()
            coverage_str = maneuver_data.format_coverage(coverage)
            gen_str = f"  {Colors.DIM}({general_pts} general skill pts){Colors.RESET}" if general_pts else ""
            print(f"   {Colors.CYAN}Maneuvers:{Colors.RESET} {coverage_str}{gen_str}")

        if chain.warnings:
            for w in chain.warnings[:2]:
                # Color based on warning type
                if w.startswith('❌'):
                    print(f"   {Colors.RED}{w}{Colors.RESET}")
                else:
                    print(f"   {Colors.YELLOW}{w}{Colors.RESET}")


def display_results(chains: List[Chain], limit: int = 10, maneuver_data=None):
    """Display search results"""
    if not chains:
        print(f"\n{Colors.RED}No valid chains found with those criteria.{Colors.RESET}")
        print(f"{Colors.DIM}Try relaxing your filters or changing the chain length.{Colors.RESET}")
        return

    print(f"\n{Colors.GREEN}{Colors.BOLD}Found {len(chains)} chain(s):{Colors.RESET}")
    print_divider()

    for i, chain in enumerate(chains[:limit], 1):
        display_chain(chain, i, maneuver_data=maneuver_data)

    if len(chains) > limit:
        print(f"\n{Colors.DIM}... and {len(chains) - limit} more{Colors.RESET}")


def run_questionnaire(solver: LifepathSolver):
    """Run the main questionnaire loop"""

    # Get unique settings for validation
    all_settings = sorted(set(lp.setting for lp in solver.lifepaths))

    # Optimization options
    opt_options = [
        ('years-', 'Youngest character (minimize years)'),
        ('years+', 'Oldest character (maximize years)'),
        ('stats+', 'Maximum stat points (M + P + Flex)'),
        ('mental+', 'Maximum mental stats (M + Flex)'),
        ('physical+', 'Maximum physical stats (P + Flex)'),
        ('resources+', 'Maximum resources'),
        ('circles+', 'Maximum circles'),
        ('maneuvers+', 'Maximum Infection maneuver coverage (all phases)'),
        ('maneuvers-inf+', 'Maximum Infiltration maneuver coverage'),
        ('maneuvers-usu+', 'Maximum Usurpation maneuver coverage'),
        ('maneuvers-inv+', 'Maximum Invasion maneuver coverage'),
    ]

    while True:
        clear_screen()
        print_header()

        # 1. Target lifepath
        print(f"{Colors.BOLD}What lifepath do you want to end at?{Colors.RESET}")
        print(f"{Colors.DIM}Examples: Criminal, Magnate, Archcotare, Anvil Captain, Psychologist{Colors.RESET}")
        target = get_input("Target lifepath")

        if not target:
            print(f"{Colors.RED}No target specified, exiting.{Colors.RESET}")
            break

        # Validate target exists (case-insensitive)
        # First try exact match
        if target not in solver.by_name:
            # Try case-insensitive exact match
            exact_match = None
            for name in solver.by_name.keys():
                if name.lower() == target.lower():
                    exact_match = name
                    break

            if exact_match:
                target = exact_match
            else:
                # Try fuzzy match
                matches = [n for n in solver.by_name.keys() if target.lower() in n.lower()]
                if matches:
                    print(f"\n{Colors.YELLOW}Did you mean one of these?{Colors.RESET}")
                    for i, m in enumerate(matches[:5], 1):
                        print(f"  {i}. {m}")
                    choice = input(f"{Colors.YELLOW}Choice (or Enter to re-type): {Colors.RESET}").strip()
                    try:
                        target = matches[int(choice) - 1]
                    except (ValueError, IndexError):
                        continue
                else:
                    print(f"{Colors.RED}'{target}' not found. Try again.{Colors.RESET}")
                    input("Press Enter to continue...")
                    continue

        print_divider()

        # Show canonical chain suggestion if available
        canonical = load_canonical_chains(solver)
        canonical_chain = None
        for setting, targets in canonical.items():
            if target in targets:
                canonical_chain = targets[target].get('chain')
                break

        if canonical_chain and canonical_chain.get('valid'):
            # Use skeleton if available, otherwise full path
            skeleton = canonical_chain.get('skeleton', canonical_chain['path'])
            required = canonical_chain.get('required', [])
            years = canonical_chain['years']

            # Format skeleton with color coding
            formatted_parts = []
            for part in skeleton:
                if part.startswith('[') and part.endswith(']'):
                    formatted_parts.append(f"{Colors.DIM}{part}{Colors.RESET}")
                else:
                    formatted_parts.append(f"{Colors.CYAN}{part}{Colors.RESET}")

            print(f"\n{Colors.GREEN}💡 Path template ({years} years):{Colors.RESET}")
            print(f"   {' → '.join(formatted_parts)}")
            if required:
                print(f"   {Colors.DIM}Key LPs: {', '.join(required)}{Colors.RESET}")
            print(f"   {Colors.DIM}(+{canonical_chain['stats']}M/P, +{canonical_chain['circles']}C, +{canonical_chain['resources']}R){Colors.RESET}")
            print()

        # Inner loop for "same target, different options"
        same_target = True
        while same_target:
            # 2. Chain length
            print(f"\n{Colors.BOLD}How many lifepaths in the chain?{Colors.RESET}")
            print(f"{Colors.DIM}Typical range: 4-7 (longer chains take more time to search){Colors.RESET}")

            while True:
                length_str = get_input("Chain length", "5")
                try:
                    length = int(length_str)
                    if 5 <= length <= 10:
                        break
                    print(f"{Colors.RED}Please enter a number between 5 and 10{Colors.RESET}")
                except ValueError:
                    print(f"{Colors.RED}Please enter a valid number{Colors.RESET}")

            print_divider()

            # 3. Primary optimization
            primary_opt = get_choice(
                "Primary optimization (what matters most)?",
                opt_options,
                allow_none=True
            )

            # 4. Secondary optimization
            secondary_opt = None
            if primary_opt:
                remaining_opts = [o for o in opt_options if o[0] != primary_opt]
                secondary_opt = get_choice(
                    "Secondary optimization (tiebreaker)?",
                    remaining_opts,
                    allow_none=True
                )

            print_divider()

            # 5. Must include specific lifepaths
            must_include = get_lifepath_list(
                "Must include these lifepaths (pass through):",
                solver,
                max_count=3
            )

            # 6. Required settings
            require_settings = get_settings_list(
                "Require lifepaths from these settings (must visit):",
                all_settings,
                max_count=3
            )

            # 7. Excluded settings
            exclude_settings = get_settings_list(
                "Exclude lifepaths from these settings (avoid):",
                all_settings,
                max_count=3
            )

            # 8. Born preference
            born_options = [
                ('rough', 'Rough start (Born Slave, Born on the Streets, Son of a Gun)'),
                ('noble', 'Noble start (Born to Rule)'),
                ('common', 'Common start (Born Citizen, Freeman, League, Fire)'),
            ]
            born_pref = get_choice(
                "Prefer a starting background?",
                born_options,
                allow_none=True
            )

            print_divider()

            # Build optimization list
            optimize = []
            if primary_opt:
                optimize.append(primary_opt)
            if secondary_opt:
                optimize.append(secondary_opt)

            # Summary
            print(f"\n{Colors.BOLD}Search Parameters:{Colors.RESET}")
            print(f"  Target: {Colors.CYAN}{target}{Colors.RESET}")
            print(f"  Length: {Colors.CYAN}{length} lifepaths{Colors.RESET}")
            if optimize:
                opt_names = [dict(opt_options).get(o, o) for o in optimize]
                print(f"  Optimize: {Colors.CYAN}{' → '.join(opt_names)}{Colors.RESET}")
            if must_include:
                print(f"  Via: {Colors.CYAN}{', '.join(must_include)}{Colors.RESET}")
            if require_settings:
                print(f"  Require settings: {Colors.CYAN}{', '.join(require_settings)}{Colors.RESET}")
            if exclude_settings:
                print(f"  Exclude settings: {Colors.CYAN}{', '.join(exclude_settings)}{Colors.RESET}")
            if born_pref:
                born_names = dict(born_options).get(born_pref, born_pref)
                print(f"  Born: {Colors.CYAN}{born_names}{Colors.RESET}")

            print_divider()
            print(f"\n{Colors.YELLOW}Searching...{Colors.RESET}")

            # Run search
            chains = solver.find_chains(
                target_name=target,
                length=length,
                must_include=must_include if must_include else None,
                optimize=optimize if optimize else None,
                require_settings=require_settings if require_settings else None,
                exclude_settings=exclude_settings if exclude_settings else None,
                born_preference=born_pref,
                limit=10
            )

            # Display results
            display_results(chains, maneuver_data=solver._maneuver_data)

            print_divider()

            # Continue?
            print(f"\n{Colors.BOLD}What next?{Colors.RESET}")
            print(f"  {Colors.CYAN}1.{Colors.RESET} New search (different target)")
            print(f"  {Colors.CYAN}2.{Colors.RESET} Same target ({target}), different options")
            print(f"  {Colors.CYAN}q.{Colors.RESET} Quit")

            choice = input(f"{Colors.YELLOW}Choice: {Colors.RESET}").strip().lower()

            if choice == 'q' or choice == 'quit':
                print(f"\n{Colors.GREEN}Thanks for using the Lifepath Navigator!{Colors.RESET}\n")
                return  # Exit the entire function
            elif choice == '2':
                # Continue inner loop with same target
                clear_screen()
                print_header()
                print(f"{Colors.BOLD}Target:{Colors.RESET} {Colors.CYAN}{target}{Colors.RESET}")
                continue
            else:
                # Break inner loop to start fresh with new target
                same_target = False


def main():
    """Main entry point"""
    # Check if running in a terminal that supports colors
    if not sys.stdout.isatty():
        # Disable colors for non-TTY output
        for attr in dir(Colors):
            if not attr.startswith('_'):
                setattr(Colors, attr, '')

    print(f"{Colors.DIM}Loading lifepath data...{Colors.RESET}")

    json_path = os.path.join(os.path.dirname(__file__), "human_lifepaths_complete.json")
    solver = LifepathSolver(json_path)

    try:
        run_questionnaire(solver)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.GREEN}Goodbye!{Colors.RESET}\n")
    except EOFError:
        print(f"\n\n{Colors.GREEN}Goodbye!{Colors.RESET}\n")


if __name__ == "__main__":
    main()
