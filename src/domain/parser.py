import re
from typing import Optional

class ReceiptParser:
    @staticmethod
    def extract_total(text: str) -> Optional[float]:
        """
        Intenta extraer el monto total de la boleta.
        Maneja casos con múltiples totales (ej: Total -> Descuento -> Total a Pagar).
        Prioriza 'Total a Pagar' y el último 'Total' encontrado.
        """
        if not text:
            return None

        lines = text.split('\n')
        final_candidates = []
        general_candidates = []
        
        # Regex para capturar números (10.000, 10000, $10.000)
        # Asumimos punto como separador de miles (CLP)
        amount_pattern = r'[\$]?\s*(\d[\d\.]*)' 
        
        for line in lines:
            line_lower = line.lower()
            
            # Ignorar líneas de subtotal explícito
            if "subtotal" in line_lower or "sub-total" in line_lower or "sub total" in line_lower or "neto" in line_lower:
                continue
                
            # Buscar números en la línea
            matches = re.findall(amount_pattern, line)
            if not matches:
                continue
                
            # Extraer valores numéricos válidos de la línea
            line_values = []
            for m in matches:
                try:
                    # Limpieza: quitar puntos (miles) y símbolos
                    clean_val = m.replace('.', '').replace('$', '').strip()
                    if not clean_val: continue
                    val = float(clean_val)
                    line_values.append(val)
                except ValueError:
                    continue
            
            if not line_values:
                continue
                
            # Tomamos el valor máximo de la línea como el "monto" de esa línea
            # (ej: "Total 2 items: 5000" -> max(2, 5000) = 5000)
            line_amount = max(line_values)
            
            # Clasificar según palabras clave
            if "total a pagar" in line_lower or "a pagar" in line_lower or "total final" in line_lower:
                final_candidates.append(line_amount)
            elif "total" in line_lower or "suma" in line_lower or "valor total" in line_lower:
                general_candidates.append(line_amount)
        
        # 1. Prioridad: "Total a Pagar" (El último encontrado)
        if final_candidates:
            return final_candidates[-1]
            
        # 2. Prioridad: "Total" (El último encontrado, para manejar descuentos posteriores)
        if general_candidates:
            return general_candidates[-1]

        # 3. Fallback: Buscar el número más grande asociado a un signo $ en todo el texto
        fallback_pattern = r'(?i)[\$][\s]*([\d\.]+)'
        matches = re.findall(fallback_pattern, text)
        fallback_candidates = []
        for m in matches:
            try:
                val = float(m.replace('.', ''))
                fallback_candidates.append(val)
            except ValueError:
                continue
        
        if fallback_candidates:
            return max(fallback_candidates)

        return None
