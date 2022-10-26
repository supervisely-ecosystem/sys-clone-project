import supervisely as sly
from supervisely.video_annotation.key_id_map import KeyIdMap

import progress

import globals as g


def clone(api: sly.Api, project_id, datasets, project_meta):
    key_id_map = KeyIdMap()
    for dataset in datasets:
        dst_dataset = api.dataset.create(
            project_id=project_id,
            name=dataset.name,
            description=dataset.description,
            change_name_if_conflict=True,
        )

        videos_infos = api.video.get_list(dataset_id=dataset.id)
        progress = sly.Progress(message=f"Cloning videos from dataset: {dataset.name}", total_cnt=len(videos_infos))
        for video_info in videos_infos:
            if video_info.link:
                new_video_info = api.video.upload_link(dataset_id=dst_dataset.id, name=video_info.name, link=video_info.link)
            elif video_info.hash:
                new_video_info = api.video.upload_hash(dataset_id=dst_dataset.id, name=video_info.name, hash=video_info.hash)
            else:
                sly.logger.warn(f"{video_info.name} have no hash or link. Item will be skipped.")
                continue
            
            ann_json = api.video.annotation.download(video_id=video_info.id)
            ann = sly.VideoAnnotation.from_json(data=ann_json, project_meta=project_meta, key_id_map=key_id_map)
            api.video.annotation.append(video_id=new_video_info.id, ann=ann, key_id_map=key_id_map)
            progress.iter_done_report()
