"""
Adımlar:
    1- Gerekli kütüphanelerin import edilmesi
    2. Settings sınıfının oluşturulması
    3. DATABASE_URL, saatlik ücret gibi gerekli alanları tanımla
    4. async_database_url özelliğinin eklenmesi
    5. settings instance oluşturmak
Kurulum:
    1. pydantic-settings kütüphaneisini requirements.txt dosyasına ekle:
        pydantic-settings
    2. Bağımlılıkların yüklenmesi
        pip install -r requirements.txt
    3. backend/.env'a ortam değişkenlerinin eklenmesi
"""

from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    DATABASE_URL: str
    HOURLY_RATE: float = 10.0
    ALLOWED_ORIGINS: str = "Http://localhost:8501,http://localhost:3000"

    @property
    def allowed_orgins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()