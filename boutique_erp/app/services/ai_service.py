"""
AI Integration Service using Google Gemini.
"""
import logging
from google import genai

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configure Gemini API if key is available
if not settings.gemini_api_key:
    logger.warning("GEMINI_API_KEY is not set. AI features will not work.")

async def generate_product_description(title: str, category: str, attributes: dict, base_sell_price: int = None, stock_quantity: int = None, prompt_template: str = None) -> str:
    """
    Generate an engaging product caption using Gemini.
    Enforces the rule that AI only acts as a copywriter, never as a data source.
    """
    if not settings.gemini_api_key:
        return "❌ خطا: کلید دسترسی به هوش مصنوعی تنظیم نشده است."

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        
        # Format the database values
        db_context = f"""
        Product Title/SKU: {title}
        Category: {category}
        Base Sell Price: {base_sell_price if base_sell_price is not None else 'N/A'} Rials
        Stock: {stock_quantity if stock_quantity is not None else 'N/A'}
        Specifications: {attributes}
        """

        system_instruction = """
        You are a professional copywriter for an e-commerce jewelry and accessory store.
        CRITICAL RULE: The Database is the ONLY source of truth.
        Do NOT invent or hallucinate prices, discounts, inventory, or product specifications.
        If information is missing in the DATABASE VALUES, leave it empty. Never guess.
        Keep the tone engaging, write in Persian (Farsi), and use appropriate emojis.
        """

        user_prompt = prompt_template or "Write a beautiful and engaging caption for this product for our Telegram/Bale channel. Include the price and specs if available."
        
        full_prompt = f"{system_instruction}\n\nDATABASE VALUES:\n{db_context}\n\nPROMPT TEMPLATE:\n{user_prompt}"
        
        interaction = client.interactions.create(
            model="gemini-flash-latest",
            input=full_prompt
        )
        return interaction.output_text.strip()
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return f"❌ خطا در ارتباط با هوش مصنوعی: {str(e)}"

async def generate_cms_post(topic: str, category_name: str = None, prompt_template: str = None) -> str:
    """
    Generate a CMS post based on a topic and a category's prompt template.
    """
    if not settings.gemini_api_key:
        return "❌ خطا: کلید دسترسی به هوش مصنوعی تنظیم نشده است."

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        
        system_instruction = """
        You are a professional copywriter for an e-commerce jewelry and accessory store.
        Write engaging content for our Telegram/Bale channel in Persian (Farsi).
        Use appropriate emojis and formatting.
        """
        
        user_prompt = prompt_template or "یک پست جذاب با توجه به موضوع زیر بنویس."
        
        full_prompt = f"{system_instruction}\n\nTOPIC / KEYWORDS:\n{topic}\n\nCATEGORY: {category_name or 'General'}\n\nPROMPT TEMPLATE:\n{user_prompt}"
        
        interaction = client.interactions.create(
            model="gemini-flash-latest",
            input=full_prompt
        )
        return interaction.output_text.strip()
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return f"❌ خطا در ارتباط با هوش مصنوعی: {str(e)}"
