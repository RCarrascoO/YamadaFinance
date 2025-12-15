import pandas as pd
import io
from datetime import datetime

def generate_excel_report(receipts: list) -> io.BytesIO:
    """
    Genera un archivo Excel con el listado de boletas.
    """
    if not receipts:
        return None
        
    data = []
    for r in receipts:
        data.append({
            "ID": r.id,
            "Fecha": r.date_added.strftime("%Y-%m-%d %H:%M"),
            "Comercio": r.merchant_name,
            "Categoría": r.category,
            "Monto Total": r.total_amount,
            "Texto OCR": r.raw_text[:100] + "..." if r.raw_text else ""
        })
        
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Gastos')
        
    output.seek(0)
    return output
