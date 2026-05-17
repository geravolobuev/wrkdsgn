from parser.job_classifier import classify_job_or_ad_by_score, job_score


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
]


def is_ad_or_funnel(text: str) -> bool:
    normalized = text.lower()

    if classify_job_or_ad_by_score(text) == "AD":
        return True

    marker_hits = sum(1 for marker in AD_EXTRA_MARKERS if marker in normalized)
    if marker_hits >= 2 and job_score(text) < 5:
        return True

    return False
