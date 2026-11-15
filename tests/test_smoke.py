"""B1: the package imports and the shared limits are sane."""

import harness.config as config


def test_config_imports():
    assert config.MAX_CHARS == 1500
    assert config.PROFILE_DIR.name == "profile"
    assert config.PROFILE_DIR.parent.name == ".harness"
