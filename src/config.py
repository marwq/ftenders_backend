from pydantic import MongoDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_url: MongoDsn
    mongo_db: str
    anthropic_api_key: str


settings = Settings() # type: ignore
