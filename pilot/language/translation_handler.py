from pilot.configs.config import Config
from pilot.language.lang_content_mapping import get_lang_content

CFG = Config()


def get_lang_text(key):
    return get_lang_content(key, CFG.LANGUAGE)
