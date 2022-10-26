import supervisely as sly

import globals as g


@g.my_app.callback("clone-data")
@sly.timeit
def clone_data(api: sly.Api, task_id, context, state, app_logger):
    project = api.project.get_info_by_id(g.PROJECT_ID)
    if not g.DATASET_ID:
        project_name = g.PROJECT_NAME or project.name
        api.project.clone_advanced(id=g.PROJECT_ID, dst_workspace_id=g.DEST_WORKSPACE_ID, dst_name=project_name)
    else:
        if not g.DATASET_NAME:
            dataset = api.dataset.get_info_by_id(id=g.DATASET_ID)
            ds_name = api.dataset.get_free_name(parent_id=g.DEST_PROJECT_ID, name=dataset.name)
        else:
            ds_name = g.DATASET_NAME
        api.dataset.copy(dst_project_id=g.DEST_PROJECT_ID, id=g.DATASET_ID, new_name=ds_name)
    g.my_app.stop()


def main():
    sly.logger.info(
        "Script arguments",
        extra={
            "TEAM_ID": g.TEAM_ID,
            "WORKSPACE_ID": g.WORKSPACE_ID,
            "PROJECT_ID": g.PROJECT_ID
        }
    )

    g.my_app.run(initial_events=[{"command": "clone-data"}])


if __name__ == "__main__":
    sly.main_wrapper("main", main)
