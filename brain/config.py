"""
Configuration settings loaded from environment variables.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_db_password: str = ""
    
    # Odoo
    odoo_url: str = "http://localhost:8069"
    odoo_db: str = "contax_prod"
    odoo_user: str = "admin"
    odoo_password: str = ""
    
    # Encryption key for SUNAT credentials (generate with: openssl rand -hex 32)
    encryption_key: str = ""
    
    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings loader."""
    return Settings()
