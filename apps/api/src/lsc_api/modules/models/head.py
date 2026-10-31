"""Optional server-side split-model head inference (SERVER_HEAD_ENABLED).

SECURITY(MODEL-06): inputs (embeddings) are never logged. The ONNX session is
loaded once and reused. This is used only for packages with ``head_mode ==
server``; most packages run the head on-device.

``onnxruntime`` is an optional dependency (``[head]`` extra); this module is
imported lazily only when the feature flag is on, so the base image need not
include it.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

from lsc_api.core.errors import UpstreamError, ValidationError

# Bound the decoded embedding so a caller cannot submit an oversized tensor.
_MAX_EMBEDDING_BYTES = 64 * 1024


@dataclass(frozen=True)
class HeadResult:
    """Top-k class indices and probabilities (basis points)."""

    classes: list[int]
    probs_bp: list[int]


class ServerHead:
    """Loads a head.onnx and runs bounded top-k inference (CPU)."""

    def __init__(self, onnx_bytes: bytes) -> None:
        """Load the ONNX head into a reusable CPU session.

        Failure modes: ``UpstreamError`` if onnxruntime is unavailable or the
        model cannot be loaded.
        """

        try:
            import onnxruntime as ort  # lazy import; optional dependency
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise UpstreamError("server head enabled but onnxruntime missing") from exc
        try:
            self._session = ort.InferenceSession(
                onnx_bytes, providers=["CPUExecutionProvider"]
            )
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError("failed to load server head model") from exc
        self._input_name = self._session.get_inputs()[0].name

    def infer(self, *, embedding_b64: str, top_k: int) -> HeadResult:
        """Run top-k inference on a base64-encoded float32 embedding.

        Failure modes: ``ValidationError`` if the embedding is malformed or too
        large. Inputs are never logged.
        """

        import numpy as np

        try:
            raw = base64.b64decode(embedding_b64)
        except (ValueError, TypeError) as exc:
            raise ValidationError("embedding is not valid base64") from exc
        if len(raw) == 0 or len(raw) > _MAX_EMBEDDING_BYTES:
            raise ValidationError("embedding size out of bounds")
        if len(raw) % 4 != 0:
            raise ValidationError("embedding is not float32-aligned")

        vector = np.frombuffer(raw, dtype="<f4").reshape(1, -1)
        logits = self._session.run(None, {self._input_name: vector})[0][0]

        # Softmax -> top-k, probabilities as integer basis points (no floats out).
        exps = np.exp(logits - np.max(logits))
        probs = exps / np.sum(exps)
        k = min(top_k, probs.shape[0])
        idx = np.argsort(probs)[::-1][:k]
        return HeadResult(
            classes=[int(i) for i in idx],
            probs_bp=[int(round(float(probs[i]) * 10_000)) for i in idx],
        )
