from google import genai
import os

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY no encontrada.")
    exit(1)

client = genai.Client(api_key=api_key)

print("Modelos disponibles:")
for m in client.models.list():
    print(m.name)
