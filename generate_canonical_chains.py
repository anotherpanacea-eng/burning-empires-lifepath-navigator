#!/usr/bin/env python3
"""
Generate canonical chains for capstone lifepaths in each setting.

This script:
1. Identifies "capstone" lifepaths (those with real requirements - not just stepping stones)
2. Generates optimal chains using min_years optimization
3. Analyzes chains to identify required vs flexible LPs
4. Outputs results as JSON for reference and testing
"""

import json
import sys
from collections import defaultdict
from lifepath_solver import LifepathSolver


def analyze_chain_requirements(solver, chain, target_lp):
    """
    Analyze a chain to identify which LPs are required vs flexible.

    Returns:
        dict with:
        - required_uids: UIDs that MUST appear to satisfy requirements
        - required_names: Names of required LPs
        - born_flexibility: 'any', 'noble', 'rough', or 'common'
        - filler_count: Number of flexible slots
        - skeleton: List like ['[Any Born]', 'Soldier', '[Filler]', 'Target']
    """
    result = {
        'required_uids': set(),
        'required_names': [],
        'born_flexibility': 'any',
        'filler_count': 0,
        'skeleton': []
    }

    chain_uids = set(lp.uid for lp in chain.lifepaths)

    # Walk through each LP and check what requirements it satisfies
    for lp in chain.lifepaths:
        if lp.is_born:
            # Check if target needs specific born traits
            target_reqs = target_lp.requirements or {}
            if target_reqs.get('requires_traits'):
                noble_traits = {'Mark of Privilege', 'Your Lordship', 'Your Eminence',
                               'Your Grace', 'Corvus and Crucis'}
                if any(t in noble_traits for t in target_reqs['requires_traits']):
                    result['born_flexibility'] = 'noble'
            continue

        lp_reqs = lp.requirements or {}
        is_required = False

        # Check if this LP is in target's requires_any/requires_all
        target_reqs = target_lp.requirements or {}
        if lp.uid in target_reqs.get('requires_any', []):
            is_required = True
        if lp.uid in target_reqs.get('requires_all', []):
            is_required = True

        # Check if this LP satisfies requires_twice
        if target_reqs.get('requires_twice') == lp.uid:
            is_required = True

        # Check if this LP is needed by another LP in the chain
        for other in chain.lifepaths:
            if other.uid == lp.uid:
                continue
            other_reqs = other.requirements or {}
            if lp.uid in other_reqs.get('requires_any', []):
                is_required = True
            if lp.uid in other_reqs.get('requires_all', []):
                is_required = True
            if other_reqs.get('requires_twice') == lp.uid:
                is_required = True

        if is_required:
            result['required_uids'].add(lp.uid)
            if lp.name not in result['required_names']:
                result['required_names'].append(lp.name)

    # Build skeleton
    seen_born = False
    for i, lp in enumerate(chain.lifepaths):
        if lp.is_born:
            if not seen_born:
                seen_born = True
                if result['born_flexibility'] == 'any':
                    result['skeleton'].append('[Any Born]')
                elif result['born_flexibility'] == 'noble':
                    result['skeleton'].append('[Noble Born]')
                else:
                    result['skeleton'].append(lp.name)
            else:
                # Born LP appearing again (e.g., Born to Rule for trait path)
                # Mark as required since it's doing double duty
                result['skeleton'].append(lp.name)
                if lp.name not in result['required_names']:
                    result['required_names'].append(lp.name)
        elif lp.uid in result['required_uids']:
            result['skeleton'].append(lp.name)
        elif lp.uid == target_lp.uid:
            result['skeleton'].append(lp.name)
        else:
            result['skeleton'].append('[Filler]')
            result['filler_count'] += 1

    # Convert set to list for JSON serialization
    result['required_uids'] = list(result['required_uids'])

    return result

def identify_capstone_lifepaths(solver):
    """
    Identify lifepaths that are true "destinations" - they have complex
    requirements that make them worthy of canonical chain documentation.

    We focus on:
    - requires_any: needs specific previous experience
    - requires_all: needs multiple specific experiences
    - requires_traits: needs trait purchases

    We EXCLUDE lifepaths that are primarily stepping stones (referenced
    by many others) unless they also have substantial requirements.
    """
    capstones = defaultdict(list)

    # Track which UIDs are referenced in requirements
    reference_count = defaultdict(int)
    for lp in solver.lifepaths:
        reqs = lp.requirements or {}
        for uid in reqs.get('requires_any', []):
            reference_count[uid] += 1
        for uid in reqs.get('requires_all', []):
            reference_count[uid] += 1

    for lp in solver.lifepaths:
        if lp.is_born:
            continue

        reqs = lp.requirements or {}

        # Calculate complexity score
        complexity = 0
        reasons = []

        if reqs.get('requires_all'):
            complexity += len(reqs['requires_all']) * 3  # Very important
            reasons.append(f"requires_all({len(reqs['requires_all'])})")

        if reqs.get('requires_traits'):
            complexity += 2
            reasons.append('requires_traits')

        if reqs.get('requires_any'):
            complexity += 1
            reasons.append('requires_any')

        # Penalize heavily-referenced stepping stones (unless very complex)
        refs = reference_count.get(lp.uid, 0)
        if refs >= 3 and complexity < 3:
            continue  # Skip pure stepping stones

        # Only include if has real requirements
        if complexity >= 1:
            capstones[lp.setting].append({
                'name': lp.name,
                'uid': lp.uid,
                'complexity': complexity,
                'reasons': reasons,
                'time': lp.time,
                'refs': refs
            })

    # Sort each setting by complexity (descending)
    for setting in capstones:
        capstones[setting].sort(key=lambda x: -x['complexity'])

    return capstones


