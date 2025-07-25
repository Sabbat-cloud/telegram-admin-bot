# localization.py
import gettext
import os
from telegram import Update
from telegram.ext import ContextTypes

# Define la ruta al directorio 'locales'
LOCALE_DIR = os.path.join(os.path.dirname(__file__), 'locales')
DEFAULT_LANG = 'es'
SUPPORTED_LANGS = ['es', 'en']

def get_user_language(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Obtiene el idioma del usuario desde user_data, o devuelve el idioma por defecto."""
    return context.user_data.get('lang', DEFAULT_LANG)

def get_translator(lang: str) -> gettext.GNUTranslations:
    """
    Carga y devuelve el objeto de traducción para un idioma específico.
    Si el idioma no es soportado, carga el idioma por defecto.
    """
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    
    # gettext busca un archivo .mo en locales/<lang>/LC_MESSAGES/base.mo
    t = gettext.translation('base', localedir=LOCALE_DIR, languages=[lang], fallback=True)
    return t

def setup_translation(context: ContextTypes.DEFAULT_TYPE) -> callable:
    """
    Configura la traducción para la solicitud actual.
    Devuelve la función `_` que se usará para traducir los textos.
    """
    user_lang = get_user_language(context)
    translator = get_translator(user_lang)
    return translator.gettext

def get_system_translator(lang: str = DEFAULT_LANG) -> callable:
    """
    Obtiene una función de traducción para tareas del sistema que no están
    vinculadas a un usuario específico. Usa el idioma por defecto.
    """
    translator = get_translator(lang)
    return translator.gettext
