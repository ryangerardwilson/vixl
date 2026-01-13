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

    # Cell editing state
    mode: str = "normal"  # normal | cell_normal | cell_insert
    cell_buffer: str = ""
    cell_cursor: int = 0
    cell_hscroll: int = 0
    cell_col: Optional[Any] = None
    cell_leader_state: Optional[str] = None
    df_leader_state: Optional[str] = None

    # Numeric prefix (counts)
    pending_count: Optional[int] = None

    # Repeat last action metadata
    last_action: Optional[dict] = None

    # External editor state
    pending_external_edit: bool = False
    pending_preserve_cell_mode: bool = False
    pending_edit_snapshot: Optional[dict] = None
    external_proc: Optional[Any] = None
    external_tmp_path: Optional[str] = None
    external_meta: Optional[dict] = None
    external_receiving: bool = False


CTX_ATTRS: Set[str] = {
    "state",
    "grid",
    "paginator",
    "_set_status",
    "column_prompt",
    "_leader_ttl",
    "mode",
    "cell_buffer",
    "cell_cursor",
    "cell_hscroll",
    "cell_col",
    "cell_leader_state",
    "df_leader_state",
    "pending_count",
    "last_action",
    "pending_external_edit",
    "pending_preserve_cell_mode",
    "pending_edit_snapshot",
    "external_proc",
    "external_tmp_path",
    "external_meta",
    "external_receiving",
}
