import supervisely as sly
import progress

import globals as g


def _drop_corrupted_tags(ann_json):
    """Remove tag entries with no "name" (e.g. tags whose tag meta was deleted
    from the project but the tag instance itself was left enabled) so a single
    corrupted image doesn't crash the whole clone with KeyError('name').
    Returns the cleaned annotation json and a list of dropped tag ids."""

    dropped_tag_ids = []

    def _filter(tags):
        clean = []
        for tag_json in tags or []:
            if not tag_json.get("name"):
                dropped_tag_ids.append(tag_json.get("tagId"))
                continue
            clean.append(tag_json)
        return clean

    ann_json["tags"] = _filter(ann_json.get("tags"))
    for label_json in ann_json.get("objects", []):
        label_json["tags"] = _filter(label_json.get("tags"))
    return ann_json, dropped_tag_ids


def clone(api: sly.Api, project_id, src_ds_tree, project_meta: sly.ProjectMeta, similar_graphs):
    keep_classes = []
    remove_classes = []
    meta_has_any_shapes = False
    src_dst_ds_id_map = {}
    corrupted_tags_stats = {}  # tagId -> list of source image ids with that corrupted tag

    for obj_cls in project_meta.obj_classes:
        if obj_cls.geometry_type == sly.AnyGeometry:
            meta_has_any_shapes = True
        if obj_cls.geometry_type == sly.Cuboid:
            remove_classes.append(obj_cls.name)
            sly.logger.warning(
                f"Class {obj_cls.name} has unsupported geometry type for images: Cuboid. It will be removed."
            )
        else:
            keep_classes.append(obj_cls.name)

    def _create_datasets_tree(src_ds_tree, parent_id=None, first_ds=False):
        for src_ds, nested_src_ds_tree in src_ds_tree.items():
            dst_ds = api.dataset.create(
                project_id=project_id,
                name=g.DATASET_NAME if first_ds else src_ds.name,
                description=src_ds.description,
                change_name_if_conflict=True,
                parent_id=parent_id,
            )
            first_ds = False
            src_dst_ds_id_map[src_ds.id] = dst_ds.id

            info_ds = api.dataset.get_info_by_id(src_ds.id)
            if info_ds.custom_data:
                api.dataset.update_custom_data(dst_ds.id, info_ds.custom_data)

            _create_datasets_tree(nested_src_ds_tree, parent_id=dst_ds.id)

    def _copy_dataset_items(src_ds_id, dst_ds_id):
        images_infos = api.image.get_list(dataset_id=src_ds_id)
        images_names = [image_info.name for image_info in images_infos]
        images_ids = [image_info.id for image_info in images_infos]
        images_metas = [image_info.meta for image_info in images_infos]

        progress_cb = progress.get_progress_cb(
            api,
            task_id=g.TASK_ID,
            message="Uploading images",
            total=len(images_ids),
            is_size=False,
        )

        new_images_infos = api.image.upload_ids(
            dataset_id=dst_ds_id,
            names=images_names,
            ids=images_ids,
            progress_cb=progress_cb,
            metas=images_metas,
        )
        new_images_ids = [image_info.id for image_info in new_images_infos]

        progress_cb = progress.get_progress_cb(
            api,
            task_id=g.TASK_ID,
            message="Uploading annotations",
            total=len(new_images_ids),
            is_size=False,
        )

        have_similar_graphs = False
        if len(similar_graphs) > 0:
            have_similar_graphs = True
            dst_project_meta_json = api.project.get_meta(g.DEST_PROJECT_ID, with_settings=True)
            dst_project_meta = sly.ProjectMeta.from_json(dst_project_meta_json)
            for obj_class in project_meta.obj_classes:
                if not dst_project_meta.get_obj_class(obj_class.name):
                    dst_project_meta = dst_project_meta.add_obj_class(obj_class)
                    api.project.update_meta(id=g.DEST_PROJECT_ID, meta=dst_project_meta)

        for batch_ids, batch_new_ids in zip(sly.batched(images_ids), sly.batched(new_images_ids)):
            batch_ann_jsons = api.annotation.download_json_batch(src_ds_id, batch_ids)
            checked_ann_jsons = []
            batch_corrupted = {}  # tagId -> list of image ids in this batch
            for ann_json, img_id, new_img_id in zip(batch_ann_jsons, batch_ids, batch_new_ids):
                ann_json, dropped_tag_ids = _drop_corrupted_tags(ann_json)
                for tag_id in dropped_tag_ids:
                    corrupted_tags_stats.setdefault(tag_id, []).append(img_id)
                    batch_corrupted.setdefault(tag_id, []).append(img_id)
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
                            sly.logger.warning(
                                f"Some labels on the image ID:{img_id} have unsupported geometry: "
                                f"Cuboid. They will be removed (New image ID:{new_img_id})."
                            )
                            ann = ann.clone(labels=keep_labels)
                    else:
                        ann = ann.filter_labels_by_classes(keep_classes)
                # check if annotation contains similar graphs
                if have_similar_graphs:
                    new_labels = []
                    for label in ann.labels:
                        if label.obj_class.name in similar_graphs:
                            # get source and destination geometry config
                            src_obj_class = label.obj_class
                            dst_obj_class = dst_project_meta.get_obj_class(label.obj_class.name)
                            src_geometry_config = src_obj_class.geometry_config
                            dst_geometry_config = dst_obj_class.geometry_config
                            # create dictionary to match original labels by node ids
                            src_node_id2label = {}
                            for node_id, node in src_geometry_config["nodes"].items():
                                src_node_id2label[node_id] = node["label"]
                            # create dictionary to get destination node_ids by labels
                            dst_label2_node_id = {}
                            for node_id, node in dst_geometry_config["nodes"].items():
                                dst_label2_node_id[node["label"]] = node_id
                            # create new nodes dictioanry with destination node ids and original nodes
                            src_geometry = label.geometry
                            src_nodes = src_geometry.nodes
                            new_nodes = {}
                            for node_id, node in src_nodes.items():
                                src_node_label = src_node_id2label[node_id]
                                dst_node_id = dst_label2_node_id[src_node_label]
                                new_nodes[dst_node_id] = node
                            new_geometry = sly.GraphNodes(new_nodes)
                            new_label = sly.Label(new_geometry, dst_obj_class)
                            new_labels.append(new_label)
                        else:
                            new_labels.append(label)
                    ann = ann.clone(labels=new_labels)
                checked_ann_jsons.append(ann.to_json())
            if batch_corrupted:
                sly.logger.debug(
                    "Corrupted tags (no name in JSON) were skipped in this batch.",
                    extra={
                        "dataset_id": src_ds_id,
                        "corrupted_tags": {
                            str(tag_id): img_ids for tag_id, img_ids in batch_corrupted.items()
                        },
                    },
                )
            api.annotation.upload_jsons(
                img_ids=batch_new_ids, ann_jsons=checked_ann_jsons, progress_cb=progress_cb
            )

    def _process_datasets_tree(src_ds_tree):
        for src_ds, nested_src_ds_tree in src_ds_tree.items():
            # copy images and annotations from src_ds to dst_ds
            _copy_dataset_items(src_ds.id, src_dst_ds_id_map[src_ds.id])

            # process nested datasets
            _process_datasets_tree(nested_src_ds_tree)

    # create hierarchy of datasets
    _create_datasets_tree(src_ds_tree, first_ds=g.DATASET_NAME not in ["", None])

    # process datasets tree
    _process_datasets_tree(src_ds_tree)

    for tag_id, img_ids in corrupted_tags_stats.items():
        examples = ", ".join(str(img_id) for img_id in img_ids[:10])
        if len(img_ids) > 10:
            examples += f", ... (and {len(img_ids) - 10} more)"
        sly.logger.warning(
            f"Found {len(img_ids)} images with a corrupted tag (tagId={tag_id}, no name in JSON) - "
            f"the tag meta was likely deleted from the project. "
            f"These tags were skipped during clone. Example image IDs: {examples}"
        )
