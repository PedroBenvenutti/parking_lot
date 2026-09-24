from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração da aplicação. Valores da seção 11 da SPEC ficam aqui, nunca fixos no código."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/parking_lot"
    test_database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/parking_lot_test"

    secret_key: str = "dev-secret-change-me"
    token_ttl_minutes: int = 60 * 12

    # Tempo parado vence após N dias úteis sem movimentação.
    stale_business_days: int = 3
    # Eventos que NÃO contam como movimentação para o relógio de tempo parado.
    stale_ignored_events: list[str] = ["hazard_on", "hazard_off"]
    # Fuso usado para decidir o que é dia útil (seg-sex).
    timezone: str = "America/Sao_Paulo"

    plate_prefix: str = "ADV"
    # Quantas vagas por fileira ao gerar as vagas de um andar.
    spots_per_row: int = 6
    # Intervalo da checagem periódica de vencimentos (0 desliga).
    clock_tick_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
