"""Small, conservative signals to support a human reviewer, not automatic approval."""
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Rules adapted from VHR-07 services/moderation.py (MIT; THIRD_PARTY_NOTICES).
PROHIBITED = ('thuốc lá điện tử', 'vape', 'vũ khí', 'súng', 'đạn', 'pháo',
              'ma tuý', 'ma túy', 'cần sa', 'thuốc kê đơn')
BLOCKING_FLAGS = frozenset({'sensitive_information', 'prohibited'})


class ModerationReport(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    risk_score: float | None = Field(default=None, ge=0, le=1)
    risk_level: Literal['low', 'attention', 'high']
    categories: list[str]
    reason: str
    policy_version: str = 'nm-human-review-v1'
    model_version: str = 'rules-only'
    requires_review: Literal[True] = True
    ai_status: Literal['not_requested', 'unavailable', 'advisory'] = 'not_requested'
    score_calibrated: Literal[False] = False


REASONS = {
    'sensitive_information': 'Có dấu hiệu thông tin liên hệ/địa chỉ; cần người bán viết lại.',
    'prohibited': 'Có từ khóa mặt hàng bị cấm theo chính sách demo; BQL cần từ chối và kiểm tra.',
    'profanity': 'Có ngôn từ không phù hợp cần BQL kiểm tra.',
    'spam': 'Có dấu hiệu lặp nội dung hoặc liên kết.',
    'suspicious': 'Có yêu cầu thanh toán trước hoặc nội dung cần xác minh; chưa kết luận gian lận.',
    'external_link': 'Có liên kết ngoài cần BQL kiểm tra.',
    'abnormal_price': 'Giá cần BQL kiểm tra; không phải định giá thị trường.',
    'ai_suspicious': 'Model trích xuất gợi ý cần chú ý; chỉ là tín hiệu tư vấn.',
}


def moderation_flags(title: str, condition: str) -> list[str]:
    content = f'{title} {condition}'
    folded = unicodedata.normalize('NFD', content.casefold().replace('đ', 'd'))
    folded = ''.join(c for c in folded if unicodedata.category(c) != 'Mn')
    flags = []
    if (re.search(r'(?<!\d)(?:\+?84|0)[\s.()-]*(?:\d[\s.()-]*){8,10}(?!\d)', content)
            or re.search(r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b', content)
            or re.search(r'(?<!\d)\d{9,12}(?!\d)', content)
            or re.search(r'\b(?:can(?: ho)?|phong|toa|tang|block|chung cu)\s*[:#-]?\s*[a-z0-9]{1,6}\b', folded)
            or re.search(r'\bso\s+\d+[a-z]?\s+duong\s+\w+', folded)):
        flags.append('sensitive_information')
    if re.search(r'\b(?:dit me|du me|deo|fuck|shit)\b', folded):
        flags.append('profanity')
    if re.search(r'(.)\1{7,}|(?:https?://|www\.)', folded):
        flags.append('spam')
    if re.search(r'\b(?:chuyen khoan truoc|dat coc truoc|cam|vu khi|ma tuy)\b', folded):
        flags.append('suspicious')
    if re.search(r'(?:https?://|www\.)\S+|\b[\w-]+\.(?:com|net|org|vn|xyz|io|shop)\b', folded):
        flags.append('external_link')
    accented = unicodedata.normalize('NFC', content).casefold()
    for keyword in PROHIBITED:
        keyword_folded = ''.join(c for c in unicodedata.normalize('NFD', keyword.replace('đ','d'))
                                 if unicodedata.category(c) != 'Mn')
        if re.search(r'\b'+re.escape(keyword)+r'\b', accented) or (
                ' ' in keyword and re.search(r'\b'+re.escape(keyword_folded)+r'\b', folded)):
            flags.append('prohibited')
            break
    return flags


def assess_listing(title: str, condition: str, price_vnd: int, *, ai_flags: bool = False,
                   model_version: str = 'rules-only',
                   ai_status: Literal['not_requested', 'unavailable', 'advisory'] = 'not_requested') -> ModerationReport:
    """Rules plus bounded model signal; scores are NOT calibrated probabilities.

    Reuse extraction risk flags rather than making a second paid model request.
    No arbitrary model reason/PII is copied into the public report.
    """
    flags = moderation_flags(title, condition)
    if price_vnd <= 0 or price_vnd > 1_000_000_000:
        flags.append('abnormal_price')
    if ai_flags:
        flags.append('ai_suspicious')
    flags = list(dict.fromkeys(flags))
    if not re.fullmatch(r'[A-Za-z0-9._:-]{1,100}', model_version):
        model_version = 'invalid-model-name'
    reason = ' '.join(REASONS[flag] for flag in flags) or 'Chưa thấy dấu hiệu theo bộ luật demo; vẫn cần BQL duyệt.'
    if ai_status == 'unavailable':
        reason += ' AI không khả dụng; không được coi là đã kiểm tra bằng model.'
    return ModerationReport(risk_level='high' if BLOCKING_FLAGS.intersection(flags) else 'attention' if flags else 'low',
                            categories=flags, reason=reason, model_version=model_version, ai_status=ai_status)
