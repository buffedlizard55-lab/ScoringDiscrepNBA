"""Arithmetic self-consistency checks for one provider's final-game data.

Why this module exists
----------------------
Cross-source comparison needs two reachable score feeds. The primary NBA CDN
feed has been unavailable to the scheduled runner (see ``data/live-feed.json``
``source_health``/``source_diagnostics`` and ``ALERTING.md``), so the monitor
also needs a detector that works with a single provider.

A provider's own published numbers can be checked against each other. For a
complete basketball game:

    points = 2 * (field goals made - three-pointers made)
           + 3 * three-pointers made
           + free throws made

If a provider's scoreboard final disagrees with the components it publishes in
the same game's box score, that is a candidate discrepancy of exactly the
213-vs-214 class. It is a *candidate*: an automated check can show that one
number does not follow from the others, and it can never establish which value
the NBA's official record holds. Every result therefore carries
``"assessment": "candidate_requires_review"`` and the arithmetic that produced
it, so a reviewer can reproduce the check by hand from the cited URL.

Only the ESPN summary shape is implemented, because that is the only payload
shape verified against a live response (2026-10-07, CLE@WSH 2025-11-07 game
401809511). Unverified shapes return ``not_checkable`` instead of a guess.
"""

from __future__ import annotations

import re
from typing import Any

CONSISTENCY_SCHEMA_VERSION = 1

NOT_CHECKABLE_NOTE = (
    "The provider payload did not contain the components needed for this check. "
    "A check that cannot run is not evidence that the numbers are consistent."
)


def _parse_made_attempted(value: Any) -> tuple[int, int] | None:
    """Parse a provider stat cell such as ``"52-110"`` into (made, attempted).

    Keep numeric but impossible values for the consistency checker to flag;
    treating them as missing would turn corrupt data into a silent blind spot.
    """
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(-?\d+)\s*-\s*(-?\d+)\s*", value)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _statistics_by_name(statistics: Any) -> dict[str, str]:
    if not isinstance(statistics, list):
        return {}
    lookup: dict[str, str] = {}
    for entry in statistics:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        value = entry.get("displayValue")
        if isinstance(name, str) and isinstance(value, str):
            lookup[name] = value
    return lookup


def _component_error(components: dict[str, tuple[int, int] | None]) -> str | None:
    """Return a reason when shooting cells are impossible or contradict each other."""
    labels = {
        "fieldGoals": "field-goal",
        "threePointers": "three-point",
        "freeThrows": "free-throw",
    }
    for key, label in labels.items():
        pair = components.get(key)
        if pair is None:
            continue
        made, attempted = pair
        if made < 0 or attempted < 0:
            return f"{label} makes or attempts are negative"
        if made > attempted:
            return f"{label} makes exceed attempts"

    field_goals = components.get("fieldGoals")
    three_pointers = components.get("threePointers")
    if field_goals is None or three_pointers is None:
        return None
    if three_pointers[0] > field_goals[0]:
        return "three-point makes exceed total field-goal makes"
    if three_pointers[1] > field_goals[1]:
        return "three-point attempts exceed total field-goal attempts"
    return None


def derive_points_from_components(components: dict[str, tuple[int, int]]) -> int | None:
    """Return 2*(FGM-3PM) + 3*3PM + FTM, or None for unknown/impossible inputs."""
    required = ("fieldGoals", "threePointers", "freeThrows")
    if any(key not in components for key in required):
        return None
    field_goals = components["fieldGoals"]
    three_pointers = components["threePointers"]
    free_throws = components["freeThrows"]
    if _component_error(components) is not None:
        return None
    two_pointers_made = field_goals[0] - three_pointers[0]
    return 2 * two_pointers_made + 3 * three_pointers[0] + free_throws[0]


