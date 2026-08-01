from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Bot
    bale_bot_token: str
    super_admin_chat_id: int

    # Database
    database_url: str

    # Channel
    channel_id: int
    channel_username: str

    # Payment (Manual)
    payment_card_number: str
    payment_card_holder: str

    # 🔮 FUTURE: Bale Payment Gateway
    # bale_payment_provider_token: str | None = None

    # AI Integration
    gemini_api_key: str | None = None

settings = Settings()
