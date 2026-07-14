"""Browse → DeepFace Reports: hits list tree construction."""
from __future__ import annotations

from gui_app.widgets import (
    _bind_tree_scroll_isolation,
    _card,
    _section_label,
    _stretch_columns,
    _tree_frame,
)


class DeepfaceReportsBuildListMixin:
    """Left-hand DeepFace hits treeview."""

    def _dfr_build_list_pane(self, body) -> None:
        list_card = _card(body)
        list_card.grid(row=0, column=0, sticky="nsew", padx=(2, 4), pady=2)
        _section_label(list_card, "DeepFace hits").pack(
            anchor="w", padx=14, pady=(12, 4)
        )
        wrap, tree = _tree_frame(list_card)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("name", "state", "listed", "face", "conf", "severity", "verdict", "id")
        tree["columns"] = cols
        tree["show"] = "headings"
        widths = [150, 44, 80, 80, 50, 60, 80, 50]
        labels = {
            "name": "NAME",
            "state": "ST",
            "listed": "LISTED",
            "face": "FACE",
            "conf": "CONF",
            "severity": "SEV",
            "verdict": "VERDICT",
            "id": "ID",
        }
        for c, w in zip(cols, widths):
            tree.heading(c, text=labels.get(c, c.upper()))
            tree.column(c, width=w, minwidth=36, stretch=(c == "name"))
        _stretch_columns(tree, cols, widths)
        self.dfr_tree = tree
        tree.bind("<<TreeviewSelect>>", self._dfr_on_select)
        _bind_tree_scroll_isolation(tree, wrap)
