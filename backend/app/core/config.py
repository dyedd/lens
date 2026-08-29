from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    auth_secret_key: str = ""
    port: int = 18080
    max_connections: int = 200
    max_keepalive_connections: int = 50
    database_url: str = "sqlite+aiosqlite:///./data/data.db"

    model_config = SettingsConfigDict(
        env_prefix="LENS_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
