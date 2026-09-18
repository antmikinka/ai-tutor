import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(scope="session")
def settings(tmp_path_factory):
    from config.settings import create_settings

    root = tmp_path_factory.mktemp("backend")
    s = create_settings(
        model_dir=root / "models",
        model_cache_dir=root / "models" / "cache",
        data_dir=root / "data",
        log_dir=root / "logs",
        upload_dir=root / "uploads",
        temp_dir=root / "temp",
        knowledge_dir=root / "data" / "knowledge",
        knowledge_embedding="hashing",  # never download a model in tests
        ai_use_gpu=False,
        preload_models=False,
        log_level="WARNING",
    )
    s.ensure_directories()
    return s


@pytest.fixture(scope="session")
def client(settings):
    from fastapi.testclient import TestClient

    from main import create_app

    app = create_app(settings)
    with TestClient(app) as c:
        yield c
