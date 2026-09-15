from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    max_profile_pic_size: int = 5 * 1024 * 1024  # 5 MB

    reset_password_token_expire_minutes: int = 60

    mail_server: str = 'localhost'
    mail_port: int = 587
    mail_username: str = ''
    mail_password: SecretStr = SecretStr('')
    mail_from: str = 'no-reply@example.com'
    mail_use_tls: bool = True

    frontend_base_url: str = 'http://localhost:8000'

settings = Settings()