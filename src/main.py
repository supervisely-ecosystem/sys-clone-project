import supervisely as sly

import globals as g
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
    if g.DEST_PROJECT_ID:
        dst_project = api.project.get_info_by_id(g.DEST_PROJECT_ID)
        if dst_project is None:
            sly.logger.warn(
                f"Destination project with id={g.DEST_PROJECT_ID} not found. "
                f"New destination project will be created.",
            )
        elif dst_project.type != project.type:
            sly.logger.warn(
                f"Destination project type ({dst_project.type}) != source project type ({project.type}). "
                f"New destination project will be created.",
            )
            dst_project = None
        else:
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

    if g.DATASET_ID:
        datasets = [api.dataset.get_info_by_id(g.DATASET_ID)]
    elif project_type == str(sly.ProjectType.IMAGES):
        if g.DATASET_ID:
            datasets = api.dataset.get_nested(g.PROJECT_ID, g.DATASET_ID)
            sly.logger.info(
                "The project is of type IMAGES and the dataset_id is specified."
                f"Retrieved {len(datasets)} nested datasets.",
            )
        else:
            datasets = api.dataset.get_list(project.id, recursive=True)
            sly.logger.info(
                "The project is of type IMAGES and the dataset_id is not specified."
                f"Retrieved {len(datasets)} datasets.",
            )
    else:
        datasets = api.dataset.get_list(project.id)

    if project_type == str(sly.ProjectType.IMAGES):
        image.clone(
            api=api,
            project_id=dst_project.id,
            datasets=datasets,
            project_meta=project_meta,
        )
    elif project_type == str(sly.ProjectType.VIDEOS):
        video.clone(
            api=api,
            project_id=dst_project.id,
            datasets=datasets,
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
            datasets=datasets,
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
