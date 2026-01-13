from dataclasses import dataclass
from typing import Any, Optional, Set, Callable


@dataclass
class DfEditorContext:
    state: Any
    grid: Any
    paginator: Any
    _set_status: Callable[[str, float], None]
    column_prompt: Any = None
    _leader_ttl: float = 1.5

    # DF leader state
    df_leader_state: Optional[str] = None

    # Numeric prefix (counts)
    pending_count: Optional[int] = None

    # Repeat last action metadata
    last_action: Optional[dict] = None

    # External editor state
    pending_external_edit: bool = False
    pending_edit_snapshot: Optional[dict] = None

    # Callback to run interactive commands (e.g., external editor) in current terminal
    run_interactive: Optional[Callable[[list], int]] = None
    config: Optional[dict] = None


CTX_ATTRS: Set[str] = {
    "state",
    "grid",
    "paginator",
    "_set_status",
    "column_prompt",
    "_leader_ttl",
    "df_leader_state",
    "pending_count",
    "last_action",
    "pending_external_edit",
    "pending_edit_snapshot",
    "run_interactive",
    "config",
}
