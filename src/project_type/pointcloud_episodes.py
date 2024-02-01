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

        pcd_episodes_infos = api.pointcloud_episode.get_list(dataset_id=dataset.id)
        ann_json = api.pointcloud_episode.annotation.download(dataset_id=dataset.id)
        ann = sly.PointcloudEpisodeAnnotation.from_json(
            data=ann_json, project_meta=project_meta, key_id_map=KeyIdMap()
        )
        
        frame_to_pointcloud_ids = {}

        progress = sly.Progress(
            message=f"Cloning pointcloud episodes from dataset: {dataset.name}",
            total_cnt=len(pcd_episodes_infos),
        )
        for pcd_episode_info in pcd_episodes_infos:
            if pcd_episode_info.hash:
                new_pcd_episode_info = api.pointcloud_episode.upload_hash(
                    dataset_id=dst_dataset.id,
                    name=pcd_episode_info.name,
                    hash=pcd_episode_info.hash,
                    meta=pcd_episode_info.meta,
                )

                frame_to_pointcloud_ids[new_pcd_episode_info.meta["frame"]] = new_pcd_episode_info.id
                
                rel_images = api.pointcloud_episode.get_list_related_images(id=pcd_episode_info.id)
                if len(rel_images) != 0:
                    rimg_infos = []
                    for rel_img in rel_images:
                        rimg_infos.append(
                            {
                                ApiField.ENTITY_ID: new_pcd_episode_info.id,
                                ApiField.NAME: rel_img[ApiField.NAME],
                                ApiField.HASH: rel_img[ApiField.HASH],
                                ApiField.META: rel_img[ApiField.META],
                            }
                        )
                    api.pointcloud_episode.add_related_images(rimg_infos)
            else:
                sly.logger.warn(
                    f"{pcd_episode_info.name} have no hash. Item will be skipped."
                )
                continue

            progress.iter_done_report()

        api.pointcloud_episode.annotation.append(
            dataset_id=dst_dataset.id,
            ann=ann,
            frame_to_pointcloud_ids=frame_to_pointcloud_ids,
            key_id_map=key_id_map,
        )
