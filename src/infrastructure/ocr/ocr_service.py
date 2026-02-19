import os
import json
from google import genai
from PIL import Image
from pdf2image import convert_from_path
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OCRService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY no encontrada en variables de entorno.")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-3-flash-preview"

    def extract_data(self, file_path: str) -> dict:
        """
        Envía la imagen/PDF a Gemini Flash y retorna un JSON estructurado.
        """
        if not self.client:
            return {"error": "GEMINI_API_KEY no configurada. El OCR no está disponible."}

        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"No se encontró el archivo: {file_path}")

            # Manejar PDF (convertir primera página a imagen)
            if file_path.lower().endswith('.pdf'):
                images = convert_from_path(file_path)
                if not images:
                    return {"error": "No se pudo convertir el PDF a imagen"}
                img = images[0]
            else:
                img = Image.open(file_path)

            prompt = """
            Analiza esta boleta/recibo y extrae la siguiente información en formato JSON estrictamente:
            {
                "merchant": "Nombre del comercio o tienda",
                "date": "Fecha en formato DD-MM-YYYY (si no está, null)",
                "total_amount": 0, (número entero o decimal, sin símbolos de moneda)
                "category": "Categoría sugerida (ej: Comida, Supermercado, Transporte, Salud, Hogar, Ocio, Otros)",
                "items": ["lista de items comprados (resumida)"],
                "raw_text": "Texto completo extraído de la boleta (resumen)"
            }
            Si no encuentras algún dato, usa null. Responde SOLO con el JSON.
            """

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, img]
            )

            # Limpiar respuesta (a veces Gemini incluye ```json ... ```)
            text_response = response.text.strip()
            if text_response.startswith("```json"):
                text_response = text_response[7:]
            elif text_response.startswith("```"):
                text_response = text_response[3:]
            if text_response.endswith("```"):
                text_response = text_response[:-3]

            data = json.loads(text_response.strip())
            return data

        except Exception as e:
            logger.error(f"Error en Gemini OCR: {e}")
            return {"error": str(e)}
