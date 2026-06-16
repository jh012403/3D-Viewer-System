from __future__ import annotations

from pathlib import Path
from typing import Any

from pipelines.image_to_3d.reconstruction_head import ReconstructionHead, ReconstructionResult
from pipelines.image_to_3d.trellis_wrapper import run_trellis, trellis_contract


class TrellisHead(ReconstructionHead):
    name = "trellis"

    def availability(self) -> dict[str, Any]:
        return trellis_contract()

    def reconstruct(
        self,
        *,
        input_image: Path,
        multiview_info: dict[str, Any],
        work_dir: Path,
        output_dir: Path,
        object_name: str,
    ) -> ReconstructionResult:
        result = run_trellis(
            input_image=input_image,
            work_dir=work_dir,
            output_dir=output_dir,
            object_name=object_name,
        )
        summary = result.get("summary") or {}
        return ReconstructionResult(
            mesh_path=Path(str(result["mesh_path"])),
            requested_head=self.name,
            used_head=self.name,
            resolved_backend=self.name,
            mesh_backend=self.name,
            multiview_source="single_view_object_only_input",
            log_paths=result.get("log_paths") or {},
            raw_outputs={
                "trellis_summary": summary,
                "mesh_backend": "trellis",
                "mesh_backend_configured": "trellis",
                "input_image": str(input_image),
                "multiview_active": bool(multiview_info.get("active")),
            },
            notes=[
                "TRELLIS.2 reconstruction from normalized object-centric image input.",
                "Foreground extraction and normalization are executed before this reconstruction head.",
            ],
        )
