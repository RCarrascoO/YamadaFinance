import os
import sys
from dotenv import load_dotenv

# Añadir el directorio src al path para que las importaciones funcionen correctamente
# Esto permite importar 'infrastructure', 'domain', etc. directamente
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from infrastructure.telegram.bot import run_bot
from infrastructure.database.db_config import engine, Base
from sqlalchemy import text

def migrate_db():
    """Aplica migraciones de columnas nuevas sobre tablas existentes (idempotente)."""
    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS interval VARCHAR DEFAULT 'mensual';"
        ))
        conn.execute(text(
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS month_of_year INTEGER;"
        ))
        conn.commit()

def main():
    load_dotenv() # Cargar variables de entorno desde .env
    
    # Crear tablas en la base de datos si no existen
    print("Inicializando base de datos...")
    Base.metadata.create_all(bind=engine)

    # Migraciones de columnas (seguro ejecutar siempre)
    print("Aplicando migraciones...")
    migrate_db()
    
    print("Iniciando YamadaFinance Bot...")
    try:
        run_bot()
    except Exception as e:
        print(f"Error al iniciar el bot: {e}")

if __name__ == "__main__":
    main()
