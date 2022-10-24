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
load_dotenv(os.path.join(app_root_directory, "secret_debug.env"))
load_dotenv(os.path.join(app_root_directory, "debug.env"))

api: sly.Api = sly.Api.from_env()
my_app: AppService = AppService()


TEAM_ID = os.environ.get("CONTEXT_TEAMID", None)
WORKSPACE_ID = os.environ.get("CONTEXT_WORKSPACEID", None)
PROJECT_ID = os.environ.get("CONTEXT_PROJECTID", None)
DATASET_ID = os.environ.get("CONTEXT_DATASETID", None)

DEST_TEAM_ID = os.environ.get("modal.state.teamId", None)
DEST_WORKSPACE_ID = os.environ.get("modal.state.workspaceId", None)
DEST_PROJECT_ID = os.environ.get("modal.state.projectId", None)

if DATASET_ID:
    DEST_DATASET_ID = os.environ.get("modal.state.datasetId", None)