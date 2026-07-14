"""DeepFace tab: Scan sub-tab (run mugshot scans) + Setup sub-tab (install/weights)."""
from __future__ import annotations

from gui_app.tabs.deepface.scan_build import DeepfaceScanBuildMixin
from gui_app.tabs.deepface.scan_build_form import DeepfaceScanBuildFormMixin
from gui_app.tabs.deepface.scan_build_panels import DeepfaceScanBuildPanelsMixin
from gui_app.tabs.deepface.scan_options import DeepfaceScanOptionsMixin
from gui_app.tabs.deepface.scan_photo import DeepfaceScanPhotoMixin
from gui_app.tabs.deepface.scan_live import DeepfaceScanLiveMixin
from gui_app.tabs.deepface.scan_review import DeepfaceScanReviewMixin
from gui_app.tabs.deepface.scan_run import DeepfaceScanRunMixin
from gui_app.tabs.deepface.scan_export import DeepfaceScanExportMixin
from gui_app.tabs.deepface.setup_build import DeepfaceSetupBuildMixin
from gui_app.tabs.deepface.setup_build_weights import DeepfaceSetupBuildWeightsMixin
from gui_app.tabs.deepface.setup_status import DeepfaceSetupStatusMixin
from gui_app.tabs.deepface.setup_actions import DeepfaceSetupActionsMixin
from gui_app.tabs.deepface.scroll_log import DeepfaceScrollLogMixin


class DeepfaceTabMixin(
    DeepfaceScanBuildMixin,
    DeepfaceScanBuildFormMixin,
    DeepfaceScanBuildPanelsMixin,
    DeepfaceScanOptionsMixin,
    DeepfaceScanPhotoMixin,
    DeepfaceScanLiveMixin,
    DeepfaceScanReviewMixin,
    DeepfaceScanRunMixin,
    DeepfaceScanExportMixin,
    DeepfaceSetupBuildMixin,
    DeepfaceSetupBuildWeightsMixin,
    DeepfaceSetupStatusMixin,
    DeepfaceSetupActionsMixin,
    DeepfaceScrollLogMixin,
):
    """Compose all DeepFace tab sub-mixins."""


__all__ = ["DeepfaceTabMixin"]
