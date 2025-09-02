import os
import supervisely as sly
from supervisely.api.module_api import ApiField
from supervisely.video_annotation.key_id_map import KeyIdMap
from supervisely.pointcloud_annotation.constants import OBJECT_KEY
from uuid import UUID

import globals as g


def clone(api: sly.Api, project_id, src_ds_tree, project_meta):
    key_id_map_initial = KeyIdMap()
    key_id_map_new = KeyIdMap()
    src_dst_ds_id_map = {}
    sly.logger.info(f"Source to Destination Dataset ID Map: {src_dst_ds_id_map}")
    # Mapping from pointcloud ID -> {image_hash: image_id}
    pcl_to_hash_to_id = {}
    # Mapping from pointcloud ID -> {image_hash: [figures_json]}
    pcl_to_rimg_figures = {}

    def _create_datasets_tree(src_ds_tree, parent_id=None, first_ds=False):
        for src_ds, nested_src_ds_tree in src_ds_tree.items():
            sly.logger.info(f"Cloning dataset: {src_ds.name} (ID: {src_ds.id})")    
            dst_ds = api.dataset.create(
                project_id=project_id,
                name=g.DATASET_NAME if first_ds else src_ds.name,
                description=src_ds.description,
                change_name_if_conflict=True,
                parent_id=parent_id,
            )
            sly.logger.info(f"Created dataset: {dst_ds.name} (ID: {dst_ds.id})")    
            first_ds = False
            src_dst_ds_id_map[src_ds.id] = dst_ds.id

            info_ds = api.dataset.get_info_by_id(src_ds.id)
            if info_ds.custom_data:
                api.dataset.update_custom_data(dst_ds.id, info_ds.custom_data)

            _create_datasets_tree(nested_src_ds_tree, parent_id=dst_ds.id)

            sly.logger.info(f"Cloned dataset: {src_ds.name} (ID: {src_ds.id}) to {dst_ds.name} (ID: {dst_ds.id})")  

    def _copy_dataset_items(src_ds_id, dst_ds_id):
        dataset = api.dataset.get_info_by_id(src_ds_id)
        
        pcd_episodes_infos = api.pointcloud_episode.get_list(dataset_id=src_ds_id)
        ann_json = api.pointcloud_episode.annotation.download(dataset_id=src_ds_id)
        ann = sly.PointcloudEpisodeAnnotation.from_json(
            data=ann_json, project_meta=project_meta, key_id_map=key_id_map_initial
        )

        frame_to_pointcloud_ids = {}

        progress = sly.Progress(
            message=f"Cloning pointcloud episodes from dataset: {dataset.name}",
            total_cnt=len(pcd_episodes_infos),
        )
        for pcd_episode_info in pcd_episodes_infos:
            if pcd_episode_info.hash:
                new_pcd_episode_info = api.pointcloud_episode.upload_hash(
                    dataset_id=dst_ds_id,
                    name=pcd_episode_info.name,
                    hash=pcd_episode_info.hash,
                    meta=pcd_episode_info.meta,
                )

                frame_to_pointcloud_ids[new_pcd_episode_info.meta["frame"]] = (
                    new_pcd_episode_info.id
                )

                # --- Handle related images and their figures ---
                rel_images = api.pointcloud_episode.get_list_related_images(id=pcd_episode_info.id)
                if len(rel_images) > 0:
                    rimg_infos = []  # payload for add_related_images
                    rimg_ids = [rimg[ApiField.ID] for rimg in rel_images]

                    # Download figures for related images in batch
                    batch_rimg_figures = api.image.figure.download(
                        dataset_id=src_ds_id, image_ids=rimg_ids
                    )

                    for rel_img in rel_images:
                        rimg_infos.append(
                            {
                                ApiField.ENTITY_ID: new_pcd_episode_info.id,
                                ApiField.NAME: rel_img[ApiField.NAME],
                                ApiField.HASH: rel_img[ApiField.HASH],
                                ApiField.META: rel_img[ApiField.META],
                            }
                        )

                        # Process figures if present
                        rel_image_id = rel_img[ApiField.ID]
                        if rel_image_id in batch_rimg_figures:
                            figs = batch_rimg_figures[rel_image_id]
                            figs_json = []
                            for fig in figs:
                                fig_json = fig.to_json()
                                # Substitute OBJECT_ID with OBJECT_KEY
                                fig_json[OBJECT_KEY] = str(
                                    key_id_map_initial.get_object_key(fig_json[ApiField.OBJECT_ID])
                                )
                                fig_json.pop(ApiField.OBJECT_ID, None)
                                figs_json.append(fig_json)

                            pcl_to_rimg_figures.setdefault(new_pcd_episode_info.id, {})[
                                rel_img[ApiField.HASH]
                            ] = figs_json

                    # Upload related images metadata (no binaries, hash reuse)
                    uploaded_rimgs = api.pointcloud_episode.add_related_images(rimg_infos)

                    # Build mapping hash -> new img_id for later figures upload
                    for info, uploaded in zip(rimg_infos, uploaded_rimgs):
                        img_hash = info.get(ApiField.HASH)
                        img_id = (
                            uploaded.get(ApiField.ID)
                            if isinstance(uploaded, dict)
                            else getattr(uploaded, "id", None)
                        )
                        if img_hash is not None and img_id is not None:
                            pcl_to_hash_to_id.setdefault(new_pcd_episode_info.id, {})[
                                img_hash
                            ] = img_id
            else:
                sly.logger.warn(f"{pcd_episode_info.name} have no hash. Item will be skipped.")
                continue

            progress.iter_done_report()

        # Append annotation once for the whole dataset (object IDs will be generated here)
        api.pointcloud_episode.annotation.append(
            dataset_id=dst_ds_id,
            ann=ann,
            frame_to_pointcloud_ids=frame_to_pointcloud_ids,
            key_id_map=key_id_map_new,
        )

        # After annotation append, key_id_map_new contains mapping OBJECT_KEY -> new OBJECT_ID
        # Prepare and upload figures for related images
        figures_payload = []
        for pcl_id, hash_to_figs in pcl_to_rimg_figures.items():
            hash_map = pcl_to_hash_to_id.get(pcl_id, {})
            for img_hash, figs_json in hash_to_figs.items():
                if img_hash not in hash_map:
                    continue
                img_id = hash_map[img_hash]
                for fig in figs_json:
                    try:
                        fig[ApiField.ENTITY_ID] = img_id
                        fig[ApiField.DATASET_ID] = dst_ds_id
                        fig[ApiField.PROJECT_ID] = project_id
                        fig[ApiField.OBJECT_ID] = key_id_map_new.get_object_id(
                            UUID(fig[OBJECT_KEY])
                        )
                    except Exception:
                        continue
                figures_payload.extend(figs_json)

        if len(figures_payload) > 0:
            api.image.figure.create_bulk(figures_json=figures_payload, dataset_id=dst_ds_id)

            sly.logger.info(f"Uploaded figures for dataset: {dst_ds_id}")   

    def _process_datasets_tree(src_ds_tree):
        for src_ds, nested_src_ds_tree in src_ds_tree.items():
            # copy pointcloud episodes and annotations from src_ds to dst_ds
            _copy_dataset_items(src_ds.id, src_dst_ds_id_map[src_ds.id])

            # process nested datasets
            _process_datasets_tree(nested_src_ds_tree)

    # create hierarchy of datasets
    _create_datasets_tree(src_ds_tree, first_ds=g.DATASET_NAME not in ["", None])

    # process datasets tree
    _process_datasets_tree(src_ds_tree)
