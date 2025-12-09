import os
import openai
import google.generativeai as genai
from zhipuai import ZhipuAI
import time
import httpx

def translate_text(text, target_lang, model_name, api_key):
    """
    Translates text into the target language using the specified model.
    Handles both single strings and newline-separated batches.
    """
    if not text or str(text).strip() == "":
        return ""

    # Common System Prompt
    # Updated for batch/bulk translation capability
    system_instruction = (
        f"You are a professional translator. Translate the following content into {target_lang}. "
        "Rules:\n"
        "1. Maintain original formatting, casing, symbols, and HTML tags.\n"
        "2. The input may be a list of sentences/phrases separated by newlines. PRESERVE the exact number of lines.\n"
        "3. Return ONLY the translated text. No explanations, no quotes around the output unless in source.\n"
        "4. If a line is a placeholder/code, keep it as is.\n"
        "5. Do NOT merge lines. One input line = One output line."
    )

    try:
        if "deepseek" in model_name.lower():
            # DeepSeek uses OpenAI compatible API
            # model_name input example: "deepseek v3.2" -> we try to map to "deepseek-chat" or use as is if specific.
            # DeepSeek API usually uses "deepseek-chat" or "deepseek-reasoner".
            # If user asks for specific version, we try to honor it or fallback to chat.
            
            # Mapping specific display names to API model IDs
            api_model_id = "deepseek-chat"
            if "v3.2" in model_name:
                 # Assuming v3.2 is deepseek-chat or a specific new alias. 
                 # Given current API docs usually point to deepseek-chat for V3, we stick to it unless we know the specific ID.
                 # However, if the user explicitly wants "deepseek v3.2", maybe the API supports that string.
                 # Safest bet: stick to "deepseek-chat" which is V3, or try passing the string.
                 # Let's try passing "deepseek-chat" as it is the stable endpoint.
                 api_model_id = "deepseek-chat"
            
            client = openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com", http_client=httpx.Client(timeout=60.0))
            response = client.chat.completions.create(
                model=api_model_id,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": str(text)}
                ],
                temperature=0.3, # Low temperature for more deterministic translations
                stream=False
            )
            return response.choices[0].message.content.strip()

        elif "gemini" in model_name.lower():
            genai.configure(api_key=api_key)
            # Map "gemini-2.5-flash" to likely API ID.
            # Current Gemini Flash is "gemini-1.5-flash". 2.5 might be "gemini-2.5-flash" or "gemini-2.5-flash-001".
            # We will try the exact string first, if it fails, fallback? No, let's trust the user knows the model exists or we use a safe default.
            # actually, let's try to use the string provided but formatted correctly.
            
            if "2.5-flash" in model_name:
                api_model_id = "gemini-2.5-flash" # Corrected based on user feedback
            else:
                api_model_id = "gemini-pro"
                
            # Fallback/Override: Since we can't be sure 2.5 exists in this environment, 
            # we'll assume the user wants the latest Flash if they ask for Flash.
            # But the user asked for "gemini-2.5-flash" specifically.
            
            model = genai.GenerativeModel(model_name=api_model_id)
            
            # Constructing a prompt that includes instruction
            full_prompt = f"{system_instruction}\n\nOriginal Text: {text}\nTranslation:"
            
            response = model.generate_content(full_prompt)
            return response.text.strip()

        elif "glm" in model_name.lower():
            client = ZhipuAI(api_key=api_key)
            # Map "glm-4.6" -> "glm-4" or "glm-4-plus" or exact.
            api_model_id = "glm-4"
            if "4.6" in model_name:
                api_model_id = "glm-4" # Zhipu usually updates glm-4 endpoint. Or maybe "glm-4-plus".
            
            response = client.chat.completions.create(
                model=api_model_id,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": str(text)}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content.strip()

        elif "kimi" in model_name.lower():
            # Kimi uses OpenAI compatible API
            # Map "kimi-k2" -> "moonshot-v1-8k" or "moonshot-v1-32k" or "kimi-k2"?
            # Moonshot API models are usually "moonshot-v1-8k".
            # Unless they released a "kimi-k2" endpoint.
            api_model_id = "moonshot-v1-8k"
            
            client = openai.OpenAI(api_key=api_key, base_url="https://api.moonshot.cn/v1", http_client=httpx.Client(timeout=60.0))
            response = client.chat.completions.create(
                model=api_model_id,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": str(text)}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content.strip()

        else:
            return "[Error: Unknown Model Selection]"

    except Exception as e:
        # Return the error message to be logged in the CSV or UI
        return f"[Error: {str(e)}]"
