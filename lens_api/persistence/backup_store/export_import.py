from __future__ import annotations

from .shared import (
    BACKUP_DUMP_VERSION,
    ConfigBackupDump,
    ConfigImportResult,
    EXPORTABLE_SETTING_KEYS,
    SettingEntity,
    SettingItem,
    UTC,
    datetime,
    json,
    select,
)


class BackupExportImportMixin:
    @staticmethod
    def parse_dump(payload: bytes) -> "ConfigBackupDump":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid backup file") from exc
        try:
            return ConfigBackupDump.model_validate(data)
        except ValueError as exc:
            raise ValueError("Invalid backup file") from exc

    async def export_dump(
        self,
        *,
        lens_version: str,
        include_request_logs: bool,
        include_gateway_api_keys: bool,
    ) -> ConfigBackupDump:
        async with self._session_factory() as session:
            settings_rows = (
                (
                    await session.execute(
                        select(SettingEntity)
                        .where(SettingEntity.key.in_(EXPORTABLE_SETTING_KEYS))
                        .order_by(SettingEntity.key.asc())
                    )
                )
                .scalars()
                .all()
            )
            sites = await self._load_sites(session)
            groups = await self._load_groups(session)
            model_prices = await self._load_model_prices(session)
            cronjobs = await self._load_cronjobs(session)
            stats = await self._load_stats(session)
            gateway_api_keys = (
                await self._load_gateway_api_keys(session)
                if include_gateway_api_keys
                else []
            )
            request_logs = (
                await self._load_request_logs(session) if include_request_logs else []
            )

        return ConfigBackupDump(
            version=BACKUP_DUMP_VERSION,
            exported_at=datetime.now(UTC).isoformat(),
            lens_version=lens_version,
            include_request_logs=include_request_logs,
            include_gateway_api_keys=include_gateway_api_keys,
            settings=[
                SettingItem(key=item.key, value=item.value) for item in settings_rows
            ],
            sites=sites,
            groups=groups,
            model_prices=model_prices,
            cronjobs=cronjobs,
            stats=stats,
            gateway_api_keys=gateway_api_keys,
            request_logs=request_logs,
        )

    async def import_dump(self, dump: ConfigBackupDump) -> ConfigImportResult:
        if dump.version != BACKUP_DUMP_VERSION:
            raise ValueError(f"Unsupported backup version: {dump.version}")

        async with self._session_factory() as session:
            rows_affected: dict[str, int] = {}

            protocol_config_ids, protocols_by_config_id, available_model_keys = (
                await self._replace_sites(session, dump.sites)
            )
            rows_affected["sites"] = len(dump.sites)
            rows_affected["site_base_urls"] = sum(
                len(site.base_urls) for site in dump.sites
            )
            rows_affected["site_credentials"] = sum(
                len(site.credentials) for site in dump.sites
            )
            rows_affected["site_protocol_configs"] = sum(
                len(site.protocols) for site in dump.sites
            )
            rows_affected["site_models"] = sum(
                len(protocol.models)
                for site in dump.sites
                for protocol in site.protocols
            )

            await self._replace_groups(
                session,
                dump.groups,
                available_protocol_config_ids=protocol_config_ids,
                protocols_by_config_id=protocols_by_config_id,
                available_model_keys=available_model_keys,
            )
            rows_affected["model_groups"] = len(dump.groups)
            rows_affected["model_group_items"] = sum(
                len(group.items) for group in dump.groups
            )

            await self._replace_model_prices(session, dump.model_prices)
            rows_affected["model_prices"] = len(dump.model_prices)

            await self._replace_settings(session, dump.settings)
            rows_affected["settings"] = len(dump.settings)

            await self._replace_cronjobs(session, dump.cronjobs)
            rows_affected["cronjobs"] = len(dump.cronjobs)

            await self._replace_stats(session, dump.stats)
            rows_affected["imported_stats_total"] = (
                1 if dump.stats.imported_total is not None else 0
            )
            rows_affected["imported_stats_daily"] = len(dump.stats.imported_daily)
            rows_affected["request_log_daily_stats"] = len(dump.stats.request_daily)
            rows_affected["overview_model_daily_stats"] = len(dump.stats.model_daily)

            if dump.include_gateway_api_keys:
                await self._replace_gateway_api_keys(session, dump.gateway_api_keys)
                rows_affected["gateway_api_keys"] = len(dump.gateway_api_keys)

            if dump.include_request_logs:
                await self._replace_request_logs(session, dump.request_logs)
                rows_affected["request_logs"] = len(dump.request_logs)

            await session.commit()

        return ConfigImportResult(rows_affected=rows_affected)
