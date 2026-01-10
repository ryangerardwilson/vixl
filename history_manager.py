import os
from typing import List, Optional


class HistoryManager:
    def __init__(self, history_path: str, legacy_path: Optional[str] = None, max_items: int = 100):
        self.history_path = history_path
        self.legacy_path = legacy_path
        self.max_items = max_items
        self.history: List[str] = []

    def load(self) -> List[str]:
        # Try current history path
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    data = [l.rstrip('\n') for l in f if l.strip()]
                self.history = data[-self.max_items:]
                return self.history
            except Exception:
                self.history = []
                return self.history

        # Try legacy path and migrate
        if self.legacy_path and os.path.exists(self.legacy_path):
            try:
                with open(self.legacy_path, 'r', encoding='utf-8') as f:
                    data = [l.rstrip('\n') for l in f if l.strip()]
                self.history = data[-self.max_items:]
                # migrate best-effort
                try:
                    with open(self.history_path, 'w', encoding='utf-8') as out:
                        out.write('\n'.join(data) + ('\n' if data else ''))
                except Exception:
                    pass
                return self.history
            except Exception:
                self.history = []
                return self.history

        # No history; create empty file best-effort
        try:
            with open(self.history_path, 'w', encoding='utf-8') as f:
                f.write('')
        except Exception:
            pass
        self.history = []
        return self.history

    def append(self, entry: str) -> None:
        if not entry:
            return
        self.history.append(entry)
        if len(self.history) > self.max_items:
            self.history = self.history[-self.max_items:]

    def persist(self, entry: str) -> None:
        if not entry:
            return
        try:
            with open(self.history_path, 'a', encoding='utf-8') as f:
                f.write(entry + '\n')
        except Exception:
            pass

    @property
    def items(self) -> List[str]:
        return list(self.history)
