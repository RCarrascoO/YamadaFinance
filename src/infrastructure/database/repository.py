from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from thefuzz import fuzz
from .models import ReceiptModel, BudgetModel, SubscriptionModel, ReminderModel
from domain.receipt import Receipt
from domain.parser import ReceiptParser

class ReceiptRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_receipt(self, user_id: int, raw_text: str, image_path: str, file_hash: str = None, total_amount: float = None) -> ReceiptModel:
        # Si Gemini ya nos dio el total, lo usamos. Si no, intentamos parsear.
        final_total = total_amount if total_amount is not None else ReceiptParser.extract_total(raw_text)
        
        db_receipt = ReceiptModel(
            user_id=user_id,
            raw_text=raw_text,
            image_path=image_path,
            file_hash=file_hash,
            total_amount=final_total
        )
        self.db.add(db_receipt)
        self.db.commit()
        self.db.refresh(db_receipt)
        return db_receipt

    def update_category(self, receipt_id: int, category: str):
        """Actualiza la categoría de una boleta."""
        receipt = self.db.query(ReceiptModel).filter(ReceiptModel.id == receipt_id).first()
        if receipt:
            receipt.category = category
            self.db.commit()
            self.db.refresh(receipt)
        return receipt

    def add_expense(self, user_id: int, amount: float, description: str, category: str = "Suscripciones") -> ReceiptModel:
        """Agrega un gasto manual (ej: suscripción)."""
        db_receipt = ReceiptModel(
            user_id=user_id,
            raw_text=description,
            image_path="MANUAL",
            total_amount=amount,
            category=category,
            date_added=datetime.now()
        )
        self.db.add(db_receipt)
        self.db.commit()
        self.db.refresh(db_receipt)
        return db_receipt

    def delete_receipt(self, receipt_id: int):
        """Elimina una boleta por su ID."""
        self.db.query(ReceiptModel).filter(ReceiptModel.id == receipt_id).delete()
        self.db.commit()

    def is_duplicate(self, user_id: int, file_hash: str) -> bool:
        if not file_hash:
            return False
        return self.db.query(ReceiptModel).filter(
            ReceiptModel.user_id == user_id,
            ReceiptModel.file_hash == file_hash
        ).first() is not None

    def get_monthly_total(self, user_id: int, month: int = None, year: int = None) -> float:
        """Calcula el total gastado en un mes específico (o el actual si no se especifica)."""
        now = datetime.now()
        target_month = month if month else now.month
        target_year = year if year else now.year
        
        start_date = datetime(target_year, target_month, 1)
        # Calcular fin de mes
        if target_month == 12:
            end_date = datetime(target_year + 1, 1, 1)
        else:
            end_date = datetime(target_year, target_month + 1, 1)
        
        result = self.db.query(func.sum(ReceiptModel.total_amount)).filter(
            ReceiptModel.user_id == user_id,
            ReceiptModel.date_added >= start_date,
            ReceiptModel.date_added < end_date
        ).scalar()
        
        return result if result else 0.0

    def get_monthly_expenses_by_category(self, user_id: int, month: int = None, year: int = None):
        """Obtiene el total de gastos agrupado por categoría para un mes específico."""
        now = datetime.now()
        target_month = month if month else now.month
        target_year = year if year else now.year
        
        start_date = datetime(target_year, target_month, 1)
        if target_month == 12:
            end_date = datetime(target_year + 1, 1, 1)
        else:
            end_date = datetime(target_year, target_month + 1, 1)
        
        results = self.db.query(
            ReceiptModel.category, 
            func.sum(ReceiptModel.total_amount)
        ).filter(
            ReceiptModel.user_id == user_id,
            ReceiptModel.date_added >= start_date,
            ReceiptModel.date_added < end_date
        ).group_by(ReceiptModel.category).all()
        
        return results

    def get_monthly_expenses_by_merchant(self, user_id: int, month: int = None, year: int = None):
        """Obtiene el total de gastos agrupado por comercio (marca) para un mes específico."""
        now = datetime.now()
        target_month = month if month else now.month
        target_year = year if year else now.year
        
        start_date = datetime(target_year, target_month, 1)
        if target_month == 12:
            end_date = datetime(target_year + 1, 1, 1)
        else:
            end_date = datetime(target_year, target_month + 1, 1)
        
        results = self.db.query(
            ReceiptModel.merchant_name, 
            func.sum(ReceiptModel.total_amount)
        ).filter(
            ReceiptModel.user_id == user_id,
            ReceiptModel.date_added >= start_date,
            ReceiptModel.date_added < end_date
        ).group_by(ReceiptModel.merchant_name).all()
        
        return results

    def update_merchant(self, receipt_id: int, merchant_name: str):
        """Actualiza el nombre del comercio de una boleta."""
        receipt = self.db.query(ReceiptModel).filter(ReceiptModel.id == receipt_id).first()
        if receipt:
            receipt.merchant_name = merchant_name
            self.db.commit()
            self.db.refresh(receipt)
        return receipt

    def update_total_amount(self, receipt_id: int, new_amount: float):
        """Actualiza el monto total de una boleta."""
        receipt = self.db.query(ReceiptModel).filter(ReceiptModel.id == receipt_id).first()
        if receipt:
            receipt.total_amount = new_amount
            self.db.commit()
            self.db.refresh(receipt)
        return receipt

    def get_yearly_total(self, user_id: int, year: int = None) -> float:
        """Calcula el total gastado en un año específico (o el actual)."""
        now = datetime.now()
        target_year = year if year else now.year
        
        start_date = datetime(target_year, 1, 1)
        end_date = datetime(target_year + 1, 1, 1)
        
        result = self.db.query(func.sum(ReceiptModel.total_amount)).filter(
            ReceiptModel.user_id == user_id,
            ReceiptModel.date_added >= start_date,
            ReceiptModel.date_added < end_date
        ).scalar()
        
        return result if result else 0.0

    def get_yearly_expenses_breakdown(self, user_id: int, year: int = None):
        """Obtiene el desglose mensual de gastos para un año."""
        now = datetime.now()
        target_year = year if year else now.year
        
        start_date = datetime(target_year, 1, 1)
        end_date = datetime(target_year + 1, 1, 1)
        
        results = self.db.query(
            func.extract('month', ReceiptModel.date_added).label('month'),
            func.sum(ReceiptModel.total_amount)
        ).filter(
            ReceiptModel.user_id == user_id,
            ReceiptModel.date_added >= start_date,
            ReceiptModel.date_added < end_date
        ).group_by('month').order_by('month').all()
        
        return results

    def get_receipt_by_id(self, receipt_id: int) -> ReceiptModel:
        return self.db.query(ReceiptModel).filter(ReceiptModel.id == receipt_id).first()

    def update_category(self, receipt_id: int, category: str):
        """Actualiza la categoría de una boleta."""
        receipt = self.db.query(ReceiptModel).filter(ReceiptModel.id == receipt_id).first()
        if receipt:
            receipt.category = category
            self.db.commit()
            self.db.refresh(receipt)
        return receipt

    def find_known_merchant(self, text: str) -> str:
        """
        Busca si alguna marca conocida (ya guardada en la BD) aparece en el texto.
        Usa Fuzzy Matching para tolerar errores de OCR o pequeñas variaciones.
        Retorna el nombre de la marca o None.
        """
        # Obtener todas las marcas únicas que no sean nulas
        known_merchants = self.db.query(ReceiptModel.merchant_name).distinct().filter(ReceiptModel.merchant_name != None).all()
        
        # Convertir a lista de strings y filtrar vacíos
        merchants = [m[0] for m in known_merchants if m[0]]
        
        text_lower = text.lower()
        best_match = None
        highest_score = 0
        
        for merchant in merchants:
            # 1. Búsqueda exacta (rápida)
            if merchant.lower() in text_lower:
                return merchant
            
            # 2. Búsqueda difusa (Fuzzy)
            # Usamos partial_ratio para buscar el nombre de la marca DENTRO del texto largo
            score = fuzz.partial_ratio(merchant.lower(), text_lower)
            
            # Umbral de confianza: 85%
            if score > 85 and score > highest_score:
                highest_score = score
                best_match = merchant
                
        return best_match

    def get_most_common_category_for_merchant(self, merchant_name: str) -> str:
        """
        Predice la categoría basada en el historial de ese comercio.
        Retorna la categoría más frecuente o None.
        """
        if not merchant_name:
            return None
            
        result = self.db.query(
            ReceiptModel.category, 
            func.count(ReceiptModel.category).label('count')
        ).filter(
            ReceiptModel.merchant_name == merchant_name,
            ReceiptModel.category != None
        ).group_by(ReceiptModel.category).order_by(func.count(ReceiptModel.category).desc()).first()
        
        return result[0] if result else None

    def get_last_receipts(self, user_id: int, limit: int = 5):
        """Obtiene las últimas N boletas."""
        return self.db.query(ReceiptModel).filter(
            ReceiptModel.user_id == user_id
        ).order_by(ReceiptModel.date_added.desc()).limit(limit).all()

    def get_all_receipts(self):
        return self.db.query(ReceiptModel).all()

    def get_top_category_of_month(self, user_id: int, month: int = None, year: int = None):
        """Obtiene la categoría con mayor gasto del mes."""
        now = datetime.now()
        target_month = month if month else now.month
        target_year = year if year else now.year
        
        start_date = datetime(target_year, target_month, 1)
        if target_month == 12:
            end_date = datetime(target_year + 1, 1, 1)
        else:
            end_date = datetime(target_year, target_month + 1, 1)
            
        result = self.db.query(
            ReceiptModel.category,
            func.sum(ReceiptModel.total_amount).label('total')
        ).filter(
            ReceiptModel.user_id == user_id,
            ReceiptModel.date_added >= start_date,
            ReceiptModel.date_added < end_date,
            ReceiptModel.category != None
        ).group_by(ReceiptModel.category).order_by(func.sum(ReceiptModel.total_amount).desc()).first()
        
        return result

    def get_most_frequent_merchant(self, user_id: int):
        """Obtiene el comercio más visitado históricamente."""
        result = self.db.query(
            ReceiptModel.merchant_name,
            func.count(ReceiptModel.id).label('count')
        ).filter(
            ReceiptModel.user_id == user_id,
            ReceiptModel.merchant_name != None
        ).group_by(ReceiptModel.merchant_name).order_by(func.count(ReceiptModel.id).desc()).first()
        
        return result

    def get_total_receipts_count(self, user_id: int) -> int:
        """Cuenta el total de boletas procesadas."""
        return self.db.query(func.count(ReceiptModel.id)).filter(ReceiptModel.user_id == user_id).scalar()

    # --- Métodos de Presupuestos ---
    def set_budget(self, user_id: int, category: str, amount: float, month: int, year: int):
        """Crea o actualiza un presupuesto."""
        budget = self.db.query(BudgetModel).filter(
            BudgetModel.user_id == user_id,
            BudgetModel.category == category,
            BudgetModel.month == month,
            BudgetModel.year == year
        ).first()
        
        if budget:
            budget.amount_limit = amount
        else:
            budget = BudgetModel(user_id=user_id, category=category, amount_limit=amount, month=month, year=year)
            self.db.add(budget)
        
        self.db.commit()
        self.db.refresh(budget)
        return budget

    def get_budget_status(self, user_id: int, category: str, month: int, year: int):
        """Retorna (gastado, limite, porcentaje) para una categoría."""
        # Obtener límite
        budget = self.db.query(BudgetModel).filter(
            BudgetModel.user_id == user_id,
            BudgetModel.category == category,
            BudgetModel.month == month,
            BudgetModel.year == year
        ).first()
        
        if not budget:
            return None
            
        # Calcular gastado
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
            
        spent = self.db.query(func.sum(ReceiptModel.total_amount)).filter(
            ReceiptModel.user_id == user_id,
            ReceiptModel.category == category,
            ReceiptModel.date_added >= start_date,
            ReceiptModel.date_added < end_date
        ).scalar() or 0.0
        
        percentage = (spent / budget.amount_limit) * 100 if budget.amount_limit > 0 else 100
        return spent, budget.amount_limit, percentage

    def get_all_budgets(self, user_id: int, month: int, year: int):
        """Obtiene todos los presupuestos del mes."""
        return self.db.query(BudgetModel).filter(
            BudgetModel.user_id == user_id,
            BudgetModel.month == month,
            BudgetModel.year == year
        ).all()

    def get_budget_by_id(self, budget_id: int):
        return self.db.query(BudgetModel).filter(BudgetModel.id == budget_id).first()

    def delete_budget(self, budget_id: int):
        self.db.query(BudgetModel).filter(BudgetModel.id == budget_id).delete()
        self.db.commit()

    # --- Métodos de Suscripciones ---
    def add_subscription(self, user_id: int, name: str, amount: float, day: int):
        sub = SubscriptionModel(user_id=user_id, name=name, amount=amount, day_of_month=day)
        self.db.add(sub)
        self.db.commit()
        return sub

    def get_subscriptions(self, user_id: int):
        return self.db.query(SubscriptionModel).filter(SubscriptionModel.user_id == user_id).all()

    def delete_subscription(self, sub_id: int):
        self.db.query(SubscriptionModel).filter(SubscriptionModel.id == sub_id).delete()
        self.db.commit()

    def update_subscription(self, sub_id: int, amount: float = None, day: int = None):
        sub = self.db.query(SubscriptionModel).filter(SubscriptionModel.id == sub_id).first()
        if sub:
            if amount is not None:
                sub.amount = amount
            if day is not None:
                sub.day_of_month = day
            self.db.commit()
            return sub
        return None

    def get_due_subscriptions(self, day: int):
        """Obtiene suscripciones que deben cobrarse hoy y no han sido procesadas este mes."""
        current_month_str = datetime.now().strftime("%Y-%m")
        return self.db.query(SubscriptionModel).filter(
            SubscriptionModel.day_of_month == day,
            (SubscriptionModel.last_processed_month != current_month_str) | (SubscriptionModel.last_processed_month == None)
        ).all()

    def mark_subscription_processed(self, sub_id: int):
        sub = self.db.query(SubscriptionModel).filter(SubscriptionModel.id == sub_id).first()
        if sub:
            sub.last_processed_month = datetime.now().strftime("%Y-%m")
            self.db.commit()

    # --- Métodos de Recordatorios ---
    def add_reminder(self, user_id: int, message: str, remind_at: datetime):
        reminder = ReminderModel(user_id=user_id, message=message, remind_at=remind_at)
        self.db.add(reminder)
        self.db.commit()
        return reminder

    def get_pending_reminders(self):
        """Obtiene recordatorios que ya pasaron su fecha y no han sido enviados."""
        now = datetime.now()
        return self.db.query(ReminderModel).filter(
            ReminderModel.remind_at <= now,
            ReminderModel.is_sent == False
        ).all()

    def mark_reminder_sent(self, reminder_id: int):
        reminder = self.db.query(ReminderModel).filter(ReminderModel.id == reminder_id).first()
        if reminder:
            reminder.is_sent = True
            self.db.commit()

    def get_active_reminders_for_user(self, user_id: int):
        """Obtiene recordatorios futuros para un usuario."""
        now = datetime.now()
        return self.db.query(ReminderModel).filter(
            ReminderModel.user_id == user_id,
            ReminderModel.remind_at > now,
            ReminderModel.is_sent == False
        ).order_by(ReminderModel.remind_at).all()

    def delete_reminder(self, reminder_id: int):
        self.db.query(ReminderModel).filter(ReminderModel.id == reminder_id).delete()
        self.db.commit()

    def get_reminder_by_id(self, reminder_id: int):
        return self.db.query(ReminderModel).filter(ReminderModel.id == reminder_id).first()

    def update_reminder(self, reminder_id: int, message: str = None, remind_at: datetime = None):
        reminder = self.db.query(ReminderModel).filter(ReminderModel.id == reminder_id).first()
        if reminder:
            if message:
                reminder.message = message
            if remind_at:
                reminder.remind_at = remind_at
            self.db.commit()
            return reminder
        return None

    def get_all_active_users(self):
        """Obtiene lista de IDs de usuarios únicos."""
        return [r.user_id for r in self.db.query(ReceiptModel.user_id).distinct()]

