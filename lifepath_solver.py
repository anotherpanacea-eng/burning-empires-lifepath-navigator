"""
Burning Empires Lifepath Solver (UID-based)

A clean solver using pre-parsed requirements in structured JSON format.
"""

import json
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Lifepath:
    """Represents a single lifepath"""
    uid: int
    name: str
    setting: str
    tags: List[str]
    is_born: bool
    time: int
    resources: int
    circles: int
    stat: str
    skills: Dict
    traits: Dict
    requirements: Dict

    @property
    def key(self) -> str:
        return f"{self.name} ({self.setting})"

    def __hash__(self):
        return self.uid

    def __eq__(self, other):
        return self.uid == other.uid


@dataclass
class Chain:
    """Represents a chain of lifepaths"""
    lifepaths: List[Lifepath]
    warnings: List[str] = field(default_factory=list)

    @property
    def uids(self) -> List[int]:
        return [lp.uid for lp in self.lifepaths]

    @property
    def uid_set(self) -> Set[int]:
        return set(self.uids)

    @property
    def total_years(self) -> int:
        base_years = sum(lp.time for lp in self.lifepaths)
        return base_years + self.setting_jumps

    @property
    def setting_jumps(self) -> int:
        jumps = 0
        for i in range(1, len(self.lifepaths)):
            if self.lifepaths[i].setting != self.lifepaths[i-1].setting:
                jumps += 1
        return jumps

    @property
    def all_tags(self) -> Set[str]:
        tags = set()
        for lp in self.lifepaths:
            tags.update(lp.tags)
        return tags

    def get_traits(self) -> Set[str]:
        """Get all traits available in this chain"""
        traits = set()
        for lp in self.lifepaths:
            traits.update(lp.traits.get('list', []))
        return traits

    def get_net_trait_points(self) -> Tuple[int, int, int]:
        """Calculate net trait points (total - required traits cost)

        Returns: (net_points, total_points, required_count)
        - Each LP with traits has 1 required trait (first in list)
        - Net = total points - number of required traits
        """
        total_points = sum(lp.traits.get('points', 0) for lp in self.lifepaths)

        # First trait in each LP's list is required (costs 1 pt each)
        required_count = 0
        for lp in self.lifepaths:
            trait_list = lp.traits.get('list', [])
            if trait_list:
                required_count += 1

        net_points = total_points - required_count
        return (net_points, total_points, required_count)

    def get_optional_traits(self) -> Set[str]:
        """Get traits available for purchase (costs 1 pt each from net pool)"""
        optional = set()
        for lp in self.lifepaths:
            trait_list = lp.traits.get('list', [])
            # Traits after the first are optional (available for 1 pt)
            if len(trait_list) > 1:
                optional.update(trait_list[1:])
        return optional

    def get_required_traits(self) -> Set[str]:
        """Get traits that are automatically purchased (first trait from each LP)"""
        required = set()
        for lp in self.lifepaths:
            trait_list = lp.traits.get('list', [])
            if trait_list:
                required.add(trait_list[0])
        return required

    def can_afford_trait(self, trait_name: str) -> Tuple[bool, str]:
        """Check if chain can afford a specific trait.

        Returns: (can_afford, reason)
        """
        required = self.get_required_traits()
        optional = self.get_optional_traits()
        net, _, _ = self.get_net_trait_points()

        # If it's a required trait, it's free
        if trait_name in required:
            return (True, "required (free)")

        # If it's optional, need 1 net point
        if trait_name in optional:
            if net >= 1:
                return (True, f"optional (1 pt, have {net} net)")
            else:
                return (False, f"need 1 pt but only have {net} net")

        # Trait not available in this chain
        return (False, "not available in chain")

    def get_stats(self) -> Tuple[int, int, int]:
        """Calculate stat bonuses from chain.

        Returns: (mental, physical, flexible)
        - mental: guaranteed +M bonuses
        - physical: guaranteed +P bonuses
        - flexible: +M/P bonuses (can be assigned to either)
        """
        mental = 0
        physical = 0
        flexible = 0

        for lp in self.lifepaths:
            stat = lp.stat.strip()
            if stat in ('—', '', '-'):
                continue
            elif stat == '+1M' or stat == '+1 M':
                mental += 1
            elif stat == '+1P' or stat == '+1 P':
                physical += 1
            elif stat == '+1M/P' or stat == '+1 M/P':
                flexible += 1
            elif stat in ('+1M,P', '+1 M,P', '+1M, P'):
                mental += 1
                physical += 1

        return (mental, physical, flexible)

    @property
    def max_mental(self) -> int:
        """Maximum mental stat bonus (M + flexible)"""
        m, p, f = self.get_stats()
        return m + f

    @property
    def max_physical(self) -> int:
        """Maximum physical stat bonus (P + flexible)"""
        m, p, f = self.get_stats()
        return p + f

    @property
    def total_stats(self) -> int:
        """Total stat points (M + P + flexible)"""
        m, p, f = self.get_stats()
        return m + p + f

    @property
    def total_resources(self) -> int:
        """Total resource points from chain"""
        return sum(lp.resources for lp in self.lifepaths)

    @property
    def total_circles(self) -> int:
        """Total circles from chain"""
        return sum(lp.circles for lp in self.lifepaths)


