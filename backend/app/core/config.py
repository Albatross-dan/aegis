from pathlib import Path

from pydantic_settings import BaseSettings


REPO_ROOT = Path(__file__).resolve().parents[3]
INFRA_ENV_FILE = REPO_ROOT / "infrastructure" / ".env"

class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = str(INFRA_ENV_FILE)

settings = Settings()
