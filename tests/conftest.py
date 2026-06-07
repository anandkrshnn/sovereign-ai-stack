import os
import shutil
from pathlib import Path
import pytest
from sovereign_ai import Config, SovereignPipeline

@pytest.fixture(scope="function")
def sovereign_test_env(tmp_path):
    """Create isolated test environment."""
    env = {
        "base_dir": tmp_path,
        "tenants": {},
    }

    # Create tenants
    for tenant_id in ["tenant_alpha", "tenant_beta"]:
        tenant_dir = tmp_path / tenant_id
        tenant_dir.mkdir()

        config = Config(
            tenant_id=tenant_id,
        )

        env["tenants"][tenant_id] = {
            "config": config,
            "dir": tenant_dir,
        }

    return env
