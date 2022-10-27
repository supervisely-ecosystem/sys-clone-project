import supervisely as sly
from supervisely.api.module_api import ApiField
from supervisely.video_annotation.key_id_map import KeyIdMap

import globals as g


def clone(api: sly.Api, project_id, datasets, project_meta):
    key_id_map = KeyIdMap()
    for dataset in datasets:
        dst_dataset = api.dataset.create(
            project_id=project_id,
            name=g.DATASET_NAME or dataset.name,
            description=dataset.description,
            change_name_if_conflict=True,
        )
        pcds_infos = api.pointcloud.get_list(dataset_id=dataset.id)
        progress = sly.Progress(
            message=f"Cloning pointclouds from dataset: {dataset.name}",
            total_cnt=len(pcds_infos),
        )
        for pcd_info in pcds_infos:
            if pcd_info.hash:
                new_pcd_info = api.pointcloud.upload_hash(
                    dataset_id=dst_dataset.id,
                    name=pcd_info.name,
                    hash=pcd_info.hash,
                    meta=pcd_info.meta,
                )

                ann_json = api.pointcloud.annotation.download(pointcloud_id=pcd_info.id)
                ann = sly.PointcloudAnnotation.from_json(
                    data=ann_json, project_meta=project_meta, key_id_map=KeyIdMap()
                )

                api.pointcloud.annotation.append(
                    pointcloud_id=new_pcd_info.id, ann=ann, key_id_map=key_id_map
                )

                rel_images = api.pointcloud.get_list_related_images(id=pcd_info.id)
                if len(rel_images) != 0:
                    rimg_infos = []
                    for rel_img in rel_images:
                        rimg_infos.append(
                            {
                                ApiField.ENTITY_ID: new_pcd_info.id,
                                ApiField.NAME: rel_img[ApiField.NAME],
                                ApiField.HASH: rel_img[ApiField.HASH],
                                ApiField.META: rel_img[ApiField.META],
                            }
                        )
                    api.pointcloud.add_related_images(rimg_infos)
            else:
                sly.logger.warn(f"{pcd_info.name} have no hash. Item will be skipped.")
                continue

            progress.iter_done_report()
