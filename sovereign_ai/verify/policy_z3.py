import hashlib
import json
import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

try:
    from z3 import (And, Bool, BoolVal, Const, Context, EnumSort, Not, Or,
                    Solver, sat, unsat)

    HAS_Z3 = True
except ImportError:
    HAS_Z3 = False

logger = logging.getLogger("sovereign_ai.verify.policy_z3")


class PolicyVerifier:
    """
    Formal policy verification using the Z3 SMT solver.
    Encodes ABAC rules as boolean constraints to detect conflicts
    and reachability issues.
    """

    def __init__(self):
        if not HAS_Z3:
            logger.warning("z3-solver not installed. Policy verification will be limited.")

    def _get_context_and_solver(self) -> Tuple[Optional[Context], Optional[Solver]]:
        if not HAS_Z3:
            return None, None
        ctx = Context()
        solver = Solver(ctx=ctx)
        return ctx, solver

    def _get_sorts_and_vars(self, ctx: Context, policies: List[Dict[str, Any]]):
        """Extracts unique attributes to create Z3 Enums within a specific context."""
        principals = sorted(list(set(p.get("principal", "any") for p in policies)))
        resources = sorted(list(set(p.get("resource", "any") for p in policies)))
        actions = sorted(list(set(p.get("action", "any") for p in policies)))

        # Z3 EnumSort requires at least one member
        if not principals:
            principals = ["any"]
        if not resources:
            resources = ["any"]
        if not actions:
            actions = ["any"]

        # Create Enums for each attribute type
        Principal, principal_members = EnumSort("Principal", principals, ctx=ctx)
        Resource, resource_members = EnumSort("Resource", resources, ctx=ctx)
        Action, action_members = EnumSort("Action", actions, ctx=ctx)

        # Map strings to Z3 Enum instances
        p_map = dict(zip(principals, principal_members))
        r_map = dict(zip(resources, resource_members))
        a_map = dict(zip(actions, action_members))

        # Current constants we are checking
        p_const = Const("p", Principal)
        r_const = Const("r", Resource)
        a_const = Const("a", Action)

        return (p_const, r_const, a_const), (p_map, r_map, a_map)

    def is_authorized(
        self, principal: str, resource: str, action: str, policies: List[Dict[str, Any]]
    ) -> bool:
        """
        Runtime authorization check using SMT.
        Returns True if the action is explicitly allowed and NOT explicitly denied.
        Uses an internal LRU cache via a hash of the input parameters.
        """
        if not HAS_Z3:
            logger.critical("z3-solver is not available. Failing closed for safety.")
            return False
        # Create a stable hash of policies for cache key
        policy_hash = hashlib.sha256(json.dumps(policies, sort_keys=True).encode()).hexdigest()
        return self._cached_auth_check(
            principal, resource, action, policy_hash, tuple(json.dumps(p) for p in policies)
        )

    @lru_cache(maxsize=1024)
    def _cached_auth_check(
        self, principal: str, resource: str, action: str, policy_hash: str, policy_tuple: Tuple[str]
    ) -> bool:
        """Internal cached Z3 check."""
        policies = [json.loads(p) for p in policy_tuple]
        return self._run_auth_check(principal, resource, action, policies)

    def _run_auth_check(
        self, principal: str, resource: str, action: str, policies: List[Dict[str, Any]]
    ) -> bool:
        """Pure Z3 authorization logic."""
        ctx, solver = self._get_context_and_solver()
        if not solver:
            return True

        (p_const, r_const, a_const), (p_map, r_map, a_map) = self._get_sorts_and_vars(ctx, policies)

        # Domain handling
        if principal not in p_map:
            if "any" in p_map:
                principal = "any"
            else:
                return False

        if resource not in r_map:
            if "any" in r_map:
                resource = "any"
            else:
                return False

        if action not in a_map:
            if "any" in a_map:
                action = "any"
            else:
                return False

        solver.push()

        allow_exprs = []
        deny_exprs = []

        true_val = BoolVal(True, ctx=ctx)

        for pol in policies:
            cond = And(
                p_const == p_map[pol["principal"]] if pol["principal"] != "any" else true_val,
                r_const == r_map[pol["resource"]] if pol["resource"] != "any" else true_val,
                a_const == a_map[pol["action"]] if pol["action"] != "any" else true_val,
            )
            if pol.get("effect") == "allow":
                allow_exprs.append(cond)
            else:
                deny_exprs.append(cond)

        # Target condition
        target_cond = And(
            p_const == p_map[principal], r_const == r_map[resource], a_const == a_map[action]
        )

        is_allowed = Or(*allow_exprs) if allow_exprs else BoolVal(False, ctx=ctx)
        is_denied = Or(*deny_exprs) if deny_exprs else BoolVal(False, ctx=ctx)

        # SMT Goal: Prove there exists a valid state where target is allowed AND not denied
        solver.add(And(target_cond, is_allowed, Not(is_denied)))

        result = solver.check() == sat
        solver.pop()
        return result

    def detect_conflicts(self, policies: List[Dict[str, Any]]) -> List[str]:
        """
        Detects logical conflicts using SMT.
        Checks if there exists any (Principal, Resource, Action) tuple
        where two policies give contradictory results.
        """
        ctx, solver = self._get_context_and_solver()
        if not solver or not policies:
            return []

        conflicts = []
        (p_const, r_const, a_const), (p_map, r_map, a_map) = self._get_sorts_and_vars(ctx, policies)

        for i, p1 in enumerate(policies):
            for j, p2 in enumerate(policies):
                if i >= j:
                    continue

                # We only care if one allows and another denies
                if p1.get("effect") == p2.get("effect"):
                    continue

                solver.push()

                # Policy 1 condition
                c1 = And(
                    (
                        p_const == p_map[p1["principal"]]
                        if p1["principal"] != "any"
                        else BoolVal(True, ctx=ctx)
                    ),
                    (
                        r_const == r_map[p1["resource"]]
                        if p1["resource"] != "any"
                        else BoolVal(True, ctx=ctx)
                    ),
                    (
                        a_const == a_map[p1["action"]]
                        if p1["action"] != "any"
                        else BoolVal(True, ctx=ctx)
                    ),
                )

                # Policy 2 condition
                c2 = And(
                    (
                        p_const == p_map[p2["principal"]]
                        if p2["principal"] != "any"
                        else BoolVal(True, ctx=ctx)
                    ),
                    (
                        r_const == r_map[p2["resource"]]
                        if p2["resource"] != "any"
                        else BoolVal(True, ctx=ctx)
                    ),
                    (
                        a_const == a_map[p2["action"]]
                        if p2["action"] != "any"
                        else BoolVal(True, ctx=ctx)
                    ),
                )

                # Conflict exists if both can be true simultaneously
                solver.add(And(c1, c2))

                if solver.check() == sat:
                    m = solver.model()
                    conflicts.append(
                        f"Conflict between Policy {i} and {j}: "
                        f"Principal={m[p_const]}, Resource={m[r_const]}, Action={m[a_const]}"
                    )

                solver.pop()

        return conflicts

    def check_reachability(
        self, principal: str, resource: str, policies: List[Dict[str, Any]]
    ) -> bool:
        """Checks if a principal can EVER reach a resource under current policies."""
        ctx, solver = self._get_context_and_solver()
        if not solver:
            logger.critical("z3-solver is not available. Failing closed for safety.")
            return False

        (p_const, r_const, a_const), (p_map, r_map, a_map) = self._get_sorts_and_vars(ctx, policies)

        # If target principal/resource not in policies, we must handle carefully
        if principal not in p_map:
            if "any" in p_map:
                principal = "any"
            else:
                return False

        if resource not in r_map:
            if "any" in r_map:
                resource = "any"
            else:
                return False

        solver.push()

        allow_exprs = []
        deny_exprs = []

        for pol in policies:
            cond = And(
                (
                    p_const == p_map[pol["principal"]]
                    if pol["principal"] != "any"
                    else BoolVal(True, ctx=ctx)
                ),
                (
                    r_const == r_map[pol["resource"]]
                    if pol["resource"] != "any"
                    else BoolVal(True, ctx=ctx)
                ),
            )
            if pol.get("effect") == "allow":
                allow_exprs.append(cond)
            else:
                deny_exprs.append(cond)

        # Reachable if (principal, resource) matches an 'allow' and NO 'deny'
        target_cond = And(p_const == p_map[principal], r_const == r_map[resource])

        is_allowed = Or(*allow_exprs) if allow_exprs else BoolVal(False, ctx=ctx)
        is_denied = Or(*deny_exprs) if deny_exprs else BoolVal(False, ctx=ctx)

        solver.add(And(target_cond, is_allowed, Not(is_denied)))

        result = solver.check() == sat
        solver.pop()
        return result

    def is_policy_satisfiable(self, formulas: List[Any]) -> bool:
        """Checks if a set of policy constraints/formulas is logically satisfiable."""
        if not HAS_Z3:
            logger.critical("z3-solver is not available. Failing closed.")
            return False
        # Create solver in default context to match formulas created outside custom contexts
        from z3 import Solver, sat

        solver = Solver()
        solver.push()
        for f in formulas:
            solver.add(f)
        result = solver.check() == sat
        solver.pop()
        return result
