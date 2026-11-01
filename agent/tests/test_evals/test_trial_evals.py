"""The parts of the trial eval that need no model."""

from evals.trial import (
    MailVerdict,
    TrialVerdict,
    mail_problems,
    mail_verdict_problems,
    trial_problems,
)

_GOOD_MAIL = """Dzień dobry,

po lekturze całości widać, że zakończenie wymaga pracy.

1. Zakończenie: 39% badanych wskazało płacę, proszę to uwzględnić.

W razie pytań proszę pisać.

Pozdrawiam"""


def test_a_good_mail_has_no_problems() -> None:
    assert mail_problems(_GOOD_MAIL) == []


def test_a_percentage_from_the_thesis_is_not_a_score() -> None:
    assert "39%" in _GOOD_MAIL
    assert not any("39" in p for p in mail_problems(_GOOD_MAIL))


def test_the_assessment_stays_out_of_the_mail() -> None:
    problems = mail_problems(
        _GOOD_MAIL.replace("Zakończenie:", "Ocena 7/10, na obronie:")
    )

    assert any("7/10" in p for p in problems)
    assert any("obron" in p for p in problems)


def test_a_mail_keeps_its_shape() -> None:
    points = "\n".join(f"{i}. Punkt." for i in range(1, 7))

    assert "6 points, limit 5" in mail_problems(f"Dzień dobry,\n{points}\nPozdrawiam")
    assert "no numbered corrections" in mail_problems("Dzień dobry,\nPozdrawiam")
    assert "does not open with the greeting" in mail_problems("Witam\n1. X\nPozdrawiam")
    assert "does not end on the sign-off" in mail_problems(
        "Dzień dobry,\n1. X\nPozdrawiam\nJan"
    )


def test_a_defect_without_a_way_forward_counts() -> None:
    verdict = TrialVerdict(acts_on={"1": True}, first_is_most_important=True)

    assert trial_problems(verdict, ("a", "b")) == ["no way forward: b"]


def test_what_the_judge_finds_in_a_mail_is_reported() -> None:
    verdict = MailVerdict(added=["x"], gendered=["Pani"], actionable=True)

    assert mail_verdict_problems(verdict) == [
        "added: x",
        "gendered: Pani",
        "the tone is off",
    ]
