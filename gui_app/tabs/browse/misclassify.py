"""Browse arrests with race / classification filters and photo sidebar."""
from __future__ import annotations

from gui_app.tabs.browse.misclassify_actions import MisclassifyActionsMixin
from gui_app.tabs.browse.misclassify_build import MisclassifyBuildMixin
from gui_app.tabs.browse.misclassify_export import MisclassifyExportMixin


class MisclassifyTabMixin(
    MisclassifyExportMixin,
    MisclassifyActionsMixin,
    MisclassifyBuildMixin,
):
    """Browse tab (historically named Misclassify)."""
