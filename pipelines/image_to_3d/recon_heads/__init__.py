from __future__ import annotations

from pipelines.image_to_3d.reconstruction_head import ReconstructionHead, normalize_head_name
from pipelines.image_to_3d.recon_heads.hunyuan3d_head import Hunyuan3DHead
from pipelines.image_to_3d.recon_heads.trellis_head import TrellisHead


HEAD_REGISTRY: dict[str, type[ReconstructionHead]] = {
    "trellis": TrellisHead,
    "hunyuan3d": Hunyuan3DHead,
}


def get_reconstruction_head(name: str) -> ReconstructionHead:
    normalized = normalize_head_name(name)
    try:
        return HEAD_REGISTRY[normalized]()
    except KeyError as exc:
        available = ", ".join(sorted(HEAD_REGISTRY))
        raise ValueError(f"Unsupported reconstruction head '{name}'. Available heads: {available}.") from exc


def list_reconstruction_heads() -> list[str]:
    return sorted(HEAD_REGISTRY)
