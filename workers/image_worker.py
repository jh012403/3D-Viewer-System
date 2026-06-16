from __future__ import annotations

from workers.base_worker import BaseWorker, build_arg_parser


def main() -> None:
    args = build_arg_parser("Run the image-to-3D worker.").parse_args()
    BaseWorker("image_to_3d", "pipelines.image_to_3d.cli").run(once=args.once)


if __name__ == "__main__":
    main()

