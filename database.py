import sqlite3
import logging

DB_PATH = "currency.db"

def get_connection():
    # timeout=20 дозволяє чекати, якщо база зайнята іншим запитом
    return sqlite3.connect(DB_PATH, timeout=20)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Створюємо таблицю з двома колонками для курсу: buy та sell
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rates (
                currency TEXT PRIMARY KEY,
                buy REAL,
                sell REAL
            )
        """)
        
        # Таблиця користувачів
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                requests INTEGER DEFAULT 0
            )
        """)
        
        # Таблиця логів
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                currency TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Перевірка на випадок, якщо база вже існувала зі старою структурою
        # Додаємо колонки, якщо їх немає (міграція)
        cursor.execute("PRAGMA table_info(rates)")
        columns = [column[1] for column in cursor.fetchall()]
        if "rate" in columns:
            # Якщо стара колонка 'rate' існує, видаляємо стару таблицю або перейменовуємо
            # Найпростіший шлях для локальної розробки — перестворити
            cursor.execute("DROP TABLE rates")
            cursor.execute("""
                CREATE TABLE rates (
                    currency TEXT PRIMARY KEY,
                    buy REAL,
                    sell REAL
                )
            """)
            
        conn.commit()

def set_rate(currency: str, buy: float, sell: float):
    """Оновлює або додає курс купівлі та продажу"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO rates (currency, buy, sell) 
            VALUES (?, ?, ?)
        """, (currency.upper(), buy, sell))
        conn.commit()

def get_rate(currency: str):
    """Повертає кортеж (buy, sell) або None"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT buy, sell FROM rates WHERE currency = ?", (currency.upper(),))
        result = cursor.fetchone()
        return result if result else None

def log_action(user_id, action, currency=None):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO logs (user_id, action, currency) VALUES (?, ?, ?)", (user_id, action, currency))
            cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            cursor.execute("UPDATE users SET requests = requests + 1 WHERE user_id = ?", (user_id,))
            conn.commit()
    except Exception as e:
        logging.error(f"Database logging error: {e}")

def get_global_stats():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM logs")
        actions = cursor.fetchone()[0]
        return users, actions