import os
import sys
from dotenv import load_dotenv

# Añadir el directorio src al path para que las importaciones funcionen correctamente
# Esto permite importar 'infrastructure', 'domain', etc. directamente
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from infrastructure.telegram.bot import run_bot
from infrastructure.database.db_config import engine, Base

def main():
    load_dotenv() # Cargar variables de entorno desde .env
    
    # Crear tablas en la base de datos si no existen
    print("Inicializando base de datos...")
    Base.metadata.create_all(bind=engine)
    
    print("Iniciando Lilo Bot...")
    try:
        run_bot()
    except Exception as e:
        print(f"Error al iniciar el bot: {e}")

if __name__ == "__main__":
    main()
