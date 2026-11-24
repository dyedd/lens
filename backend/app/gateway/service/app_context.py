"""Resolve the application state bound to the current async context."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .app_state import AppState

_current_app_state: ContextVar[AppState | None] = ContextVar(
    "lens_current_app_state", default=None
)


def bind_app_state(state: AppState) -> Token[AppState | None]:
    return _current_app_state.set(state)


def reset_app_state(token: Token[AppState | None]) -> None:
    _current_app_state.reset(token)


def get_current_app_state() -> AppState:
    state = _current_app_state.get()
    if state is None:
        raise RuntimeError("Lens AppState is not bound to the current context")
    return state


class AppStateProxy:
    """Resolve the application-owned state for the current async context."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_current_app_state(), name)


app_state = AppStateProxy()
