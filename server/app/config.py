from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "QuizBlitz API"

    model_config = SettingsConfigDict(env_file=".env")
