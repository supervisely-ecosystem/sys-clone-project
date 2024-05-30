import supervisely as sly
import progress

import globals as g


def clone(api: sly.Api, project_id, datasets, project_meta: sly.ProjectMeta):
    keep_classes = []
    remove_classes = []
    meta_has_any_shapes = False
    parent_ids_map = {}
    for ds in datasets:
        if ds.parent_id and ds.parent_id not in parent_ids_map:
            parent_ids_map[ds.parent_id] = None
    for obj_cls in project_meta.obj_classes:
        if obj_cls.geometry_type == sly.AnyGeometry:
            meta_has_any_shapes = True
        if obj_cls.geometry_type == sly.Cuboid:
            remove_classes.append(obj_cls.name)
            sly.logger.warn(
                f"Class {obj_cls.name} has unsupported geometry type for images: Cuboid. It will be removed."
            )
        else:
            keep_classes.append(obj_cls.name)
    for dataset in datasets:
        if dataset.parent_id in parent_ids_map:
            parent_id = parent_ids_map[dataset.parent_id]
        else:
            parent_id = None
        dst_dataset = api.dataset.create(
            project_id=project_id,
            name=g.DATASET_NAME or dataset.name,
            description=dataset.description,
            change_name_if_conflict=True,
            parent_id=parent_id,
        )
        if dataset.id in parent_ids_map:
            parent_ids_map[dataset.id] = dst_dataset.id

        images_infos = api.image.get_list(dataset_id=dataset.id)
        images_names = [image_info.name for image_info in images_infos]
        images_ids = [image_info.id for image_info in images_infos]


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
            total=len(new_images_ids),
            is_size=False,
        )

        for batch_ids, batch_new_ids in zip(sly.batched(images_ids), sly.batched(new_images_ids)):
            batch_ann_jsons = api.annotation.download_json_batch(dataset.id, batch_ids)
            checked_ann_jsons = []
            for ann_json, img_id, new_img_id in zip(batch_ann_jsons, batch_ids, batch_new_ids):
                # * do not remove: convert to sly and back to json to fix possible geometric errors
                ann = sly.Annotation.from_json(ann_json, project_meta)
                # * filter labels with Cuboid geometry
                if len(remove_classes) > 0:
                    if meta_has_any_shapes:
                        ann_has_any_shapes = False
                        keep_labels = []
                        for label in ann.labels:
                            if label.geometry.geometry_name() == sly.Cuboid.geometry_name():
                                ann_has_any_shapes = True
                                continue
                            keep_labels.append(label)
                        if ann_has_any_shapes:
                            sly.logger.warn(
                                f"Some labels on the image ID:{img_id} have unsupported geometry: "
                                f"Cuboid. They will be removed (New image ID:{new_img_id})."
                            )
                            ann = ann.clone(labels=keep_labels)
                    else:
                        ann = ann.filter_labels_by_classes(keep_classes)
                checked_ann_jsons.append(ann.to_json())
            api.annotation.upload_jsons(
                img_ids=batch_new_ids, ann_jsons=checked_ann_jsons, progress_cb=progress_cb
            )