def main():
    print("Loading lifepath data...")
    solver = LifepathSolver('human_lifepaths_complete.json')
    settings = set(lp.setting for lp in solver.lifepaths)
    print(f"Loaded {len(solver.lifepaths)} lifepaths across {len(settings)} settings\n")

    # Identify capstone lifepaths
    print("Identifying capstone lifepaths...")
    capstones = identify_capstone_lifepaths(solver)

    total = sum(len(lps) for lps in capstones.values())
    print(f"\nFound {total} capstone lifepaths\n")

    # Summary
    print("="*60)
    print("CAPSTONE LIFEPATHS BY SETTING")
    print("="*60)

    for setting in sorted(capstones.keys()):
        lps = capstones[setting]
        print(f"\n{setting} ({len(lps)} capstones):")
        for lp in lps[:10]:  # Show top 10
            print(f"  • {lp['name']}: {', '.join(lp['reasons'])} (complexity={lp['complexity']})")
        if len(lps) > 10:
            print(f"  ... and {len(lps)-10} more")

    # Generate canonical chains
    print("\n" + "="*60)
    print("GENERATING CANONICAL CHAINS")
    print("="*60)

    canonical = {}
    processed = 0

    for setting in sorted(capstones.keys()):
        canonical[setting] = {}
        setting_lps = capstones[setting]

        for lp_info in setting_lps:
            processed += 1
            target = lp_info['name']
            sys.stdout.write(f"\n[{processed}/{total}] {setting} → {target}...")
            sys.stdout.flush()

            # Try lengths 5, 6, 7 until we find a valid chain
            result = None
            for length in [5, 6, 7]:
                try:
                    chains = solver.find_chains(
                        target_name=target,
                        length=length,
                        optimize=['min_years'],
                        limit=1
                    )
                    if chains:
                        chain = chains[0]
                        trait_points = chain.get_net_trait_points()  # (required, optional, net)

                        # Analyze which LPs are required vs flexible
                        target_lp = solver.by_name[target][0]
                        analysis = analyze_chain_requirements(solver, chain, target_lp)

                        result = {
                            'path': [lp.name for lp in chain.lifepaths],
                            'skeleton': analysis['skeleton'],
                            'required': analysis['required_names'],
                            'born_flex': analysis['born_flexibility'],
                            'filler_slots': analysis['filler_count'],
                            'years': chain.total_years,
                            'stats': chain.total_stats,
                            'circles': chain.total_circles,
                            'resources': chain.total_resources,
                            'trait_pts': trait_points[2],  # net trait points
                            'valid': True
                        }
                        break
                except Exception as e:
                    print(f" ERROR: {e}")
                    continue

            if result:
                canonical[setting][target] = {
                    'uid': lp_info['uid'],
                    'complexity': lp_info['complexity'],
                    'reasons': lp_info['reasons'],
                    'chain': result
                }
                print(f" ✓ ({result['years']}yrs)")
            else:
                print(" ✗")

    # Save results
    output_file = 'canonical_chains.json'
    with open(output_file, 'w') as f:
        json.dump(canonical, f, indent=2)
    print(f"\n✓ Saved canonical chains to {output_file}")

    # Generate summary for CLI integration
    print("\n" + "="*60)
    print("CANONICAL CHAIN SUMMARY")
    print("="*60)

    success_count = 0
    fail_count = 0

    for setting in sorted(canonical.keys()):
        targets = canonical[setting]
        print(f"\n{setting}:")
        for target_name, data in sorted(targets.items(), key=lambda x: -x[1]['complexity']):
            chain = data.get('chain')
            if chain and chain.get('valid'):
                skeleton = ' → '.join(chain.get('skeleton', chain['path']))
                required = chain.get('required', [])
                print(f"  {target_name}: {skeleton}")
                if required:
                    print(f"    Key LPs: {', '.join(required)}")
                print(f"    ({chain['years']}yrs, +{chain['stats']}M/P, +{chain['circles']}C, +{chain['resources']}R)")
                success_count += 1
            else:
                print(f"  {target_name}: NO VALID CHAIN")
                fail_count += 1

    print(f"\n" + "="*60)
    print(f"RESULTS: {success_count} successful, {fail_count} failed")
    print("="*60)

    # Generate test fixtures
    test_cases = []
    for setting, targets in canonical.items():
        for target_name, data in targets.items():
            chain = data.get('chain')
            if chain and chain.get('valid'):
                test_cases.append({
                    'setting': setting,
                    'target': target_name,
                    'uid': data['uid'],
                    'length': len(chain['path']),
                    'expected_path': chain['path'],
                    'expected_years': chain['years'],
                })

    fixtures_file = 'canonical_test_fixtures.json'
    with open(fixtures_file, 'w') as f:
        json.dump(test_cases, f, indent=2)
    print(f"\n✓ Generated {len(test_cases)} test fixtures → {fixtures_file}")

    return canonical, test_cases


if __name__ == '__main__':
    canonical, tests = main()
