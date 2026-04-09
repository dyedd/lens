from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Lens"
    app_env: str = "dev"
    host: str = "127.0.0.1"
    port: int = 18080
    auth_secret_key: str = "lens-dev-secret-key-change-me-32bytes"
    auth_algorithm: str = "HS256"
    auth_access_token_minutes: int = 60 * 12
    request_timeout_seconds: float = 180.0
    connect_timeout_seconds: float = 10.0
    max_connections: int = 200
    max_keepalive_connections: int = 50
    database_url: str = "sqlite+aiosqlite:///data/data.db"
    anthropic_version: str = "2023-06-01"

    model_config = SettingsConfigDict(
        env_prefix="LENS_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
