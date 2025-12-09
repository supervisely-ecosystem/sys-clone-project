import supervisely as sly
from supervisely.video_annotation.key_id_map import KeyIdMap
from typing import Callable, List, Tuple
from supervisely import DatasetInfo
from supervisely.project.project_settings import LabelingInterface


def _get_ann_progress_cb(total_cnt: int) -> Callable[[int], None]:
    progress = sly.Progress(message="Uploading annotations", total_cnt=total_cnt, is_size=False)
    progress_cb = progress.iters_done_report
    return progress_cb


def clone(
    api: sly.Api,
    recreated_datasets: List[Tuple[DatasetInfo, DatasetInfo]],
    project_meta,
):
    key_id_map = KeyIdMap()
    with sly.ApiContext(api=api, project_meta=project_meta):
        for dataset_pair in recreated_datasets:
            dataset, dst_dataset = dataset_pair
            videos_infos = api.video.get_list(dataset_id=dataset.id)
            progress = sly.Progress(
                message=f"Cloning videos from dataset: {dataset.name}",
                total_cnt=len(videos_infos),
            )
            anns = []
            new_video_infos = []
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
                    sly.logger.warning(
                        f"{video_info.name} have no hash or link. Item will be skipped."
                    )
                    continue
                ann_json = api.video.annotation.download(video_id=video_info.id)
                ann = sly.VideoAnnotation.from_json(
                    data=ann_json, project_meta=project_meta, key_id_map=key_id_map
                )
                new_video_infos.append(new_video_info)

                sly.logger.debug(f"New video info: {new_video_info}")
                sly.logger.debug(f"Type of new video info: {type(new_video_info)}")

                if project_meta.labeling_interface != LabelingInterface.MULTIVIEW:
                    ann_progress_cb = _get_ann_progress_cb(total_cnt=len(ann.figures))
                    api.video.annotation.append(
                        video_id=new_video_info.id, ann=ann, progress_cb=ann_progress_cb
                    )
                else:
                    anns.append(ann)
                progress.iter_done_report()
            if project_meta.labeling_interface == LabelingInterface.MULTIVIEW:
                vid_ids = [v.id for v in new_video_infos]
                figures_cnt = sum(len(ann.figures) for ann in anns)
                ann_progress_cb = _get_ann_progress_cb(total_cnt=figures_cnt)
                api.video.annotation.upload_anns_multiview(vid_ids, anns, ann_progress_cb)
