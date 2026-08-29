from __future__ import annotations

from .replace_config import (
    _replace_cronjobs,
    _replace_gateway_api_keys,
    _replace_settings,
)
from .replace_groups import _replace_groups
from .replace_logs import _replace_request_logs
from .replace_prices_stats import _replace_model_prices, _replace_stats
from .replace_sites import _replace_sites


class BackupReplacersMixin:
    _replace_sites = _replace_sites
    _replace_groups = _replace_groups
    _replace_model_prices = _replace_model_prices
    _replace_stats = _replace_stats
    _replace_settings = _replace_settings
    _replace_cronjobs = _replace_cronjobs
    _replace_gateway_api_keys = _replace_gateway_api_keys
    _replace_request_logs = _replace_request_logs
