from __future__ import annotations

from pathlib import Path
from typing import Any

from pipelines.image_to_3d.hunyuan3d_wrapper import hunyuan3d_contract, run_hunyuan3d
from pipelines.image_to_3d.reconstruction_head import ReconstructionHead, ReconstructionResult


class Hunyuan3DHead(ReconstructionHead):
    name = "hunyuan3d"

    def availability(self) -> dict[str, Any]:
        return hunyuan3d_contract()

    def reconstruct(
        self,
        *,
        input_image: Path,
        multiview_info: dict[str, Any],
        work_dir: Path,
        output_dir: Path,
        object_name: str,
    ) -> ReconstructionResult:
        result = run_hunyuan3d(
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
                "hunyuan_summary": summary,
                "mesh_backend": "hunyuan3d",
                "mesh_backend_configured": "hunyuan3d",
                "input_image": str(input_image),
                "multiview_active": bool(multiview_info.get("active")),
            },
            notes=[
                "Hunyuan3D-2 reconstruction from normalized object-centric image input.",
                "Foreground extraction and normalization are executed before this reconstruction head.",
            ],
        )
