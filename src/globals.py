import os
import sys
import supervisely as sly
from dotenv import load_dotenv

app_root_directory = os.path.dirname(os.getcwd())
sys.path.append(app_root_directory)
sys.path.append(os.path.join(app_root_directory, "src"))
print(f"App root directory: {app_root_directory}")
sly.logger.info(f'PYTHONPATH={os.environ.get("PYTHONPATH", "")}')

if sly.is_development():
    load_dotenv("local.env")
    load_dotenv(os.path.expanduser("~/supervisely.env"))

api = sly.Api.from_env()

TASK_ID = os.environ.get("TASK_ID", None)

TEAM_ID = sly.env.team_id(raise_not_found=False)
WORKSPACE_ID = sly.env.workspace_id(raise_not_found=False)
PROJECT_ID = sly.env.project_id(raise_not_found=False)
DATASET_ID = sly.env.dataset_id(raise_not_found=False)

DEST_TEAM_ID = os.environ.get("modal.state.teamId", None)
DEST_WORKSPACE_ID = os.environ.get("modal.state.workspaceId", None)
DEST_PROJECT_ID = os.environ.get("modal.state.projectId", None)

PROJECT_NAME = os.environ.get("modal.state.projectName", None)
if PROJECT_NAME is not None:
    PROJECT_NAME = PROJECT_NAME.replace("\\", "").replace("|", "").replace("/", "")
DATASET_NAME = os.environ.get("modal.state.datasetName", None)
if DATASET_NAME is not None:
    DATASET_NAME = DATASET_NAME.replace("\\", "").replace("|", "").replace("/", "")
