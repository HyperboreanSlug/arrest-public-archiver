"""CLIP zero-shot ethnicity backend (local torch + transformers)."""
from __future__ import annotations

from scraper.mugshot_ethnicity.backends_base import EthnicityBackend
from scraper.mugshot_ethnicity.models import FaceEthnicityScore


class ClipBackend(EthnicityBackend):
    """Local CLIP zero-shot prompts (torch + transformers). Heavier fallback."""

    name = "clip"
    is_production = True
    PROMPTS = {
        "white": "a frontal mugshot of a white caucasian person",
        "black": "a frontal mugshot of a black african american person",
        "asian": "a frontal mugshot of an east asian person",
        "indian": "a frontal mugshot of a south asian indian person",
        "hispanic": "a frontal mugshot of a hispanic or latino person",
        "middle_eastern": "a frontal mugshot of a middle eastern person",
    }

    def __init__(self):
        self._model = None
        self._processor = None
        self._device = "cpu"

    def is_available(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            from PIL import Image  # noqa: F401
            return True
        except Exception:
            return False

    def _load(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import CLIPModel, CLIPProcessor

        model_id = "openai/clip-vit-base-patch32"
        self._processor = CLIPProcessor.from_pretrained(model_id)
        self._model = CLIPModel.from_pretrained(model_id)
        self._model.eval()
        if torch.cuda.is_available():
            self._device = "cuda"
            self._model.to(self._device)

    def analyze(self, photo_path: str) -> FaceEthnicityScore:
        try:
            import torch
            from PIL import Image

            self._load()
            assert self._model is not None and self._processor is not None
            image = Image.open(photo_path).convert("RGB")
            labels = list(self.PROMPTS.keys())
            texts = [self.PROMPTS[k] for k in labels]
            inputs = self._processor(
                text=texts, images=image, return_tensors="pt", padding=True
            )
            if self._device == "cuda":
                inputs = {k: v.to(self._device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self._model(**inputs)
                logits = outputs.logits_per_image[0]
                probs = logits.softmax(dim=0).detach().cpu().tolist()
            scores = {lab: float(p) for lab, p in zip(labels, probs)}
            top = max(scores, key=scores.get)
            return FaceEthnicityScore(
                photo_path=photo_path,
                top_label=top,
                top_confidence=float(scores[top]),
                scores=scores,
                backend=self.name,
                face_detected=True,
            )
        except Exception as e:
            return FaceEthnicityScore(
                photo_path=photo_path,
                top_label="unknown",
                top_confidence=0.0,
                backend=self.name,
                face_detected=False,
                error=str(e),
            )
