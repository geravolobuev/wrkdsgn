import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from job_parser.job_classifier import classify_job_or_ad_by_score, job_score


def _print_case(name: str, text: str) -> None:
    score = job_score(text)
    decision = classify_job_or_ad_by_score(text)
    print(f"{name}: decision={decision} score={score}")


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

    assert classify_job_or_ad_by_score(valid_vacancy) == "JOB"
    assert classify_job_or_ad_by_score(invalid_news) == "AD"
    assert classify_job_or_ad_by_score(ambiguous_post) in {"AD", "UNCERTAIN"}
    assert classify_job_or_ad_by_score(freelance_hiring) == "JOB"

    assert job_score(valid_vacancy) >= 3
    assert job_score(invalid_news) <= 0


if __name__ == "__main__":
    run_examples()
