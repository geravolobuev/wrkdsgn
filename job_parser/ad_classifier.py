from job_parser.job_classifier import classify_job_or_ad_by_score, job_score


AD_EXTRA_MARKERS = [
    "бесплатн",
    "набор заканчивается",
    "для регистрации",
    "жмите кнопку",
    "домашк",
    "школ",
    "образовательной лиценз",
    "#реклама",
    "рекламодател",
    "wb",
    "wildberries",
    "легкие деньги",
    "размещение объявлений",
    "размещение вакансий",
    "реклама:",
    "все наши проекты",
    "топ -",
    "часа топ",
    "закреп поста",
    "прайс",
    "стоимость размещения",
    "bot",
    "_bot",
]


def is_ad_or_funnel(text: str) -> bool:
    normalized = text.lower()

    hard_reject_markers = [
        "размещение объявлений",
        "размещение вакансий",
        "реклама:",
        "все наши проекты",
    ]
    if any(marker in normalized for marker in hard_reject_markers):
        return True

    if classify_job_or_ad_by_score(text) == "AD":
        return True

    marker_hits = sum(1 for marker in AD_EXTRA_MARKERS if marker in normalized)
    if marker_hits >= 2 and job_score(text) < 5:
        return True

    return False
