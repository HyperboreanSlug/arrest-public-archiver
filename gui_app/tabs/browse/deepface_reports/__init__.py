"""Browse → DeepFace Reports package (split for maintainability)."""
from __future__ import annotations

from .actions import DeepfaceReportsActionsMixin
from .build import DeepfaceReportsBuildMixin
from .build_list import DeepfaceReportsBuildListMixin
from .build_review import DeepfaceReportsBuildReviewMixin
from .data import DeepfaceReportsDataMixin
from .ethnicity import DeepfaceReportsEthnicityMixin
from .filters import DeepfaceReportsFiltersMixin
from .photo import DeepfaceReportsPhotoMixin
from .review import DeepfaceReportsReviewMixin
from .review_fill import DeepfaceReportsReviewFillMixin


class DeepfaceReportsTabMixin(
    DeepfaceReportsBuildMixin,
    DeepfaceReportsBuildListMixin,
    DeepfaceReportsBuildReviewMixin,
    DeepfaceReportsDataMixin,
    DeepfaceReportsFiltersMixin,
    DeepfaceReportsPhotoMixin,
    DeepfaceReportsReviewMixin,
    DeepfaceReportsReviewFillMixin,
    DeepfaceReportsActionsMixin,
    DeepfaceReportsEthnicityMixin,
):
    """Dedicated queue for stored DeepFace gross-misclass hits + verdict tracking."""

    pass


__all__ = ["DeepfaceReportsTabMixin"]
