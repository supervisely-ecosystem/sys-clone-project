import supervisely as sly
import os
from supervisely import DatasetInfo
from typing import List, Tuple, Generator
import globals as g
import functions as f
from workflow import Workflow
import project_type.image as image
import project_type.video as video
import project_type.volume as volume
import project_type.pointcloud as pointcloud
import project_type.pointcloud_episodes as pointcloud_episodes


@g.my_app.callback("clone-data")
@sly.timeit
def clone_data(api: sly.Api, task_id, context, state, app_logger):
    project = api.project.get_info_by_id(g.PROJECT_ID)
    workflow = Workflow(api)
    # -------------------------------------- Add Workflow Input -------------------------------------- #
    workflow.add_input(project.id)
    # ----------------------------------------------- - ---------------------------------------------- #

    project_meta_json = api.project.get_meta(project.id, with_settings=True)
    project_meta = sly.ProjectMeta.from_json(data=project_meta_json)
    project_type = project_meta.project_type

    dst_project = None
    similar_graphs = []
    if g.DEST_PROJECT_ID:
        dst_project = api.project.get_info_by_id(g.DEST_PROJECT_ID)
        if dst_project is None:
            sly.logger.warning(
                f"Destination project with id={g.DEST_PROJECT_ID} not found. "
                f"New destination project will be created.",
            )
        elif dst_project.type != project.type:
            sly.logger.warning(
                f"Destination project type ({dst_project.type}) != source project type ({project.type}). "
                f"New destination project will be created.",
            )
            dst_project = None
        else:
            if project.type == "images" and dst_project:
                # get destination project meta
                dst_project_meta_json = api.project.get_meta(dst_project.id)
                dst_project_meta = sly.ProjectMeta.from_json(dst_project_meta_json)
                # chech if there are any graph objects in source and destination project metas
                src_obj_classes = project_meta.obj_classes
                dst_obj_classes = dst_project_meta.obj_classes
                src_graph_names = [
                    obj_class.name
                    for obj_class in src_obj_classes
                    if obj_class.geometry_type == sly.GraphNodes
                ]
                dst_graph_names = [
                    obj_class.name
                    for obj_class in dst_obj_classes
                    if obj_class.geometry_type == sly.GraphNodes
                ]
                if len(src_graph_names) > 0 and len(dst_graph_names) > 0:
                    # check if there are graph objects with the same name
                    if len(set(src_graph_names).intersection(set(dst_graph_names))) > 0:
                        # check if they have same number of nodes and same node labels
                        for src_name in src_graph_names:
                            if src_name in dst_graph_names:
                                src_obj_class = project_meta.get_obj_class(src_name)
                                dst_obj_class = dst_project_meta.get_obj_class(src_name)
                                src_geometry_config = src_obj_class.geometry_config
                                dst_geometry_config = dst_obj_class.geometry_config
                                # check if graphs have the same number of nodes
                                if len(dst_geometry_config["nodes"]) == len(
                                    src_geometry_config["nodes"]
                                ):
                                    # check if graphs have the same node labels
                                    dst_node_labels = [
                                        value["label"]
                                        for value in dst_geometry_config["nodes"].values()
                                    ]
                                    src_node_labels = [
                                        value["label"]
                                        for value in src_geometry_config["nodes"].values()
                                    ]
                                    if set(dst_node_labels) == set(src_node_labels):
                                        similar_graphs.append(src_name)
            if len(similar_graphs) == 0:
                try:
                    api.project.merge_metas(project.id, dst_project.id)
                except Exception as e:
                    sly.logger.warn(
                        f"Can not merge meta of source project and destination project: {str(e)}. "
                        f"New destination project will be created."
                    )
                    dst_project = None

    if dst_project is None:
        dst_project = api.project.create(
            workspace_id=g.DEST_WORKSPACE_ID,
            name=g.PROJECT_NAME or project.name,
            type=project.type,
            description=project.description,
            change_name_if_conflict=True,
        )
        api.project.update_meta(id=dst_project.id, meta=project_meta)

    if project_type in [str(sly.ProjectType.IMAGES), str(sly.ProjectType.POINT_CLOUD_EPISODES)]:
        datasets_tree = api.dataset.get_tree(
            project.id
        )  # Dict[DatasetInfo, Dict[DatasetInfo, Dict[...]]] (recursively)
        if g.DATASET_ID:

            def _find_datasets_tree_by_id(datasets_tree, dataset_id):
                for dataset, nested_datasets_tree in datasets_tree.items():
                    if dataset.id == dataset_id:
                        return {dataset: nested_datasets_tree}
                    nested_result = _find_datasets_tree_by_id(nested_datasets_tree, dataset_id)
                    if nested_result is not None:
                        return nested_result
                return

            datasets_tree = _find_datasets_tree_by_id(datasets_tree, g.DATASET_ID)

    elif g.DATASET_ID:
        datasets = [api.dataset.get_info_by_id(g.DATASET_ID)]
    else:
        datasets = api.dataset.get_list(project.id, recursive=True)

        log_msg = f.get_datasets_tree_msg(datasets)
        sly.logger.info("Datasets to clone:", extra={"datasets_tree": log_msg}) 

    if project_type == str(sly.ProjectType.IMAGES):
        image.clone(
            api=api,
            project_id=dst_project.id,
            src_ds_tree=datasets_tree,
            project_meta=project_meta,
            similar_graphs=similar_graphs,
        )
    elif project_type == str(sly.ProjectType.VIDEOS):
        recreated_datasets = recreated(api, project.id, dst_project.id)
        video.clone(
            api=api,
            project_id=dst_project.id,
            recreated_dataset=recreated_datasets,
            project_meta=project_meta,
        )
    elif project_type == str(sly.ProjectType.VOLUMES):
        volume.clone(
            api=api,
            project_id=dst_project.id,
            datasets=datasets,
            project_meta=project_meta,
        )
    elif project_type == str(sly.ProjectType.POINT_CLOUDS):
        pointcloud.clone(
            api=api,
            project_id=dst_project.id,
            datasets=datasets,
            project_meta=project_meta,
        )
    elif project_type == str(sly.ProjectType.POINT_CLOUD_EPISODES):
        pointcloud_episodes.clone(
            api=api,
            project_id=dst_project.id,
            src_ds_tree=datasets_tree,
            project_meta=project_meta,
        )
    else:
        raise NotImplementedError(f"Unknown project type: {project_type}")

    api.app.set_output_project(
        task_id=g.TASK_ID, project_id=dst_project.id, project_name=dst_project.name
    )

    # -------------------------------------- Add Workflow Output ------------------------------------- #
    workflow.add_output(dst_project.id, g.DATASET_ID)
    # ----------------------------------------------- - ---------------------------------------------- #

    g.my_app.stop()


