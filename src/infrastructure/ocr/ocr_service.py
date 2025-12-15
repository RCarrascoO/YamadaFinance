import pytesseract
from PIL import Image
import os
from pdf2image import convert_from_path

class OCRService:
    def extract_text(self, file_path: str) -> str:
        """
        Extrae texto de una imagen o PDF usando Tesseract OCR.
        """
        try:
            # Verificar si el archivo existe
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"No se encontró el archivo: {file_path}")

            text = ""
            
            # Detectar si es PDF
            if file_path.lower().endswith('.pdf'):
                # Convertir PDF a imágenes
                images = convert_from_path(file_path)
                for i, image in enumerate(images):
                    text += f"\n--- Página {i+1} ---\n"
                    text += pytesseract.image_to_string(image)
            else:
                # Es una imagen normal
                image = Image.open(file_path)
                text = pytesseract.image_to_string(image)
            
            return text
        except Exception as e:
            print(f"Error en OCR: {e}")
            return ""
