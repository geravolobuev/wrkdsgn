import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from parser.job_classifier import calculate_job_score, classify_job_post, classify_job_post_with_details


def _print_case(name: str, text: str) -> None:
    result = classify_job_post_with_details(text)
    print(
        f"{name}: accepted={result['accepted']} score={result['score']} confidence={result['confidence']} "
        f"positives={result['matched_positive']} negatives={result['matched_negative']}"
    )


def run_examples() -> None:
    valid_vacancy = (
        "We are hiring a Middle Product Designer (remote). "
        "Send CV and portfolio to hr@studio.com or DM @design_hr"
    )

    invalid_news = (
        "Design news: new article and podcast about UX trends. "
        "Join webinar this Friday."
    )

    ambiguous_post = (
        "Today we discuss design career paths and interview experiences in our meetup."
    )

    freelance_hiring = (
        "Ищем freelance UX/UI designer на проект. "
        "Оплата 120000 ₽, пишите @teamlead, присылайте портфолио"
    )

    _print_case("valid_vacancy", valid_vacancy)
    _print_case("invalid_news", invalid_news)
    _print_case("ambiguous_post", ambiguous_post)
    _print_case("freelance_hiring", freelance_hiring)

    assert classify_job_post(valid_vacancy) is True
    assert classify_job_post(invalid_news) is False
    assert classify_job_post(ambiguous_post) is False
    assert classify_job_post(freelance_hiring) is True

    assert calculate_job_score(valid_vacancy) > 0
    assert calculate_job_score(invalid_news) < 0


if __name__ == "__main__":
    run_examples()
