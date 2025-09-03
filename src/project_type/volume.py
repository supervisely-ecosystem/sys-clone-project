import os
import supervisely as sly
from supervisely.video_annotation.key_id_map import KeyIdMap
from typing import List, Tuple
from supervisely import DatasetInfo

import globals as g


def clone(
    api: sly.Api,
    recreated_datasets: List[Tuple[DatasetInfo, DatasetInfo]],
    project_meta,
):
    key_id_map = KeyIdMap()
    for dataset_pair in recreated_datasets:
        dataset, dst_dataset = dataset_pair
        geometries_dir = f"geometries_{dataset.id}"
        sly.fs.mkdir(geometries_dir)
        volumes_infos = api.volume.get_list(dataset_id=dataset.id)
        progress = sly.Progress(
            message=f"Cloning volumes from dataset: {dataset.name}",
            total_cnt=len(volumes_infos),
        )
        for volume_info in volumes_infos:
            if volume_info.hash:
                new_volume_info = api.volume.upload_hash(
                    dataset_id=dst_dataset.id,
                    name=volume_info.name,
                    hash=volume_info.hash,
                    meta=volume_info.meta,
                )
            else:
                sly.logger.warn(f"{volume_info.name} have no hash. Item will be skipped.")
                continue

            ann_json = api.volume.annotation.download(volume_id=volume_info.id)
            ann = sly.VolumeAnnotation.from_json(
                data=ann_json, project_meta=project_meta, key_id_map=key_id_map
            )

            api.volume.annotation.append(
                volume_id=new_volume_info.id, ann=ann, key_id_map=key_id_map
            )

            if ann.spatial_figures:
                geometries = []
                for sf in ann_json.get("spatialFigures"):
                    sf_id = sf.get("id")
                    path = os.path.join(geometries_dir, f"{sf_id}.nrrd")
                    api.volume.figure.download_stl_meshes([sf_id], [path])
                    with open(path, "rb") as file:
                        geometry_bytes = file.read()
                    geometries.append(geometry_bytes)

                api.volume.figure.upload_sf_geometry(
                    ann.spatial_figures, geometries, key_id_map=key_id_map
                )
                del geometries
            progress.iter_done_report()

        sly.fs.remove_dir(geometries_dir)
