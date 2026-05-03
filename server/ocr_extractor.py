import os
import sys
import pytesseract
from PIL import Image
import io
from groq import Groq
import json

try:
    pytesseract.get_tesseract_version()
except Exception as e:
    raise RuntimeError("Tesseract not found. Make sure it's installed and in PATH.")

from config import GROQ_API_KEY, GROQ_MODEL, GROQ_TIMEOUT

_groq_client = Groq(api_key=GROQ_API_KEY, timeout=GROQ_TIMEOUT)

_SEPARATION_PROMPT = """You are an expert at analyzing Databricks and Apache Spark error outputs.
 
You will receive raw text extracted via OCR from one or two screenshots.
The text may contain a mix of error messages, stack traces, and Python/Scala code.
 
Your task:
1. Identify and extract the ERROR portion — this includes exception class names, error messages, and stack traces.
2. Identify and extract the CODE portion — this includes Python, Scala, or SQL code snippets.
3. If a section is not present, return an empty string for it.
4. Do NOT invent or hallucinate content that is not present in the raw text.
5. Clean up OCR artifacts (misread characters, broken indentation) as best you can.
 
Respond ONLY with valid JSON. No markdown. No explanation. No text outside JSON.
 
Format exactly:
{
  "error_text": "<extracted error and stack trace>",
  "code_text": "<extracted code snippet>"
}"""


def extract_from_image(image_byte : bytes):
    image = Image.open(io.BytesIO(image_byte))
    
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
        
    custom_config = r"--oem 3 --psm 6"
    text = pytesseract.image_to_string(image, config=custom_config)
    
    return text.strip()

def seperate_code_error(raw_texts: list[str]) -> str:
    combined = "\n \n -------------- Scrrenshot Break -------------- \n \n ".join(raw_texts)
    
    user_content = f"RAW OCR TEXT: \n \n {combined}"
    
    try:
        response = _groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages = [
                {"role":"system", "content":_SEPARATION_PROMPT},
                {"role":"user", "content": user_content},
            ],
            max_tokens=1500,
            temperature=0.0
        ) 
        content = response.choices[0].message.content.strip()
        print("_______________________________________________")
        print(content)
        print("_______________________________________________")
        content=  content.replace("```json","").replace("```", "").strip()
        
        start = content.find('{')
        end = content.find('}')
        if start == -1 or end == -1:
            raise ValueError(f"No JSON found in Groq response: {content}")
 
        parsed = json.loads(content[start: end + 1])
        
        return {
            "error_text": parsed.get("error_text", "").strip(),
            "code_text": parsed.get("code_text", "").strip(),
        }
    except Exception as e:
        return {
            "error_text": combined,
            "code_text":  "",
            "warning":    f"Groq separation failed: {str(e)} — raw OCR text returned in error_text",
        }
        
def process_screenshots(image_bytes_list: list[bytes]) -> dict:
    """
    Accepts 1 or 2 images.
    Returns: {error_text, code_text, raw_ocr_texts, warning}
    """
    if not image_bytes_list:
        raise ValueError("No images provided.")
 
    if len(image_bytes_list) > 2:
        raise ValueError("Maximum 2 screenshots allowed.")
 
    raw_texts = []
    for i, img_bytes in enumerate(image_bytes_list):
        try:
            text = extract_from_image(img_bytes)
            print("_____________________________________")
            print(text)
            print("_____________________________________")
            raw_texts.append(text)
        except Exception as e:
            raise ValueError(f"OCR failed on image {i + 1}: {str(e)}")
 
    result = seperate_code_error(raw_texts)
 
    result["raw_ocr_texts"] = raw_texts
 
    return result