import os
import openai
import google.generativeai as genai
from zhipuai import ZhipuAI
import time

def translate_text(text, target_lang, model_name, api_key):
    """
    Translates a single string of text into the target language using the specified model.
    """
    if not text or str(text).strip() == "":
        return ""

    # Common System Prompt
    # Note: Some models support system prompt better than others.
    # We want strict translation, no yapping.
    system_instruction = (
        f"You are a professional translator. Translate the following text into {target_lang}. "
        "Rules:\n"
        "1. Maintain original formatting, casing, symbols, and HTML tags.\n"
        "2. Return ONLY the translated text. No explanations, no quotes around the output unless in source.\n"
        "3. If the text is a placeholder or code that shouldn't be translated, return it as is."
    )

    try:
        if model_name == "DeepSeek":
            # DeepSeek uses OpenAI compatible API
            client = openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": str(text)}
                ],
                temperature=0.3, # Low temperature for more deterministic translations
                stream=False
            )
            return response.choices[0].message.content.strip()

        elif model_name == "Gemini":
            genai.configure(api_key=api_key)
            # Gemini often works better with a direct prompt structure if system instruction isn't strictly supported in all versions
            # But gemini-pro supports it.
            model = genai.GenerativeModel('gemini-pro')
            
            # Constructing a prompt that includes instruction
            full_prompt = f"{system_instruction}\n\nOriginal Text: {text}\nTranslation:"
            
            response = model.generate_content(full_prompt)
            return response.text.strip()

        elif model_name == "GLM (智谱)":
            client = ZhipuAI(api_key=api_key)
            response = client.chat.completions.create(
                model="glm-4",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": str(text)}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content.strip()

        elif model_name == "Kimi (Moonshot)":
            # Kimi uses OpenAI compatible API
            client = openai.OpenAI(api_key=api_key, base_url="https://api.moonshot.cn/v1")
            response = client.chat.completions.create(
                model="moonshot-v1-8k",
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
