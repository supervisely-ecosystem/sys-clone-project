import supervisely as sly
import progress

import globals as g


def clone(api: sly.Api, project_id, datasets, project_meta):
    for dataset in datasets:
        dst_dataset = api.dataset.create(
            project_id=project_id,
            name=g.DATASET_NAME or dataset.name,
            description=dataset.description,
            change_name_if_conflict=True,
        )

        images_infos = api.image.get_list(dataset_id=dataset.id)
        images_names = [image_info.name for image_info in images_infos]
        images_ids = [image_info.id for image_info in images_infos]

        ann_jsons = [
            ann_info.annotation for ann_info in api.annotation.get_list(dataset_id=dataset.id)
        ]

        progress_cb = progress.get_progress_cb(
            api,
            task_id=g.TASK_ID,
            message="Uploading images",
            total=len(images_ids),
            is_size=False,
        )

        new_images_infos = api.image.upload_ids(
            dataset_id=dst_dataset.id,
            names=images_names,
            ids=images_ids,
            progress_cb=progress_cb,
        )
        new_images_ids = [image_info.id for image_info in new_images_infos]

        progress_cb = progress.get_progress_cb(
            api,
            task_id=g.TASK_ID,
            message="Uploading annotations",
            total=len(ann_jsons),
            is_size=False,
        )

        for batch_anns, batch_ids in zip(sly.batched(ann_jsons), sly.batched(new_images_ids)):
            checked_ann_jsons = []
            for ann_json in batch_anns:
                # convert to Annotation object and back to json to check/fix geometry correctness
                ann = sly.Annotation.from_json(ann_json, project_meta)
                checked_ann_jsons.append(ann.to_json())
            api.annotation.upload_jsons(
                img_ids=batch_ids, ann_jsons=checked_ann_jsons, progress_cb=progress_cb
            )
