import supervisely as sly
import progress

import globals as g


def clone(
    api: sly.Api, project_id, src_ds_tree, project_meta: sly.ProjectMeta, similar_graphs
):
    keep_classes = []
    remove_classes = []
    meta_has_any_shapes = False
    src_dst_ds_id_map = {}

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
            dst_project_meta_json = api.project.get_meta(g.DEST_PROJECT_ID)
            dst_project_meta = sly.ProjectMeta.from_json(dst_project_meta_json)
            for obj_class in project_meta.obj_classes:
                if not dst_project_meta.get_obj_class(obj_class.name):
                    dst_project_meta = dst_project_meta.add_obj_class(obj_class)
                    api.project.update_meta(id=g.DEST_PROJECT_ID, meta=dst_project_meta)

        for batch_ids, batch_new_ids in zip(sly.batched(images_ids), sly.batched(new_images_ids)):
            batch_ann_jsons = api.annotation.download_json_batch(src_ds_id, batch_ids)
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
    _create_datasets_tree(src_ds_tree, first_ds=g.DATASET_NAME is not None)

    # process datasets tree
    _process_datasets_tree(src_ds_tree)
