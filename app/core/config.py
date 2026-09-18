from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "CRM AI Campaign Automation API"
    environment: str = "development"
    cors_origins: list[str] = []
    database_url: SecretStr | None = None
    worker_lease_seconds: int = Field(default=30, ge=3)
    worker_heartbeat_seconds: float = Field(default=10, gt=0)
    worker_poll_seconds: float = Field(default=1, gt=0)

    @model_validator(mode="after")
    def validate_worker_intervals(self):
        if self.worker_heartbeat_seconds >= self.worker_lease_seconds / 2:
            raise ValueError("Heartbeat interval must be less than half the lease")
        return self
