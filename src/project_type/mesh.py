import supervisely as sly
from supervisely._utils import batched
from typing import List, Tuple
from supervisely import DatasetInfo

import globals as g


def clone(
    api: sly.Api,
    recreated_datasets: List[Tuple[DatasetInfo, DatasetInfo]],
    project_meta: sly.ProjectMeta,
):
    for dataset, dst_dataset in recreated_datasets:
        mesh_infos = api.mesh.get_list(dataset_id=dataset.id)
        dst_project_id = api.dataset.get_info_by_id(dst_dataset.id).project_id
        progress = sly.Progress(
            message=f"Cloning meshes from dataset: {dataset.name}",
            total_cnt=len(mesh_infos),
        )
        for batch in batched(mesh_infos, batch_size=10):
            src_ids = [info.id for info in batch]
            names = [info.name for info in batch]
            metas = [info.meta for info in batch]

            new_mesh_infos = api.mesh.upload_ids(
                dataset_id=dst_dataset.id,
                names=names,
                ids=src_ids,
                metas=metas,
            )
            dst_ids = [info.id for info in new_mesh_infos]

            api.mesh.annotation.copy_batch(
                src_dataset_id=dataset.id,
                src_mesh_ids=src_ids,
                dst_mesh_ids=dst_ids,
                dst_project_id=dst_project_id,
            )

            progress.iters_done_report(len(batch))