def espn_team_components(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract per-side shooting components from an ESPN summary payload."""
    boxscore = payload.get("boxscore")
    teams = boxscore.get("teams") if isinstance(boxscore, dict) else None
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(teams, list):
        return result
    for entry in teams:
        if not isinstance(entry, dict):
            continue
        side = str(entry.get("homeAway") or "").lower()
        if side not in {"home", "away"} or side in result:
            continue
        statistics = _statistics_by_name(entry.get("statistics"))
        components: dict[str, tuple[int, int] | None] = {
            "fieldGoals": _parse_made_attempted(statistics.get("fieldGoalsMade-fieldGoalsAttempted")),
            "threePointers": _parse_made_attempted(
                statistics.get("threePointGoalsMade-threePointGoalsAttempted")
                or statistics.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted")
            ),
            "freeThrows": _parse_made_attempted(
                statistics.get("freeThrowsMade-freeThrowsAttempted")
            ),
        }
        result[side] = {
            "team": (entry.get("team") or {}).get("abbreviation"),
            "components": components,
        }
    return result


def espn_consistency_checks(
    payload: dict[str, Any],
    provider_scores: dict[str, Any] | None,
    source_url: str,
    game_id: str | None = None,
) -> dict[str, Any]:
    """Compare ESPN's box-score components with ESPN's own reported final.

    ``provider_scores`` is the same provider's scoreboard value for the game
    (``{"away": int|None, "home": int|None}``). Nothing is compared against a
    different provider, and no assumption is made about which side is right.
    """
    result: dict[str, Any] = {
        "schema_version": CONSISTENCY_SCHEMA_VERSION,
        "source_key": "espn",
        "game_id": game_id,
        "source_url": source_url,
        "method": "2 * (FGM - 3PM) + 3 * 3PM + FTM, using the provider's own box-score components",
        "status": "not_checkable",
        "provider_reported": {
            "away": (provider_scores or {}).get("away"),
            "home": (provider_scores or {}).get("home"),
        },
        "checks": [],
        "assessment": "candidate_requires_review",
        "note": NOT_CHECKABLE_NOTE,
    }
    if not isinstance(provider_scores, dict) or any(
        provider_scores.get(side) is None for side in ("away", "home")
    ):
        result["reason"] = "the provider feed did not publish both final scores for this game"
        return result

    sides = espn_team_components(payload)
    if not sides:
        result["reason"] = "the summary payload did not include boxscore.teams"
        return result

    checks: list[dict[str, Any]] = []
    for side in ("away", "home"):
        side_entry = sides.get(side)
        if not side_entry:
            result["reason"] = f"the summary payload did not include a {side} team box score"
            result["checks"] = checks
            return result
        components = side_entry["components"]
        derivable = {key: value for key, value in components.items() if value is not None}
        if len(derivable) != 3:
            result["reason"] = f"the {side} box score did not include parseable FGM/3PM/FTM cells"
            result["checks"] = checks
            return result
        component_error = _component_error(derivable)
        derived = derive_points_from_components(derivable)
        reported = provider_scores.get(side)
        checks.append(
            {
                "side": side,
                "team": side_entry.get("team"),
                "provider_reported_final": reported,
                "derived_points": derived,
                "difference": None if derived is None or reported is None else derived - reported,
                "component_error": component_error,
                "components": {
                    "fieldGoalsMade-attempted": derivable["fieldGoals"],
                    "threePointersMade-attempted": derivable["threePointers"],
                    "freeThrowsMade-attempted": derivable["freeThrows"],
                },
                "twoPointersMade": (
                    derivable["fieldGoals"][0] - derivable["threePointers"][0]
                    if component_error is None
                    else None
                ),
            }
        )

    mismatches = [
        check
        for check in checks
        if check.get("component_error") or check["difference"] not in (0, None)
    ]
    result["checks"] = checks
    if mismatches:
        result["status"] = "inconsistent"
        result["note"] = (
            "The provider's final and/or box-score components are internally inconsistent. "
            "Where components are valid, the reported final is compared with the arithmetic "
            "derived from those components. This is a candidate discrepancy for review; it does "
            "not establish which value the NBA's official record holds."
        )
        result["differences"] = [
            {
                "side": check["side"],
                "derived_points": check["derived_points"],
                "provider_reported_final": check["provider_reported_final"],
                "difference": check["difference"],
                **({"component_error": check["component_error"]} if check.get("component_error") else {}),
            }
            for check in mismatches
        ]
    else:
        result["status"] = "consistent"
        result["note"] = (
            "The provider's reported final matches the arithmetic of the box-score components "
            "it publishes for the same game. This check cannot detect an error the provider "
            "propagated consistently across both views."
        )
    return result
