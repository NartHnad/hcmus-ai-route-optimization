from pathlib import Path
import os

from src.models.graph_factory import build_graph

CURRENT_DIR = Path(__file__).resolve().parent  # project/src/data
SRC_DIR = CURRENT_DIR.parent  # project/src
PROJECT_ROOT = SRC_DIR.parent  # project
DATA_DIR = PROJECT_ROOT / "data"


def get_json_datasets() -> list[str]:
    """
    Automatic scan the .json files in data folder.
    """
    # Just get .json file
    json_files = [file.name for file in DATA_DIR.glob("*.json")]

    # Return a sorted list
    return sorted(json_files)


def load_dataset(filename):
    """
    Load a graph dataset from the data directory.

    Parameters
    ----------
    filename : str
        JSON dataset filename.

    Returns
    -------
    Graph
        Constructed Graph object.
    """
    json_path = DATA_DIR / filename

    # Check whether the dataset exists
    if not json_path.exists():
        raise FileNotFoundError(f"Dataset '{filename}' not found.")

    return build_graph(os.fspath(json_path))
