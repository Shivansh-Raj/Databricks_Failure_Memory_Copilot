import json, re
from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL, GROQ_TIMEOUT, GROQ_MAX_TOKENS

from app.utils import _SEPARATOR

def rank_candidates(error_text: str, code_text:str = None, candidates = []):
    """
    Rerank retrieved candidates based on relevance to the error text and code context.
    """
    
    if not candidates:
        return None, 0.0
    
    try:
        groq_client = Groq(api_key=GROQ_API_KEY, timeout=GROQ_TIMEOUT)
        context_block = "\n\n".join([
            f"Incident ID: {c['incident_id']}\n{c['document']}"
            for c in candidates
        ])

        prompt = f"""
            New Incident:
            {error_text}

            Code Context:
            {code_text}

            Candidate Incidents:
            {context_block}

            Select the best matching incident.

            Respond ONLY with valid JSON.
            No explanation.
            No markdown.
            No text outside JSON.

            Format exactly:

            {{
            "incident_id":str,
            "confidence": float,
            "resolution": string
            }}
        """
        
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=GROQ_MAX_TOKENS,
            temperature=0.0
        )
        #############################
        # print(_SEPARATOR )
        # print( "Retrieves candidates")
        # print(candidates)
        # print(_SEPARATOR)
        # print(response.choices[0].message.content.strip())
        # print(_SEPARATOR)
        #############################
        
        
        import json
        import re

        content = response.choices[0].message.content.strip()
        
        # removing markdown characters if present
        content = content.replace("```json", "").replace("```", "").strip()

        start = content.find("{")
        end = content.rfind("}")

        if start == -1 or end == -1:
            raise ValueError(f"No JSON object found in response:\n{content}")

        json_str = content[start:end + 1]

        parsed = json.loads(json_str)
        
        confidence = parsed.get("confidence", 0.0)

        try:
            confidence = float(confidence)
        except:
            confidence = 0.0
                
        return parsed.get("resolution"), confidence, parsed.get("incident_id")
    
    except Exception as e:
        print(f"__________________________________________________")
        print(f"Error occurred while ranking candidates: {e}")
        print(context_block)
        print(f"__________________________________________________")
        return None, 0.0, None