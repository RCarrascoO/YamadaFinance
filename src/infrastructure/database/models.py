from sqlalchemy import Column, Integer, String, Float, DateTime, Text, BigInteger, Boolean
from sqlalchemy.sql import func
from infrastructure.database.db_config import Base

class ReceiptModel(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True)  # ID del usuario de Telegram (BigInteger para soportar IDs largos)
    file_hash = Column(String, index=True, nullable=True) # Hash SHA256 del archivo para detectar duplicados
    date_added = Column(DateTime(timezone=True), server_default=func.now())
    merchant_name = Column(String, nullable=True)
    total_amount = Column(Float, nullable=True)
    raw_text = Column(Text, nullable=True)
    image_path = Column(String, nullable=True)
    
    # Campos adicionales
    category = Column(String, nullable=True) # Ej: Comida, Transporte, Ocio
    merchant_name = Column(String, nullable=True) # Ej: PC Factory, Cine Hoyts

class BudgetModel(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True)
    category = Column(String, index=True)
    amount_limit = Column(Float)
    month = Column(Integer) # 1-12
    year = Column(Integer) # 2025

class SubscriptionModel(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True)
    name = Column(String)
    amount = Column(Float)
    day_of_month = Column(Integer) # Día del mes para cobrar (1-31)
    category = Column(String, default="Suscripciones")
    last_processed_month = Column(String, nullable=True) # "YYYY-MM" para evitar duplicados

class ReminderModel(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True)
    message = Column(String)
    remind_at = Column(DateTime)
    is_sent = Column(Boolean, default=False)
