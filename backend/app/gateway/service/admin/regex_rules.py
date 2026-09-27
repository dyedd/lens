from __future__ import annotations

from typing import Any

from fastapi import Depends, Response

from ....models.regex_rules import RegexRuleCreate, RegexRuleUpdate, RegexRuleView
from ..app_state import app_state
from ..auth import get_current_admin
from ..tasks.model_group_placement import run_model_group_placement


async def list_regex_rules(
    _: Any = Depends(get_current_admin),
) -> list[RegexRuleView]:
    """List regex rules sorted by name."""
    return await app_state.regex_rule_repo.list_rules()


async def create_regex_rule(
    payload: RegexRuleCreate, _: Any = Depends(get_current_admin)
) -> RegexRuleView:
    """Create a regex rule."""
    return await app_state.regex_rule_repo.create_rule(payload)


async def update_regex_rule(
    rule_id: str, payload: RegexRuleUpdate, _: Any = Depends(get_current_admin)
) -> RegexRuleView:
    """Update a regex rule, then place models its groups no longer cover."""
    rule = await app_state.regex_rule_repo.update_rule(rule_id, payload)
    await run_model_group_placement(app_state)
    return rule


async def delete_regex_rule(
    rule_id: str, _: Any = Depends(get_current_admin)
) -> Response:
    """Delete a regex rule and its references, then place uncovered models."""
    await app_state.regex_rule_repo.delete_rule(rule_id)
    await run_model_group_placement(app_state)
    return Response(status_code=204)
