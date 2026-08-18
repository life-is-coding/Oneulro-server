from typing import Optional

# 테마 키워드 -> 제목 수식어
_THEME_MODIFIERS: list[tuple[list[str], str]] = [
    (["바다", "해안", "자연"], "바다를 따라가는"),
    (["산", "등산", "힐링"], "산바람을 맞으며 걷는"),
    (["역사", "문화", "고궁"], "천년의 숨결을 느끼는"),
    (["음식", "맛집", "미식"], "골목마다 맛을 찾아가는"),
    (["감성", "사진", "야경"], "감성 가득한"),
]
_DEFAULT_MODIFIER = "느긋하게 즐기는"


def generate_title(destinations: list[str], total_days: int, theme_tags: Optional[list[str]] = None) -> str:
    """목적지·일수·테마를 조합해 코스 제목을 만든다 (규칙 기반, LLM 미사용)."""
    tags = theme_tags or []
    modifier = _DEFAULT_MODIFIER
    for keywords, phrase in _THEME_MODIFIERS:
        if any(kw in tag for tag in tags for kw in keywords):
            modifier = phrase
            break

    place_label = destinations[0] if len(destinations) == 1 else " · ".join(destinations[:2])
    nights = max(total_days - 1, 0)
    duration_label = f"{nights}박{total_days}일" if nights > 0 else f"{total_days}일"

    return f"{modifier} {place_label} {duration_label}"


def generate_reason(
    companion_type: Optional[str] = None,
    budget_min: Optional[int] = None,
    budget_max: Optional[int] = None,
    pet_mode: Optional[str] = None,
    theme_tags: Optional[list[str]] = None,
    natural_language_memo: Optional[str] = None,
) -> str:
    """입력 조건들을 반영 내역 문장으로 조립한다 (규칙 기반, LLM 미사용)."""
    clauses: list[str] = []

    if theme_tags:
        clauses.append(f"{', '.join(theme_tags)} 테마")
    if companion_type:
        clauses.append(f"{companion_type} 동행")
    if budget_min is not None or budget_max is not None:
        if budget_min is not None and budget_max is not None:
            clauses.append(f"예산 {budget_min:,}~{budget_max:,}원")
        elif budget_max is not None:
            clauses.append(f"예산 {budget_max:,}원 이내")
        else:
            clauses.append(f"예산 {budget_min:,}원 이상")
    if pet_mode and pet_mode.upper() not in ("NONE", "NO"):
        clauses.append("반려동물 동반 가능")
    if natural_language_memo:
        clauses.append(f"'{natural_language_memo}' 요청")

    if not clauses:
        return "고객님의 조건에 맞춰 코스를 구성했어요"

    return f"{', '.join(clauses)}을(를) 반영했어요"
