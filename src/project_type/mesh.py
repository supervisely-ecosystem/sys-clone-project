import supervisely as sly
from typing import List, Tuple
from supervisely import DatasetInfo

import globals as g


def clone(
    api: sly.Api,
    recreated_datasets: List[Tuple[DatasetInfo, DatasetInfo]],
):
    for dataset, dst_dataset in recreated_datasets:
        mesh_infos = api.mesh.get_list(dataset_id=dataset.id)
        progress = sly.Progress(
            message=f"Cloning meshes from dataset: {dataset.name}",
            total_cnt=len(mesh_infos),
        )
        src_ids = [info.id for info in mesh_infos]
        api.mesh.copy_batch(
            dst_dataset_id=dst_dataset.id,
            ids=src_ids,
            with_annotations=True,
            progress_cb=progress.iters_done_report,
        )
