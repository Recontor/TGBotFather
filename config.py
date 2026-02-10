import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
# Якщо в .env немає пароля, буде використано стандартний (але краще додати в .env)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")