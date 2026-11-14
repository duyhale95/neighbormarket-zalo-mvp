"""Small, conservative signals to support a human reviewer, not automatic approval."""
import re
import unicodedata


def moderation_flags(title: str, condition: str) -> list[str]:
    content = f'{title} {condition}'
    folded = unicodedata.normalize('NFD', content.casefold().replace('đ', 'd'))
    folded = ''.join(c for c in folded if unicodedata.category(c) != 'Mn')
    flags = []
    if (re.search(r'(?<!\d)(?:\+?84|0)[\s.()-]*(?:\d[\s.()-]*){8,10}(?!\d)', content)
            or re.search(r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b', content)
            or re.search(r'(?<!\d)\d{9,12}(?!\d)', content)):
        flags.append('sensitive_information')
    if re.search(r'\b(?:dit me|du me|deo|fuck|shit)\b', folded):
        flags.append('profanity')
    if re.search(r'(.)\1{7,}|(?:https?://|www\.)', folded):
        flags.append('spam')
    if re.search(r'\b(?:chuyen khoan truoc|dat coc truoc|cam|vu khi|ma tuy)\b', folded):
        flags.append('suspicious')
    return flags
