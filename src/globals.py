import os
import sys
import supervisely as sly
from supervisely.app.v1.app_service import AppService
from dotenv import load_dotenv

app_root_directory = os.path.dirname(os.getcwd())
sys.path.append(app_root_directory)
sys.path.append(os.path.join(app_root_directory, "src"))
print(f"App root directory: {app_root_directory}")
sly.logger.info(f'PYTHONPATH={os.environ.get("PYTHONPATH", "")}')

if sly.is_development():
    load_dotenv("local.env")
    load_dotenv(os.path.expanduser("~/supervisely.env"))

api: sly.Api = sly.Api.from_env()
my_app: AppService = AppService(ignore_task_id=True)

TASK_ID = os.environ.get("TASK_ID", None)

TEAM_ID = sly.env.team_id()
WORKSPACE_ID = sly.env.workspace_id()
PROJECT_ID = sly.env.project_id()
DATASET_ID = sly.env.dataset_id()

DEST_TEAM_ID = os.environ.get("modal.state.teamId", None)
DEST_WORKSPACE_ID = os.environ.get("modal.state.workspaceId", None)
DEST_PROJECT_ID = os.environ.get("modal.state.projectId", None)

PROJECT_NAME = os.environ.get("modal.state.projectName", None)
DATASET_NAME = os.environ.get("modal.state.datasetName", None)
