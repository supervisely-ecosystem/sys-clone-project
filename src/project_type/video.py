import supervisely as sly
from supervisely.video_annotation.key_id_map import KeyIdMap
from typing import List, Tuple
from supervisely import DatasetInfo

# import globals as g


def clone(
    api: sly.Api,
    recreated_datasets: List[Tuple[DatasetInfo, DatasetInfo]],
    project_meta,
):
    key_id_map = KeyIdMap()
    for dataset_pair in recreated_datasets:
        dataset, dst_dataset = dataset_pair
        videos_infos = api.video.get_list(dataset_id=dataset.id)
        progress = sly.Progress(
            message=f"Cloning videos from dataset: {dataset.name}",
            total_cnt=len(videos_infos),
        )
        for video_info in videos_infos:
            if video_info.link:
                new_video_info = api.video.upload_id(
                    dataset_id=dst_dataset.id,
                    name=video_info.name,
                    id=video_info.id,
                    meta=video_info.meta,
                )
            elif video_info.hash:
                new_video_info = api.video.upload_hash(
                    dataset_id=dst_dataset.id, name=video_info.name, hash=video_info.hash
                )
            else:
                sly.logger.warn(f"{video_info.name} have no hash or link. Item will be skipped.")
                continue
            ann_json = api.video.annotation.download(video_id=video_info.id)
            ann = sly.VideoAnnotation.from_json(
                data=ann_json, project_meta=project_meta, key_id_map=key_id_map
            )

            sly.logger.debug(f"New video info: {new_video_info}")
            sly.logger.debug(f"Type of new video info: {type(new_video_info)}")
            api.video.annotation.append(video_id=new_video_info.id, ann=ann, key_id_map=key_id_map)
            progress.iter_done_report()
