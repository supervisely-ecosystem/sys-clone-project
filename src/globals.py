import os
import sys
import supervisely as sly
from supervisely.app.v1.app_service import AppService
from distutils import util

app_root_directory = os.path.dirname(os.getcwd())
sys.path.append(app_root_directory)
sys.path.append(os.path.join(app_root_directory, "src"))
print(f"App root directory: {app_root_directory}")
sly.logger.info(f'PYTHONPATH={os.environ.get("PYTHONPATH", "")}')

# order matters
from dotenv import load_dotenv
load_dotenv(os.path.join(app_root_directory, "sys-clone-project", "secret_debug.env"))
load_dotenv(os.path.join(app_root_directory, "sys-clone-project", "debug.env"))

api: sly.Api = sly.Api.from_env()
my_app: AppService = AppService()

TASK_ID = os.environ.get("TASK_ID", None)

TEAM_ID = os.environ.get("CONTEXT_TEAMID", None)
WORKSPACE_ID = os.environ.get("CONTEXT_WORKSPACEID", None)
PROJECT_ID = os.environ.get("CONTEXT_PROJECTID", None)
DATASET_ID = os.environ.get("CONTEXT_DATASETID", None)

DEST_WORKSPACE_ID = os.environ.get("modal.state.workspaceId", None)
DEST_PROJECT_ID = os.environ.get("modal.state.projectId", None)

PROJECT_NAME = os.environ.get("modal.state.projectName", None)
DATASET_NAME = os.environ.get("modal.state.datasetName", None)

if DATASET_ID:
    DEST_DATASET_ID = os.environ.get("modal.state.datasetId", None)
