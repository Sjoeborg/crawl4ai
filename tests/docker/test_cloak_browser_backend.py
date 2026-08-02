import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

DOCKER_DIR = Path(__file__).parents[2] / "deploy" / "docker"
sys.path.insert(0, str(DOCKER_DIR))

from api import preserve_cloak_identity, resolve_browser_config
from schemas import BrowserBackend, CrawlRequest
from crawl4ai import BrowserConfig, CrawlerRunConfig


def _server_config(cdp_url="http://cloakbrowser:9222"):
    return {
        "crawler": {
            "browser_backends": {
                "cloak": {"cdp_url": cdp_url},
            }
        }
    }


def test_crawl_request_defaults_to_chromium():
    request = CrawlRequest(urls=["https://example.com"])

    assert request.browser_backend == BrowserBackend.CHROMIUM


def test_cloak_backend_uses_only_server_cdp_endpoint():
    config = resolve_browser_config(
        {
            "type": "BrowserConfig",
            "params": {
                "cdp_url": "http://attacker.invalid:9222",
                "browser_mode": "custom",
                "extra_args": ["--remote-debugging-address=0.0.0.0"],
                "headers": {
                    "User-Agent": "client-controlled",
                    "sec-ch-ua": "client-controlled",
                    "X-Test": "preserved",
                },
                "proxy": "http://client-proxy.invalid:8080",
                "use_persistent_context": True,
                "user_data_dir": "/tmp/client-profile",
                "enable_stealth": True,
            },
        },
        BrowserBackend.CLOAK,
        _server_config(),
    )

    assert config.cdp_url == "http://cloakbrowser:9222"
    assert config.browser_mode == "custom"
    assert config.use_managed_browser is True
    assert config.skip_default_headers is True
    assert config.headers == {"X-Test": "preserved"}
    assert config.extra_args == []
    assert config.proxy is None
    assert config.proxy_config is None
    assert config.use_persistent_context is False
    assert config.user_data_dir is None
    assert config.enable_stealth is False


def test_cloak_backend_must_be_configured_server_side():
    with pytest.raises(HTTPException) as exc_info:
        resolve_browser_config({}, BrowserBackend.CLOAK, {"crawler": {}})

    assert exc_info.value.status_code == 503


def test_cloak_backend_disables_crawl4ai_identity_patches():
    config = CrawlerRunConfig(
        override_navigator=True,
        simulate_user=True,
        magic=True,
    )

    preserve_cloak_identity(config)

    assert config.override_navigator is False
    assert config.simulate_user is False
    assert config.magic is False


def test_skip_default_headers_round_trips():
    config = BrowserConfig(skip_default_headers=True, headers={"X-Test": "yes"})

    loaded = BrowserConfig.load(config.dump())

    assert loaded.skip_default_headers is True
    assert loaded.headers == {"X-Test": "yes"}
