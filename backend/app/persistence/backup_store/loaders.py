from __future__ import annotations

from .load_config import _load_cronjobs, _load_gateway_api_keys
from .load_groups import _load_groups
from .load_logs import _load_request_logs
from .load_prices_stats import _load_model_prices, _load_stats
from .load_sites import _load_sites


class BackupLoadersMixin:
    _load_sites = _load_sites
    _load_groups = _load_groups
    _load_model_prices = _load_model_prices
    _load_stats = _load_stats
    _load_gateway_api_keys = _load_gateway_api_keys
    _load_cronjobs = _load_cronjobs
    _load_request_logs = _load_request_logs
