import supervisely as sly

import globals as g
import project_type.image as image
import project_type.video as video
import project_type.volume as volume
import project_type.pointcloud as pointcloud
import project_type.pointcloud_episodes as pointcloud_episodes


@g.my_app.callback("clone-data")
@sly.timeit
def clone_data(api: sly.Api, task_id, context, state, app_logger):
    project = api.project.get_info_by_id(g.PROJECT_ID)
    project_meta_json = api.project.get_meta(project.id)
    project_meta = sly.ProjectMeta.from_json(data=project_meta_json)
    project_type = project_meta.project_type

    if not g.DEST_PROJECT_ID:
        dst_project = api.project.create(
            workspace_id=g.DEST_WORKSPACE_ID,
            name=g.PROJECT_NAME or project.name,
            type=project.type,
            description=project.description,
            change_name_if_conflict=True,
        )
        api.project.update_meta(id=dst_project.id, meta=project_meta)
    else:
        dst_project = api.project.get_info_by_id(g.DEST_PROJECT_ID)
        api.project.merge_metas(
            src_project_id=project.id, dst_project_id=dst_project.id
        )
        
    if g.DATASET_ID:
        datasets = [api.dataset.get_info_by_id(g.DATASET_ID)]
    else:
        datasets = api.dataset.get_list(project.id)

    if project_type == str(sly.ProjectType.IMAGES):
        image.clone(api=api, project_id=dst_project.id, datasets=datasets)
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
    g.my_app.stop()


def main():
    sly.logger.info(
        "Script arguments",
        extra={
            "TEAM_ID": g.TEAM_ID,
            "WORKSPACE_ID": g.WORKSPACE_ID,
            "PROJECT_ID": g.PROJECT_ID,
        },
    )

    g.my_app.run(initial_events=[{"command": "clone-data"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main)
