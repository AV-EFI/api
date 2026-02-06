from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def runtime_path_of(request) -> Callable[[str], Path]:
    def get_path(filename: Path):
        return request.path.parent / filename

    return get_path
