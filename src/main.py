import os
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
    
    
    datasets = api.dataset.get_list(project.id)
    dataset_ids = [dataset.id for dataset in datasets]
    
    if project_type == str(sly.ProjectType.IMAGES):
        image.clone()
    elif project_type == str(sly.ProjectType.VIDEOS):
        video.clone()
    elif project_type == str(sly.ProjectType.VOLUMES):
        volume.clone()
    elif project_type == str(sly.ProjectType.POINT_CLOUDS):
        pointcloud.clone()
    elif project_type == str(sly.ProjectType.POINT_CLOUD_EPISODES):
        pointcloud_episodes.clone()
    else:
        raise NotImplementedError("Unknown project type: {}".format(project_type))


def main():
    sly.logger.info(
        "Script arguments",
        extra={
            "TEAM_ID": g.TEAM_ID,
            "WORKSPACE_ID": g.WORKSPACE_ID,
            "PROJECT_ID": g.PROJECT_ID
        }
    )

    data = {}
    state = {}
    g.my_app.run(initial_events=[{"command": "clone-data"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main)