def main():
    sly.logger.info(
        "Script arguments",
        extra={
            "INPUT TEAM_ID": g.TEAM_ID,
            "INPUT WORKSPACE_ID": g.WORKSPACE_ID,
            "INPUT PROJECT_ID": g.PROJECT_ID,
            "OUTPUT TEAM_ID": g.DEST_TEAM_ID,
            "OUTPUT WORKSPACE_ID": g.DEST_WORKSPACE_ID,
            "OUTPUT PROJECT_ID": g.DEST_PROJECT_ID,
        },
    )

    g.my_app.run(initial_events=[{"command": "clone-data"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main, log_for_agent=False)


def recreated(
    api: sly.Api, src_project_id: int, dst_project_id: int
) -> List[Tuple[DatasetInfo, DatasetInfo]]:
    return list(recreate(api, src_project_id, dst_project_id))

def recreate(
    api: sly.Api, src_project_id: int, dst_project_id: int
) -> Generator[Tuple[DatasetInfo, DatasetInfo], None, None]:

    dataset_map = {}
    for parents, src_dataset_info in api.dataset.tree(src_project_id):
        if len(parents) > 0:
            parent = f"{os.path.sep}".join(parents)
            parent_id = dataset_map.get(parent)
        else:
            # If the dataset is in the root of the project, parent_id should be None.
            # And the path (key) will be just a name of the dataset.
            parent = ""
            parent_id = None

        dst_dataset_info = api.dataset.create(
            dst_project_id, src_dataset_info.name, parent_id=parent_id
        )
        dataset_map[os.path.join(parent, dst_dataset_info.name)] = dst_dataset_info.id

        yield src_dataset_info, dst_dataset_info


if __name__ == "__main__":
    sly.main_wrapper("main", main, log_for_agent=False)