from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60
    AUTH_COOKIE_NAME: str = "fundinv_session"
    COOKIE_SECURE: str = "false"
    COOKIE_SAMESITE: str = "lax"
    ENVIRONMENT: str = "development"

    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    AUTO_MIGRATE: str = "false"
    ENABLE_SCHEDULER: str = "false"
    ENABLE_AUTOMATED_TRADING: str = "false"
    SCHEDULER_TIMEZONE: str = "Asia/Singapore"

    SMTP_EMAIL: str = ""
    SMTP_PASSWORD: str = ""

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_CONNECT_CURRENCY: str = "usd"
    STRIPE_CONNECT_REFRESH_URL: str = "http://localhost:3000/dashboard/investor/fund-flows"
    STRIPE_CONNECT_RETURN_URL: str = "http://localhost:3000/dashboard/investor/fund-flows?connect=complete"
    STRIPE_SUCCESS_URL: str = "http://localhost:3000/dashboard/investor/funds?payment=success"
    STRIPE_CANCEL_URL: str = "http://localhost:3000/dashboard/investor/funds?payment=cancelled"

    ALPACA_API_KEY: str = ""
    ALPACA_SECRET_KEY: str = ""
    ALPACA_BASE_URL: str = "https://paper-api.alpaca.markets"
    ALPACA_DATA_URL: str = "https://data.alpaca.markets"

    class Config:
        env_file = str(Path(__file__).resolve().parent.parent / ".env")


settings = Settings()