class LifepathSolver:
    """Solver for finding valid lifepath chains"""

    NOBLE_TRAITS = {"Mark of Privilege", "Your Lordship", "Your Eminence", "Your Grace", "Your Majesty"}

    def __init__(self, json_file: str):
        self.lifepaths: List[Lifepath] = []
        self.by_uid: Dict[int, Lifepath] = {}
        self.by_name: Dict[str, List[Lifepath]] = {}
        self.born_lifepaths: List[Lifepath] = []

        self._load(json_file)

    def _load(self, json_file: str):
        """Load lifepaths from JSON (supports both old and consolidated formats)"""
        with open(json_file, 'r') as f:
            data = json.load(f)

        # Support consolidated format (has 'lifepaths' key) or legacy format (array)
        if isinstance(data, dict) and 'lifepaths' in data:
            lifepath_data = data['lifepaths']
            self.canonical_chains = data.get('canonical_chains', {})
        else:
            lifepath_data = data
            self.canonical_chains = {}

        for entry in lifepath_data:
            lp = Lifepath(
                uid=entry['uid'],
                name=entry['name'],
                setting=entry['setting'],
                tags=entry.get('tags', []),
                is_born=entry.get('is_born', False),
                time=entry.get('time', 0),
                resources=entry.get('resources', 0),
                circles=entry.get('circles', 0),
                stat=entry.get('stat', ''),
                skills=entry.get('skills', {}),
                traits=entry.get('traits', {}),
                requirements=entry.get('requirements', {})
            )
            self.lifepaths.append(lp)
            self.by_uid[lp.uid] = lp

            if lp.name not in self.by_name:
                self.by_name[lp.name] = []
            self.by_name[lp.name].append(lp)

            if lp.is_born:
                self.born_lifepaths.append(lp)

        print(f"Loaded {len(self.lifepaths)} lifepaths")

    def get_lifepath(self, name: str) -> Optional[Lifepath]:
        """Get lifepath by name (returns first match if multiple)"""
        if name in self.by_name:
            return self.by_name[name][0]
        return None

    def validate_requirements(self, chain: Chain, target: Lifepath, position: int) -> Tuple[bool, List[str]]:
        """
        Validate if target LP's requirements are satisfied at given position.

        Uses proper AND/OR semantics:
        - Hard constraints (AND): requires_all, requires_previous_settings, requires_twice,
          min_age, position, incompatible_traits - ALL must pass if present
        - Prereq constraints (OR): requires_any, requires_k_of_n, requires_tags,
          requires_traits, requires_conjunction - at least ONE must pass (if any specified)

        Returns (is_valid, warnings)
        """
        reqs = target.requirements
        warnings = []
        errors = []  # Hard failures

        # Get chain state before this position
        preceding = chain.lifepaths[:position]
        preceding_uids = {lp.uid for lp in preceding}
        preceding_tags = set()
        for lp in preceding:
            preceding_tags.update(lp.tags)

        # Available traits from preceding LPs
        available_traits = set()
        for lp in preceding:
            available_traits.update(lp.traits.get('list', []))

        # ========== HARD CONSTRAINTS (AND - all must pass if present) ==========

        # Check requires_all (ALL UIDs must be present)
        # NOTE: If requires_traits is ALSO present, requires_all becomes an OR alternative
        # (e.g., Forged Lord: "Hammer Lord AND Anvil Lord OR Your Grace trait")
        ok_requires_all = True
        requires_all_is_or_option = bool(reqs.get('requires_all') and reqs.get('requires_traits'))
        if reqs.get('requires_all') and not requires_all_is_or_option:
            missing = [uid for uid in reqs['requires_all'] if uid not in preceding_uids]
            if missing:
                ok_requires_all = False
                errors.append(f"⚠ {target.name} requires all of UIDs {reqs['requires_all']} (missing {missing})")

        # Check requires_previous_settings (N LPs from those settings)
        ok_prev_settings = True
        if reqs.get('requires_previous_settings'):
            rps = reqs['requires_previous_settings']
            count_needed = rps['count']
            settings = [s.lower() for s in rps['settings']]
            born_counts = rps.get('born_counts', count_needed == 1)

            if born_counts:
                matches = sum(1 for lp in preceding
                             if lp.setting.lower() in settings or
                                any(s in lp.setting.lower() for s in settings))
            else:
                matches = sum(1 for lp in preceding
                             if (lp.setting.lower() in settings or
                                 any(s in lp.setting.lower() for s in settings))
                             and not lp.is_born)

            if matches < count_needed:
                ok_prev_settings = False
                errors.append(f"⚠ {target.name} requires {count_needed} {'/'.join(rps['settings'])} LP(s) (found {matches})")

        # Check requires_twice (UID must appear twice)
        ok_requires_twice = True
        if reqs.get('requires_twice'):
            uid = reqs['requires_twice']
            count = sum(1 for lp in preceding if lp.uid == uid)
            if count < 2:
                ok_requires_twice = False
                lp_name = self.by_uid[uid].name if uid in self.by_uid else f"UID {uid}"
                errors.append(f"⚠ {target.name} requires taking {lp_name} twice (found {count})")

        # Check min_age (sum of years + setting jumps > min_age)
        ok_min_age = True
        if reqs.get('min_age'):
            min_age = reqs['min_age']
            years = sum(lp.time for lp in preceding)
            jumps = 0
            for i in range(1, len(preceding)):
                if preceding[i].setting != preceding[i-1].setting:
                    jumps += 1
            current_age = years + jumps

            if current_age <= min_age:
                ok_min_age = False
                errors.append(f"⚠ {target.name} requires age > {min_age} (current: {current_age})")

        # Check incompatible_traits
        ok_no_incompatible = True
        if reqs.get('incompatible_traits'):
            blocked = set(reqs['incompatible_traits']) & available_traits
            if blocked:
                ok_no_incompatible = False
                errors.append(f"⚠ {target.name} incompatible with traits: {blocked}")

        # Check position constraints
        ok_position = True
        pos = reqs.get('position', {})

        if pos.get('must_be') and position != pos['must_be'] - 1:
            ok_position = False
            errors.append(f"⚠ {target.name} must be lifepath #{pos['must_be']}")

        if pos.get('cannot_be') and position == pos['cannot_be'] - 1:
            ok_position = False
            errors.append(f"⚠ {target.name} cannot be lifepath #{pos['cannot_be']}")

        if pos.get('can_be') and (position + 1) not in pos['can_be']:
            ok_position = False
            errors.append(f"⚠ {target.name} must be in position {pos['can_be']}")

        if pos.get('once_only') and target.uid in preceding_uids:
            ok_position = False
            errors.append(f"⚠ {target.name} can only be taken once")

        # Combine hard constraints
        all_hard_pass = (ok_requires_all and ok_prev_settings and ok_requires_twice
                        and ok_min_age and ok_no_incompatible and ok_position)

        # ========== PREREQ CONSTRAINTS (OR - at least one must pass) ==========

        # Check if ANY prereq requirements are specified
        has_prereq_reqs = any([
            reqs.get('requires_any'),
            reqs.get('requires_k_of_n'),
            reqs.get('requires_tags'),
            reqs.get('requires_traits'),
            reqs.get('requires_conjunction'),
            requires_all_is_or_option  # When requires_all + requires_traits exist together
        ])

        # Check requires_any (any ONE UID satisfies)
        ok_any = False
        if reqs.get('requires_any'):
            if any(uid in preceding_uids for uid in reqs['requires_any']):
                ok_any = True

        # Check requires_k_of_n (need k from list)
        ok_k_of_n = False
        if reqs.get('requires_k_of_n'):
            k = reqs['requires_k_of_n']['k']
            from_uids = reqs['requires_k_of_n']['from']
            # Use born_counts flag if present, else default: born doesn't count if k >= 2
            born_counts = reqs['requires_k_of_n'].get('born_counts', k < 2)

            if born_counts:
                matches = sum(1 for lp in preceding if lp.uid in from_uids)
            else:
                matches = sum(1 for lp in preceding
                             if lp.uid in from_uids and not lp.is_born)

            if matches >= k:
                ok_k_of_n = True
            else:
                warnings.append(f"⚠ {target.name} requires {k} of specified LPs (found {matches})")

        # Check requires_tags (any LP with matching tag)
        ok_tags = False
        if reqs.get('requires_tags'):
            if any(tag in preceding_tags for tag in reqs['requires_tags']):
                ok_tags = True

        # Check requires_traits (any trait purchasable from preceding LPs)
        # IMPORTANT: Trait must be both available AND affordable to satisfy requirement
        ok_traits = False
        if reqs.get('requires_traits'):
            for trait in reqs['requires_traits']:
                if trait in available_traits or any(trait.lower() in t.lower() for t in available_traits):
                    # Check if we can actually afford this trait
                    can_afford, reason = chain.can_afford_trait(trait)
                    if can_afford:
                        ok_traits = True  # Only satisfied if affordable
                        warnings.append(f"⚠ {target.name}: Using trait path ({trait}) - {reason}")
                    else:
                        # Trait available but unaffordable - NOT satisfied, add error
                        errors.append(f"❌ {target.name}: Trait path ({trait}) unaffordable - {reason}")
                    break

        # Check requires_conjunction (alternative complex path)
        ok_conjunction = False
        if reqs.get('requires_conjunction'):
            conj = reqs['requires_conjunction']
            all_required = conj.get('requires_all', [])
            any_of = conj.get('requires_any_of', [])
            all_any = conj.get('requires_all_any', [])

            if all_required and any_of:
                # Pattern: (all of requires_all) AND (one of requires_any_of)
                if all(uid in preceding_uids for uid in all_required):
                    if any(uid in preceding_uids for uid in any_of):
                        ok_conjunction = True
            elif all_any:
                # Pattern: one from EACH group
                if all(any(uid in preceding_uids for uid in group) for group in all_any):
                    ok_conjunction = True

        # Check requires_all as OR option (when paired with requires_traits)
        ok_requires_all_as_or = False
        if requires_all_is_or_option:
            if all(uid in preceding_uids for uid in reqs['requires_all']):
                ok_requires_all_as_or = True

        # Combine prereq constraints (OR)
        any_prereq_satisfied = (ok_any or ok_k_of_n or ok_tags or ok_traits
                               or ok_conjunction or ok_requires_all_as_or)

        # ========== FINAL DETERMINATION ==========

        # satisfied = all_hard_pass AND (no_prereqs OR any_prereq_satisfied)
        if has_prereq_reqs:
            is_satisfied = all_hard_pass and any_prereq_satisfied
        else:
            is_satisfied = all_hard_pass

        # Check _special constraints (just warn, don't fail)
        if reqs.get('_special'):
            warnings.append(f"📋 {target.name}: {reqs['_special']}")

        # Combine errors into warnings for return (maintain API compatibility)
        all_warnings = errors + warnings

        return (is_satisfied, all_warnings)

    def validate_chain(self, chain: Chain) -> Tuple[bool, List[str]]:
        """Validate an entire chain.

        Now trusts the boolean return from validate_requirements directly,
        without brittle string-matching heuristics.
        """
        all_warnings = []

        # First LP must be born
        if not chain.lifepaths[0].is_born:
            all_warnings.append(f"⚠ First lifepath must be a 'born' lifepath")
            return (False, all_warnings)

        # Validate each LP's requirements
        for i, lp in enumerate(chain.lifepaths):
            if i == 0:
                continue  # Skip born LP

            is_valid, warnings = self.validate_requirements(chain, lp, i)
            all_warnings.extend(warnings)

            # Trust the boolean return - validate_requirements now uses proper AND/OR logic
            if not is_valid:
                return (False, all_warnings)

        return (True, all_warnings)

    def _precompute_providers(self):
        """Precompute what each LP provides for satisfying requirements"""
        if hasattr(self, '_providers_computed'):
            return

        self._providers_computed = True

        # Map: uid -> set of LPs it helps satisfy
        self._uid_providers = {}  # uid -> [LPs that have this uid]
        self._tag_providers = {}  # tag -> [LPs that have this tag]
        self._trait_providers = {}  # trait -> [LPs that offer this trait]

        for lp in self.lifepaths:
            # Each LP provides its own UID
            if lp.uid not in self._uid_providers:
                self._uid_providers[lp.uid] = []
            self._uid_providers[lp.uid].append(lp)

            # Tags it provides
            for tag in lp.tags:
                if tag not in self._tag_providers:
                    self._tag_providers[tag] = []
                self._tag_providers[tag].append(lp)

            # Traits it provides
            for trait in lp.traits.get('list', []):
                trait_lower = trait.lower()
                if trait_lower not in self._trait_providers:
                    self._trait_providers[trait_lower] = []
                self._trait_providers[trait_lower].append(lp)

    def _get_requirement_satisfiers(self, lp: Lifepath) -> Set[int]:
        """Get UIDs of all LPs that could help satisfy this LP's requirements"""
        self._precompute_providers()

        reqs = lp.requirements
        satisfiers = set()

        # requires_any - any of these UIDs works
        if reqs.get('requires_any'):
            satisfiers.update(reqs['requires_any'])

        # requires_all - all of these needed
        if reqs.get('requires_all'):
            satisfiers.update(reqs['requires_all'])

        # requires_k_of_n
        if reqs.get('requires_k_of_n'):
            satisfiers.update(reqs['requires_k_of_n']['from'])

        # requires_conjunction
        if reqs.get('requires_conjunction'):
            conj = reqs['requires_conjunction']
            if conj.get('requires_all'):
                satisfiers.update(conj['requires_all'])
            if conj.get('requires_any_of'):
                satisfiers.update(conj['requires_any_of'])
            if conj.get('requires_all_any'):
                for group in conj['requires_all_any']:
                    satisfiers.update(group)

        # requires_tags - find LPs with those tags
        if reqs.get('requires_tags'):
            for tag in reqs['requires_tags']:
                if tag in self._tag_providers:
                    satisfiers.update(p.uid for p in self._tag_providers[tag])

        # requires_traits
        if reqs.get('requires_traits'):
            for trait in reqs['requires_traits']:
                trait_lower = trait.lower()
                if trait_lower in self._trait_providers:
                    satisfiers.update(p.uid for p in self._trait_providers[trait_lower])

        # requires_previous_settings
        if reqs.get('requires_previous_settings'):
            settings = [s.lower() for s in reqs['requires_previous_settings']['settings']]
            for lp2 in self.lifepaths:
                if lp2.setting.lower() in settings or any(s in lp2.setting.lower() for s in settings):
                    satisfiers.add(lp2.uid)

        # requires_twice - need that specific UID twice
        if reqs.get('requires_twice'):
            satisfiers.add(reqs['requires_twice'])

        return satisfiers

    def _check_requirements_satisfied(self, lp: Lifepath, chain_uids: Set[int]) -> bool:
        """Check if LP's requirements are satisfied by the UIDs in chain_uids.

        For OR requirements (requires_any vs requires_k_of_n), returns True if EITHER is satisfied.
        """
        reqs = lp.requirements

        # Check requires_any (need any one)
        any_uids = reqs.get('requires_any', [])
        has_any = not any_uids or any(uid in chain_uids for uid in any_uids)

        # Check requires_k_of_n (need k from list)
        k_of_n = reqs.get('requires_k_of_n')
        if k_of_n:
            k = k_of_n.get('k', k_of_n.get('count', 2))
            from_uids = k_of_n.get('from', k_of_n.get('uids', []))
            count = sum(1 for uid in from_uids if uid in chain_uids)
            has_k_of_n = count >= k
        else:
            has_k_of_n = True

        # Check requires_all (need all)
        all_uids = reqs.get('requires_all', [])
        has_all = all(uid in chain_uids for uid in all_uids)

        # For Criminal-style reqs: requires_any OR requires_k_of_n (plus requires_all if present)
        # If both any_uids and k_of_n exist, they're alternatives (OR)
        if any_uids and k_of_n:
            return (has_any or has_k_of_n) and has_all
        else:
            return has_any and has_k_of_n and has_all

    def _search_backward(
        self,
        target: Lifepath,
        length: int,
        must_include: List[str],
        results: List[Chain],
        max_results: int = 50,
        born_preference: str = None
    ):
        """Search backward from target to find valid chains using optimized DFS"""
        self._precompute_providers()

        # Precompute satisfiers for all LPs
        satisfiers_cache = {}
        for lp in self.lifepaths:
            satisfiers_cache[lp.uid] = self._get_requirement_satisfiers(lp)

        # Precompute which UIDs are needed twice by something (for repeat detection)
        # Map: uid -> True if something requires this LP twice
        twice_required = set()
        for lp in self.lifepaths:
            rt = lp.requirements.get('requires_twice')
            if rt:
                twice_required.add(rt)

        # Get all non-born LPs sorted by how "connective" they are
        non_born = [lp for lp in self.lifepaths if not lp.is_born]

        # Stack: (chain built backward from target, remaining slots)
        stack = [([target], length - 1)]
        explored = 0
        seen_chains = set()  # Avoid duplicate chains

        # Scale search limit with chain length (longer chains need more exploration)
        base_limit = 100000
        search_limit = base_limit * (1 + (length - 5) * 0.5) if length > 5 else base_limit

        while stack and len(results) < max_results:
            partial, remaining = stack.pop()
            explored += 1

            if explored > search_limit:
                print(f"  Search limit reached after {explored} nodes, found {len(results)} chains")
                break

            if remaining == 0:
                # Complete chain - validate and check
                chain_lps = list(reversed(partial))
                chain_key = tuple(lp.uid for lp in chain_lps)

                if chain_key in seen_chains:
                    continue
                seen_chains.add(chain_key)

                # First LP must be born
                if not chain_lps[0].is_born:
                    continue

                chain = Chain(lifepaths=chain_lps)
                is_valid, warnings = self.validate_chain(chain)

                if is_valid:
                    if must_include:
                        chain_names = {lp.name for lp in chain_lps}
                        if not all(name in chain_names for name in must_include):
                            continue

                    chain.warnings = warnings
                    results.append(chain)
                continue

            # Get candidates that could help satisfy requirements of items in partial
            # Focus on LPs that provide what's needed
            needed_uids = set()
            # Exclude target from preceding UIDs (partial is built backwards, target is last)
            preceding_uids_set = {lp.uid for lp in partial if lp.uid != target.uid}

            # Check if ALL LPs in partial have their requirements satisfied
            # Not just the target - intermediate LPs also need their prereqs!
            all_satisfied = True
            for lp_in_chain in partial:
                # For each LP, check if it's satisfied by LPs that would precede it
                # (everything after it in partial, since partial is built backwards)
                lp_idx = partial.index(lp_in_chain)
                after_lp = partial[lp_idx + 1:] if lp_idx + 1 < len(partial) else []
                preceding_for_lp = {l.uid for l in after_lp}

                if not self._check_requirements_satisfied(lp_in_chain, preceding_for_lp):
                    all_satisfied = False
                    needed_uids.update(satisfiers_cache.get(lp_in_chain.uid, set()))

            # Easy LPs with no prereqs (for filling gaps)
            easy_lps = [lp for lp in non_born
                       if not lp.requirements.get('requires_any')
                       and not lp.requirements.get('requires_all')
                       and not lp.requirements.get('requires_k_of_n')
                       and not lp.requirements.get('requires_twice')]

            if needed_uids:
                # Prioritize satisfiers - only add a few fillers
                candidates = [self.by_uid[uid] for uid in needed_uids
                             if uid in self.by_uid and not self.by_uid[uid].is_born]
                # Only add fillers if we don't have many satisfier options
                if len(candidates) < 8:
                    candidates = list(set(candidates) | set(easy_lps[:5]))
            else:
                # Requirements satisfied - use only fillers
                candidates = easy_lps[:12]

            # Add born LPs at position 0
            if remaining == 1:
                # Next position is 0, so add born LPs to explore
                # Prioritize preferred born types (add them last so they're popped first from stack)
                born_to_add = list(self.born_lifepaths)
                if born_preference:
                    if born_preference == 'rough':
                        preferred = self.ROUGH_BORN
                    elif born_preference == 'noble':
                        preferred = self.NOBLE_BORN
                    elif born_preference == 'common':
                        preferred = self.COMMON_BORN
                    else:
                        preferred = set()
                    # Sort: non-preferred first, preferred last (so preferred are popped first)
                    born_to_add = sorted(born_to_add, key=lambda b: b.name in preferred)

                for born in born_to_add:
                    new_partial = partial + [born]
                    stack.append((new_partial, 0))

            # Identify UIDs that can be repeated (from requires_twice)
            repeatable_uids = set()
            for lp_in_chain in partial:
                rt = lp_in_chain.requirements.get('requires_twice')
                if rt:
                    repeatable_uids.add(rt)
                # Also check if this LP is itself repeatable (something requires it twice)
                if lp_in_chain.uid in twice_required:
                    repeatable_uids.add(lp_in_chain.uid)

            # Limit branching factor based on chain depth
            # Tighter limits for longer chains to avoid explosion
            max_branch = 20 if remaining <= 3 else 15
            partial_uids = {lp.uid for lp in partial}
            for cand in candidates[:max_branch]:
                if cand.is_born:
                    continue  # Born handled separately above

                # Allow repeats only for repeatable UIDs
                if cand.uid in partial_uids and cand.uid not in repeatable_uids:
                    continue

                new_partial = partial + [cand]
                stack.append((new_partial, remaining - 1))


    def _find_constrained_chains(
        self,
        target: Lifepath,
        length: int,
        results: List[Chain],
        max_results: int = 50,
        born_preference: str = None
    ):
        """Find chains for targets with complex constraints (requires_twice, position constraints)"""

        # Find "easy" LPs that can fill gaps (no prereqs, no position constraints)
        easy_fillers = []
        for lp in self.lifepaths:
            if lp.is_born:
                continue
            reqs = lp.requirements
            pos = reqs.get('position', {})
            if pos.get('must_be') or pos.get('cannot_be'):
                continue
            if reqs.get('requires_twice'):
                continue
            if (not reqs.get('requires_any') and not reqs.get('requires_all')
                and not reqs.get('requires_k_of_n') and not reqs.get('requires_tags')):
                easy_fillers.append(lp)

        # Analyze what's needed for this target
        def trace_requirements(lp: Lifepath, depth: int = 0) -> List[Tuple[int, int, bool]]:
            """Trace back requirements, return list of (uid, min_position, is_repeatable)"""
            reqs = []
            req = lp.requirements

            if req.get('requires_twice'):
                needed_uid = req['requires_twice']
                needed_lp = self.by_uid[needed_uid]
                # Need this LP twice
                reqs.append((needed_uid, None, True))  # Repeatable
                reqs.append((needed_uid, None, True))
                # And trace ITS requirements
                reqs.extend(trace_requirements(needed_lp, depth + 1))

            if req.get('requires_any'):
                # Pick first option for tracing
                reqs.append((req['requires_any'][0], None, False))
                first_req = self.by_uid.get(req['requires_any'][0])
                if first_req:
                    reqs.extend(trace_requirements(first_req, depth + 1))

            return reqs

        needed = trace_requirements(target)

        # Check for position constraints among needed LPs
        pinned_positions = {}  # position -> uid
        for uid, pos, repeatable in needed:
            lp = self.by_uid[uid]
            must_be = lp.requirements.get('position', {}).get('must_be')
            if must_be:
                pinned_positions[must_be - 1] = uid  # Convert to 0-indexed

        # Build template chain with pinned positions
        template = [None] * length
        template[-1] = target.uid  # Target at end

        for pos, uid in pinned_positions.items():
            if pos < length:
                template[pos] = uid

        # Fill in repeated LPs working backward from target
        req = target.requirements
        if req.get('requires_twice'):
            needed_uid = req['requires_twice']
            needed_lp = self.by_uid[needed_uid]

            # Place two of these right before target (or as close as possible)
            pos = length - 2
            count = 0
            while pos >= 0 and count < 2:
                if template[pos] is None:
                    template[pos] = needed_uid
                    count += 1
                pos -= 1

            # Check if this LP also has requires_twice (nested)
            nested_req = needed_lp.requirements.get('requires_twice')
            if nested_req:
                count = 0
                while pos >= 0 and count < 2:
                    if template[pos] is None:
                        template[pos] = nested_req
                        count += 1
                    pos -= 1

        # Count empty slots to fill
        empty_slots = [i for i, uid in enumerate(template) if uid is None and i > 0]

        # Generate chains by trying born LPs and fillers
        # Prioritize preferred born types
        born_order = list(self.born_lifepaths)
        if born_preference:
            if born_preference == 'rough':
                preferred = self.ROUGH_BORN
            elif born_preference == 'noble':
                preferred = self.NOBLE_BORN
            elif born_preference == 'common':
                preferred = self.COMMON_BORN
            else:
                preferred = set()
            # Sort: preferred first
            born_order = sorted(born_order, key=lambda b: b.name not in preferred)

        for born in born_order:
            base_template = template.copy()
            base_template[0] = born.uid

            if not empty_slots:
                # No gaps - just validate
                chain_lps = [self.by_uid[uid] for uid in base_template if uid is not None]
                if len(chain_lps) == length:
                    chain = Chain(lifepaths=chain_lps)
                    is_valid, warnings = self.validate_chain(chain)
                    if is_valid:
                        chain.warnings = warnings
                        results.append(chain)
                        if len(results) >= max_results:
                            return
            else:
                # Fill empty slots with combinations of easy fillers
                from itertools import combinations_with_replacement, permutations

                # Limit filler options
                filler_sample = easy_fillers[:20]

                if len(empty_slots) == 1:
                    # Single slot - try each filler
                    for filler in filler_sample:
                        test_template = base_template.copy()
                        test_template[empty_slots[0]] = filler.uid

                        chain_lps = [self.by_uid[uid] for uid in test_template]
                        chain = Chain(lifepaths=chain_lps)
                        is_valid, warnings = self.validate_chain(chain)
                        if is_valid:
                            chain.warnings = warnings
                            results.append(chain)
                            if len(results) >= max_results:
                                return

                elif len(empty_slots) == 2:
                    # Two slots - try pairs
                    tried = set()
                    for f1 in filler_sample[:15]:
                        for f2 in filler_sample[:15]:
                            key = (f1.uid, f2.uid)
                            if key in tried:
                                continue
                            tried.add(key)

                            test_template = base_template.copy()
                            test_template[empty_slots[0]] = f1.uid
                            test_template[empty_slots[1]] = f2.uid

                            chain_lps = [self.by_uid[uid] for uid in test_template]
                            chain = Chain(lifepaths=chain_lps)
                            is_valid, warnings = self.validate_chain(chain)
                            if is_valid:
                                chain.warnings = warnings
                                results.append(chain)
                                if len(results) >= max_results:
                                    return

    def _find_conjunction_chains(
        self,
        target: Lifepath,
        length: int,
        results: List[Chain],
        max_results: int = 50,
        born_preference: str = None
    ):
        """Find chains for targets with requires_all (both LPs path and trait path)"""
        from collections import deque

        reqs = target.requirements
        must_have_all = reqs.get('requires_all', [])
        must_have_one = reqs.get('requires_any', [])
        trait_reqs = reqs.get('requires_traits', [])

        def shortest_prereq_path_bfs(target_uid: int, avoid_pos_2: bool = True) -> List[Lifepath]:
            """Find shortest prereq path using BFS (handles cycles and requires_all)"""
            target_lp = self.by_uid[target_uid]

            # Handle requires_all first (need ALL of these)
            prereq_all = target_lp.requirements.get('requires_all', [])
            if prereq_all:
                # Recursively get prereqs for each required LP
                all_prereqs = []
                seen = set()
                for req_uid in prereq_all:
                    req_lp = self.by_uid.get(req_uid)
                    if req_lp and not req_lp.is_born:
                        sub_prereqs = shortest_prereq_path_bfs(req_uid, avoid_pos_2)
                        for p in sub_prereqs:
                            if p.uid not in seen:
                                seen.add(p.uid)
                                all_prereqs.append(p)
                        if req_lp.uid not in seen:
                            seen.add(req_lp.uid)
                            all_prereqs.append(req_lp)
                return all_prereqs

            # BFS for requires_any
            queue = deque([(target_lp, [])])
            visited = {target_uid}

            while queue:
                lp, path = queue.popleft()
                prereq_any = lp.requirements.get('requires_any', [])

                # If no prereqs, this is a terminal - return path
                if not prereq_any:
                    return path  # path doesn't include target itself

                for prereq_uid in prereq_any:
                    if prereq_uid in visited:
                        continue

                    prereq_lp = self.by_uid.get(prereq_uid)
                    if not prereq_lp or prereq_lp.is_born:
                        continue

                    # Skip position:2 LPs (noble-only) if avoiding
                    if avoid_pos_2:
                        pos = prereq_lp.requirements.get('position', {})
                        if pos.get('must_be') == 2:
                            continue

                    visited.add(prereq_uid)

                    # Handle requires_all in prereq
                    prereq_all = prereq_lp.requirements.get('requires_all', [])
                    if prereq_all:
                        sub_prereqs = shortest_prereq_path_bfs(prereq_uid, avoid_pos_2)
                        return sub_prereqs + [prereq_lp] + path

                    new_path = [prereq_lp] + path  # prepend to path

                    # Check if this prereq is terminal
                    prereq_reqs = prereq_lp.requirements.get('requires_any', [])
                    if not prereq_reqs:
                        return new_path

                    queue.append((prereq_lp, new_path))

            return []  # No path found

        # Get easy fillers (no prereqs, no position constraints)
        easy_fillers = [lp for lp in self.lifepaths
                       if not lp.is_born
                       and not lp.requirements.get('requires_any')
                       and not lp.requirements.get('requires_all')
                       and not lp.requirements.get('requires_k_of_n')
                       and not lp.requirements.get('position', {}).get('must_be')]

        # Prioritize born lifepaths
        born_order = list(self.born_lifepaths)
        if born_preference:
            if born_preference == 'rough':
                preferred = self.ROUGH_BORN
            elif born_preference == 'noble':
                preferred = self.NOBLE_BORN
            elif born_preference == 'common':
                preferred = self.COMMON_BORN
            else:
                preferred = set()
            born_order = sorted(born_order, key=lambda b: b.name not in preferred)

        # Strategy 1: requires_all + requires_any combined (like Cotar Fomas)
        # Need ALL from requires_all AND ONE from requires_any
        if must_have_all and must_have_one:
            # Get prereqs for each required LP in requires_all
            all_prereqs = []
            all_required_lps = []
            seen_uids = set()

            for uid in must_have_all:
                req_lp = self.by_uid[uid]
                prereqs = shortest_prereq_path_bfs(uid)
                for lp_item in prereqs:
                    if lp_item.uid not in seen_uids:
                        seen_uids.add(lp_item.uid)
                        all_prereqs.append(lp_item)
                if req_lp.uid not in seen_uids:
                    seen_uids.add(req_lp.uid)
                    all_required_lps.append(req_lp)

            # For each option in requires_any, build a chain
            for any_uid in must_have_one:
                any_lp = self.by_uid.get(any_uid)
                if not any_lp or any_lp.is_born:
                    continue

                any_prereqs = shortest_prereq_path_bfs(any_uid)
                core_lps = list(all_prereqs)

                # Add requires_any prereqs (if not already in)
                for lp_item in any_prereqs:
                    if lp_item.uid not in seen_uids:
                        core_lps.append(lp_item)

                # Add required LPs then the any LP
                core_lps.extend(all_required_lps)
                if any_lp.uid not in seen_uids:
                    core_lps.append(any_lp)

                for born in born_order:
                    slots = length - 2 - len(core_lps)
                    if slots < 0:
                        continue

                    if slots == 0:
                        base_chain = [born] + core_lps + [target]
                    else:
                        base_chain = [born]
                        used_uids = {born.uid, target.uid} | {lp.uid for lp in core_lps}
                        for filler in easy_fillers:
                            if filler.uid not in used_uids:
                                base_chain.append(filler)
                                used_uids.add(filler.uid)
                                if len(base_chain) >= length - len(core_lps) - 1:
                                    break
                        base_chain.extend(core_lps)
                        base_chain.append(target)

                    if len(base_chain) != length:
                        continue

                    chain = Chain(lifepaths=base_chain)
                    is_valid, warnings = self.validate_chain(chain)

                    if is_valid:
                        chain.warnings = warnings
                        results.append(chain)
                        if len(results) >= max_results:
                            return

        # Strategy 2: LP path only (requires_all without requires_any)
        if must_have_all and not must_have_one:
            # Get prereq chains for EACH required LP using BFS
            required_lps_with_prereqs = []
            for uid in must_have_all:
                req_lp = self.by_uid[uid]
                prereqs = shortest_prereq_path_bfs(uid)
                required_lps_with_prereqs.append((req_lp, prereqs))

            # Merge all prereq chains, deduplicating shared prereqs
            merged_prereqs = []
            seen_uids = set()

            for req_lp, prereqs in required_lps_with_prereqs:
                for lp_item in prereqs:
                    if lp_item.uid not in seen_uids:
                        seen_uids.add(lp_item.uid)
                        merged_prereqs.append(lp_item)

            required_lps_only = []
            for req_lp, _ in required_lps_with_prereqs:
                if req_lp.uid not in seen_uids:
                    seen_uids.add(req_lp.uid)
                    required_lps_only.append(req_lp)

            core_lps = merged_prereqs + required_lps_only
            min_lp_path_length = len(core_lps) + 2  # +1 for born, +1 for target

            # Only try LP path if it fits the requested length
            if length >= min_lp_path_length:
                for born in born_order:
                    slots = length - 2 - len(core_lps)

                    if slots == 0:
                        base_chain = [born] + core_lps + [target]
                    else:
                        base_chain = [born]
                        used_uids = {born.uid, target.uid} | seen_uids
                        for filler in easy_fillers:
                            if filler.uid not in used_uids:
                                base_chain.append(filler)
                                used_uids.add(filler.uid)
                                if len(base_chain) >= length - len(core_lps) - 1:
                                    break
                        base_chain.extend(core_lps)
                        base_chain.append(target)

                    if len(base_chain) != length:
                        continue

                    chain = Chain(lifepaths=base_chain)
                    is_valid, warnings = self.validate_chain(chain)

                    if is_valid:
                        chain.warnings = warnings
                        results.append(chain)
                        if len(results) >= max_results:
                            return

            # Strategy 2b: Trait path alternative (when LP path doesn't fit)
            # For targets with requires_traits as alternative to LP path
            if trait_reqs and (length < min_lp_path_length or len(results) == 0):
                # Find LPs that provide the required traits
                self._precompute_providers()
                for trait in trait_reqs:
                    trait_lower = trait.lower()
                    if trait_lower in self._trait_providers:
                        for trait_lp in self._trait_providers[trait_lower]:
                            # If trait provider is a born LP, use it directly as start
                            if trait_lp.is_born:
                                # Path: Born LP (trait provider) -> fillers -> target
                                slots = length - 2  # -1 for born, -1 for target
                                base_chain = [trait_lp]
                                used_uids = {trait_lp.uid, target.uid}

                                for filler in easy_fillers:
                                    if filler.uid not in used_uids:
                                        base_chain.append(filler)
                                        used_uids.add(filler.uid)
                                        if len(base_chain) >= length - 1:
                                            break

                                base_chain.append(target)

                                if len(base_chain) != length:
                                    continue

                                chain = Chain(lifepaths=base_chain)
                                is_valid, warnings = self.validate_chain(chain)

                                if is_valid:
                                    chain.warnings = warnings
                                    results.append(chain)
                                    if len(results) >= max_results:
                                        return
                            else:
                                # Non-born trait provider - need prereqs to reach it
                                trait_prereqs = shortest_prereq_path_bfs(trait_lp.uid, avoid_pos_2=False)
                                core_lps = trait_prereqs + [trait_lp]

                                for born in born_order:
                                    slots = length - 2 - len(core_lps)
                                    if slots < 0:
                                        continue

                                    if slots == 0:
                                        base_chain = [born] + core_lps + [target]
                                    else:
                                        base_chain = [born]
                                        used_uids = {born.uid, target.uid} | {lp.uid for lp in core_lps}
                                        for filler in easy_fillers:
                                            if filler.uid not in used_uids:
                                                base_chain.append(filler)
                                                used_uids.add(filler.uid)
                                                if len(base_chain) >= length - len(core_lps) - 1:
                                                    break
                                        base_chain.extend(core_lps)
                                        base_chain.append(target)

                                    if len(base_chain) != length:
                                        continue

                                    chain = Chain(lifepaths=base_chain)
                                    is_valid, warnings = self.validate_chain(chain)

                                    if is_valid:
                                        chain.warnings = warnings
                                        results.append(chain)
                                        if len(results) >= max_results:
                                            return

        # Strategy 3: requires_any only path (no requires_all)
        if must_have_one and not must_have_all:
            for any_uid in must_have_one:
                any_lp = self.by_uid.get(any_uid)
                if any_lp and not any_lp.is_born:
                    prereqs = shortest_prereq_path_bfs(any_uid)
                    core_lps = prereqs + [any_lp]

                    for born in born_order:
                        slots = length - 2 - len(core_lps)
                        if slots < 0:
                            continue

                        if slots == 0:
                            base_chain = [born] + core_lps + [target]
                        else:
                            base_chain = [born]
                            used_uids = {born.uid, target.uid} | {lp.uid for lp in core_lps}
                            for filler in easy_fillers:
                                if filler.uid not in used_uids:
                                    base_chain.append(filler)
                                    used_uids.add(filler.uid)
                                    if len(base_chain) >= length - len(core_lps) - 1:
                                        break
                            base_chain.extend(core_lps)
                            base_chain.append(target)

                        if len(base_chain) != length:
                            continue

                        chain = Chain(lifepaths=base_chain)
                        is_valid, warnings = self.validate_chain(chain)

                        if is_valid:
                            chain.warnings = warnings
                            results.append(chain)
                            if len(results) >= max_results:
                                return

    # Born lifepath categories
    ROUGH_BORN = {'Born Slave', 'Born on the Streets', 'Son of a Gun'}
    NOBLE_BORN = {'Born to Rule'}
    COMMON_BORN = {'Born Citizen', 'Born to Freeman', 'Born to the League', 'Born to Fire'}

    def _find_via_waypoint(
        self,
        target: Lifepath,
        waypoint: Lifepath,
        length: int,
        results: List[Chain],
        max_results: int = 50,
        born_preference: str = None,
        exclude_settings: List[str] = None
    ):
        """Find chains that pass through a specific waypoint LP"""
        from itertools import combinations

        # Normalize excluded settings
        exc_settings = [s.lower() for s in (exclude_settings or [])]

        def is_excluded(lp: Lifepath) -> bool:
            """Check if LP is from an excluded setting"""
            if not exc_settings:
                return False
            lp_setting = lp.setting.lower()
            return any(exc in lp_setting for exc in exc_settings)

        def get_prereq_options(lp: Lifepath, include_nested: bool = True) -> List[List[Lifepath]]:
            """Get possible prereq combinations for an LP, with nested prereqs"""
            reqs = lp.requirements
            options = []

            # requires_any - any ONE of these
            if reqs.get('requires_any'):
                for uid in reqs['requires_any']:
                    prereq = self.by_uid.get(uid)
                    if prereq and not prereq.is_born and not is_excluded(prereq):
                        # Check if this prereq has its own prereqs
                        prereq_reqs = prereq.requirements
                        if include_nested and prereq_reqs.get('requires_any'):
                            # Get nested prereqs
                            for nested_uid in prereq_reqs['requires_any'][:5]:
                                nested = self.by_uid.get(nested_uid)
                                if nested and not nested.is_born and not is_excluded(nested):
                                    options.append([nested, prereq])
                        else:
                            options.append([prereq])

            # requires_k_of_n - need k of these, prefer ones with no prereqs
            if reqs.get('requires_k_of_n'):
                k = reqs['requires_k_of_n']['k']
                from_uids = reqs['requires_k_of_n']['from']
                from_lps = [self.by_uid[uid] for uid in from_uids
                           if uid in self.by_uid and not self.by_uid[uid].is_born
                           and not is_excluded(self.by_uid[uid])]

                # Sort by complexity - prefer LPs with no prereqs
                def prereq_complexity(p):
                    r = p.requirements
                    if r.get('requires_any') or r.get('requires_previous_settings'):
                        return 1
                    return 0

                from_lps_sorted = sorted(from_lps, key=prereq_complexity)

                # Generate combinations, prioritizing simple ones
                for combo in combinations(from_lps_sorted, k):
                    options.append(list(combo))

            # No specific prereqs - LP can come after anything
            if not options:
                options.append([])

            return options

        # Get prereq options
        waypoint_prereq_options = get_prereq_options(waypoint)

        # Check if waypoint directly satisfies target's requires_any
        target_reqs = target.requirements
        if waypoint.uid in target_reqs.get('requires_any', []):
            # Waypoint directly satisfies target - no additional target prereqs needed
            target_prereq_options = [[]]
        else:
            target_prereq_options = get_prereq_options(target)

        # Prioritize born lifepaths
        born_order = list(self.born_lifepaths)
        if born_preference:
            if born_preference == 'rough':
                preferred = self.ROUGH_BORN
            elif born_preference == 'noble':
                preferred = self.NOBLE_BORN
            elif born_preference == 'common':
                preferred = self.COMMON_BORN
            else:
                preferred = set()
            born_order = sorted(born_order, key=lambda b: b.name not in preferred)

        # Get all easy fillers (no prereqs) filtered by excluded settings
        all_easy_fillers = [lp for lp in self.lifepaths
                           if not lp.is_born
                           and not is_excluded(lp)
                           and not lp.requirements.get('requires_any')
                           and not lp.requirements.get('requires_all')
                           and not lp.requirements.get('requires_k_of_n')]

        seen_chains = set()  # Track unique chains by UID tuple

        # Try different combinations (limit to avoid explosion)
        for waypoint_prereqs in waypoint_prereq_options[:20]:
            for target_prereqs in target_prereq_options[:20]:
                # Calculate minimum chain length for this combo
                min_len = 1 + len(waypoint_prereqs) + 1 + len(target_prereqs) + 1

                if min_len > length:
                    continue

                slots_to_fill = length - min_len

                for born in born_order:
                    # UIDs that are reserved (will be in chain) - used to filter fillers
                    reserved_uids = {born.uid, waypoint.uid, target.uid}
                    for prereq in waypoint_prereqs + target_prereqs:
                        reserved_uids.add(prereq.uid)

                    # Get available fillers for this base chain
                    available_fillers = [lp for lp in all_easy_fillers
                                        if lp.uid not in reserved_uids]

                    # Generate filler combinations if needed
                    if slots_to_fill > 0 and len(available_fillers) >= slots_to_fill:
                        # Try multiple filler combinations
                        filler_combos = list(combinations(available_fillers[:30], slots_to_fill))[:50]
                    else:
                        filler_combos = [()]

                    for fillers in filler_combos:
                        # Build the chain
                        chain_lps = [born]

                        # Insert fillers after born
                        for filler in fillers:
                            chain_lps.append(filler)

                        # Add waypoint prereqs
                        for prereq in waypoint_prereqs:
                            chain_lps.append(prereq)

                        # Add waypoint
                        chain_lps.append(waypoint)

                        # Add target prereqs
                        for prereq in target_prereqs:
                            chain_lps.append(prereq)

                        # Add target
                        chain_lps.append(target)

                        if len(chain_lps) != length:
                            continue

                        # Skip duplicates
                        chain_key = tuple(lp.uid for lp in chain_lps)
                        if chain_key in seen_chains:
                            continue
                        seen_chains.add(chain_key)

                        # Validate
                        chain = Chain(lifepaths=chain_lps)
                        is_valid, warnings = self.validate_chain(chain)

                        if is_valid:
                            chain.warnings = warnings
                            results.append(chain)
                            if len(results) >= max_results:
                                return

    def find_chains(
        self,
        target_name: str,
        length: int,
        must_include: List[str] = None,
        optimize: List[str] = None,
        require_settings: List[str] = None,
        exclude_settings: List[str] = None,
        born_preference: str = None,
        limit: int = 10
    ) -> List[Chain]:
        """
        Find valid chains ending at target.

        Args:
            target_name: Name of the target lifepath
            length: Exact chain length
            must_include: LP names that must appear in chain
            optimize: Sort criteria ('years-', 'years+', 'stats+', 'mental+', 'physical+', 'resources+', 'circles+')
            require_settings: Settings that must have at least one LP in chain (up to 3)
            exclude_settings: Settings that cannot have any LPs in chain (up to 3)
            born_preference: 'rough' (Slave/Streets/Gun), 'noble' (Rule), 'common', or None
            limit: Max results to return
        """
        target_lps = self.by_name.get(target_name, [])
        if not target_lps:
            print(f"Target '{target_name}' not found")
            return []

        target = target_lps[0]

        print(f"\nSearching for {length}-LP chains ending at {target.name}...")
        if must_include:
            print(f"Must include: {must_include}")
        if require_settings:
            print(f"Require settings: {require_settings}")
        if exclude_settings:
            print(f"Exclude settings: {exclude_settings}")

        valid_chains = []

        # If must_include is specified, use waypoint search for each required LP
        if must_include:
            for waypoint_name in must_include:
                waypoint_lps = self.by_name.get(waypoint_name, [])
                if waypoint_lps:
                    waypoint = waypoint_lps[0]
                    self._find_via_waypoint(target, waypoint, length, valid_chains, limit * 10, born_preference, exclude_settings)
        else:
            # Check if target has complex requirements needing special handling
            reqs = target.requirements
            if reqs.get('requires_twice'):
                self._find_constrained_chains(target, length, valid_chains, limit * 5, born_preference)
            elif reqs.get('requires_all'):
                # Has requires_all constraint - use template-based search
                # This handles both (requires_all AND requires_any) and just requires_all
                self._find_conjunction_chains(target, length, valid_chains, limit * 5, born_preference)
            else:
                # Use regular backward search
                self._search_backward(target, length, [], valid_chains, limit * 5, born_preference)

        # Filter by setting requirements
        if require_settings or exclude_settings:
            filtered = []
            req_settings = [s.lower() for s in (require_settings or [])][:3]
            exc_settings = [s.lower() for s in (exclude_settings or [])][:3]

            for chain in valid_chains:
                chain_settings = {lp.setting.lower() for lp in chain.lifepaths}

                # Check required settings (need at least one LP from each)
                if req_settings:
                    missing = False
                    for req in req_settings:
                        if not any(req in s for s in chain_settings):
                            missing = True
                            break
                    if missing:
                        continue

                # Check excluded settings (no LPs from these)
                if exc_settings:
                    excluded = False
                    for exc in exc_settings:
                        if any(exc in s for s in chain_settings):
                            excluded = True
                            break
                    if excluded:
                        continue

                filtered.append(chain)

            valid_chains = filtered

        # Filter by born preference
        if born_preference:
            if born_preference == 'rough':
                allowed_born = self.ROUGH_BORN
            elif born_preference == 'noble':
                allowed_born = self.NOBLE_BORN
            elif born_preference == 'common':
                allowed_born = self.COMMON_BORN
            else:
                allowed_born = None

            if allowed_born:
                valid_chains = [c for c in valid_chains
                               if c.lifepaths[0].name in allowed_born]

        # Sort by optimization criteria
        if optimize:
            for opt in optimize:
                if opt == 'years-':
                    valid_chains.sort(key=lambda c: c.total_years)
                elif opt == 'years+':
                    valid_chains.sort(key=lambda c: -c.total_years)
                elif opt == 'mental+':
                    valid_chains.sort(key=lambda c: -c.max_mental)
                elif opt == 'physical+':
                    valid_chains.sort(key=lambda c: -c.max_physical)
                elif opt == 'stats+':
                    valid_chains.sort(key=lambda c: -c.total_stats)
                elif opt == 'resources+':
                    valid_chains.sort(key=lambda c: -c.total_resources)
                elif opt == 'circles+':
                    valid_chains.sort(key=lambda c: -c.total_circles)

        return valid_chains[:limit]


def main():
    """Test the solver"""
    solver = LifepathSolver('human_lifepaths_uid.json')

    # Test cases
    test_cases = [
        ('Archcotare', 6),
        ('Forged Lord', 6),
        ('Magnate', 6),
        ('Justiciar', 6),
        ('First Speaker', 7),
        ('Speaker', 7),
    ]

    for target, length in test_cases:
        print(f"\n{'='*60}")
        print(f"TARGET: {target} (length {length})")
        print('='*60)

        results = solver.find_chains(
            target_name=target,
            length=length,
            optimize=['years-'],
            limit=3
        )

        if results:
            for i, chain in enumerate(results[:3], 1):
                path = ' → '.join(lp.name for lp in chain.lifepaths)
                net, total, req = chain.get_net_trait_points()
                print(f"\n{i}. {path}")
                print(f"   Years: {chain.total_years}, Traits: {net} net ({total} - {req})")
                for w in chain.warnings:
                    print(f"   {w}")
        else:
            print("  No valid chains found")


if __name__ == '__main__':
    main()
