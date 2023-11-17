import os
import supervisely as sly
from supervisely.video_annotation.key_id_map import KeyIdMap

import globals as g


def clone(api: sly.Api, project_id, datasets, project_meta):
    key_id_map = KeyIdMap()
    for dataset in datasets:
        geometries_dir = f"geometries_{dataset.id}"
        sly.fs.mkdir(geometries_dir)
        dst_dataset = api.dataset.create(
            project_id=project_id,
            name=g.DATASET_NAME or dataset.name,
            description=dataset.description,
            change_name_if_conflict=True,
        )
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
