import supervisely as sly
from supervisely.api.module_api import ApiField
from supervisely.video_annotation.key_id_map import KeyIdMap
from supervisely.pointcloud_annotation.constants import OBJECT_KEY
from uuid import UUID
from typing import List, Tuple
from supervisely import DatasetInfo

import globals as g


def clone(
    api: sly.Api,
    project_id,
    recreated_datasets: List[Tuple[DatasetInfo, DatasetInfo]],
    project_meta,
):
    key_id_map_initial = KeyIdMap()
    key_id_map_new = KeyIdMap()
    for dataset_pair in recreated_datasets:
        dataset, dst_dataset = dataset_pair
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
                    data=ann_json, project_meta=project_meta, key_id_map=key_id_map_initial
                )

                api.pointcloud.annotation.append(
                    pointcloud_id=new_pcd_info.id, ann=ann, key_id_map=key_id_map_new
                )

                rel_images = api.pointcloud.get_list_related_images(id=pcd_info.id)
                if len(rel_images) > 0:
                    # payload for uploading related images referencing new pointcloud
                    rimg_infos = []
                    # mapping: related image hash -> figures json list (with OBJECT_KEY)
                    rimg_figures = {}

                    # prepare lists for batch download of source figures
                    rimg_ids = [rel_img[ApiField.ID] for rel_img in rel_images]
                    batch_rimg_figures = api.image.figure.download(
                        dataset_id=dataset.id, image_ids=rimg_ids
                    )

                    for rel_img in rel_images:
                        # Build upload payload for related images
                        rimg_infos.append(
                            {
                                ApiField.ENTITY_ID: new_pcd_info.id,
                                ApiField.NAME: rel_img[ApiField.NAME],
                                ApiField.HASH: rel_img[ApiField.HASH],
                                ApiField.META: rel_img[ApiField.META],
                            }
                        )

                        # Prepare figures json if any
                        rel_image_id = rel_img[ApiField.ID]
                        if rel_image_id in batch_rimg_figures:
                            figs = batch_rimg_figures[rel_image_id]
                            figs_json = []
                            for fig in figs:
                                fig_json = fig.to_json()
                                # replace OBJECT_ID by OBJECT_KEY for further processing
                                fig_json[OBJECT_KEY] = str(
                                    key_id_map_initial.get_object_key(fig_json[ApiField.OBJECT_ID])
                                )
                                fig_json.pop(ApiField.OBJECT_ID, None)
                                figs_json.append(fig_json)

                            # map by hash for later attachment
                            rimg_figures[rel_img[ApiField.HASH]] = figs_json

                    # Upload related images (by hash) and receive their new IDs
                    uploaded_rimgs = api.pointcloud.add_related_images(rimg_infos)

                    # Build hash -> new image id mapping
                    hash_to_id = {}
                    for info, uploaded in zip(rimg_infos, uploaded_rimgs):
                        img_hash = info.get(ApiField.HASH)
                        img_id = (
                            uploaded.get(ApiField.ID)
                            if isinstance(uploaded, dict)
                            else getattr(uploaded, "id", None)
                        )
                        if img_hash is not None and img_id is not None:
                            hash_to_id[img_hash] = img_id

                    # Prepare figures payload for upload
                    figures_payload = []
                    for img_hash, figs_json in rimg_figures.items():
                        if img_hash not in hash_to_id:
                            continue
                        img_id = hash_to_id[img_hash]
                        for fig in figs_json:
                            try:
                                fig[ApiField.ENTITY_ID] = img_id
                                fig[ApiField.DATASET_ID] = dst_dataset.id
                                fig[ApiField.PROJECT_ID] = project_id
                                fig[ApiField.OBJECT_ID] = key_id_map_new.get_object_id(
                                    UUID(fig[OBJECT_KEY])
                                )
                            except Exception:
                                continue
                        figures_payload.extend(figs_json)

                    # Upload figures in bulk if any
                    if len(figures_payload) > 0:
                        api.image.figure.create_bulk(
                            figures_json=figures_payload, dataset_id=dst_dataset.id
                        )
            else:
                sly.logger.warn(f"{pcd_info.name} have no hash. Item will be skipped.")
                continue

            progress.iter_done_report()
