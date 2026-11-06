"""Context assembly — what the agent is told about a student, per action.

One function per action type, each taking domain objects and returning a
plain dict. Deliberately pure and separate from the service that fetches the
rows: this is the seam where a future chat agent picks the same functions up
as tools, and it keeps "what the model sees" reviewable in isolation.

Assembly happens here, in `app`, and never in `agent`: the agent gets its
context whole at dispatch, so a Celery worker's job never depends on `app`
being up, and no node needs a database.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

from src.document.outline import outline_payload
from src.document.pseudonymize import author_form, pseudonymizer_for
from src.mentoring.application.exceptions import MissingContextError
from src.mentoring.domain.action import AgentAction
from src.mentoring.domain.draft import ThesisDraft
from src.mentoring.domain.fragment import PartState, ThesisFragment, ThesisPart
from src.mentoring.domain.student import MeetingNote, Student

# How much history is worth sending. Small on purpose — the point is to give
# the model the state of play, not the student's whole file.
_MAX_NOTES = 3


def _document_map(draft: ThesisDraft) -> dict[str, Any]:
    """What the whole document contains, for actions that see only part of it.

    Every node works from an excerpt — a thesis does not fit in a local
    model's context, and the excerpt starts at the beginning, where the later
    chapters are not. Without this map a model asked "is there a methodology
    chapter?" answers from what it was shown, and reports a chapter that
    exists on page 18 as never written. Computed here, over the full text,
    with no model involved.
    """
    # Pages only for a PDF: a Word file's page count is whatever the last
    # program to save it wrote, if anything.
    pages = draft.pages if draft.format == "pdf" and draft.pages > 0 else None
    return {**outline_payload(draft.content), "pages": pages}


def _research(student: Student) -> dict[str, Any]:
    """What the promoter agreed with the student, for actions that judge purpose.

    Neither is required, so `agent` says how to read them only when one is
    there. Structure and requirements stay without them: see ADR 0015.
    """
    return {
        "research_area": student.research_area,
        "research_aim": student.research_aim,
    }


def _thesis_metadata(student: Student) -> dict[str, Any]:
    """The metadata block the review nodes expect."""
    return {
        # Not the name: it would be the one thing the pseudonymizer cannot
        # take back out (ADR 0023), and the review only needs the form.
        "author_form": author_form(student.full_name),
        "title": student.current_topic or "",
        "year": student.created_at.year,
        "field_of_study": student.field_of_study,
        "thesis_type": str(student.thesis_type),
    }


# The thesis texts a context can carry, and what is not about the student.
_THESIS_KEYS = ("text", "current_text", "previous_text")
_NOT_ABOUT_THE_STUDENT = frozenset({"guidelines", "thresholds"})


def _swap_all(value: object, swap: Callable[[str], str]) -> object:
    if isinstance(value, str):
        return swap(value)
    if isinstance(value, Mapping):
        return {
            k: v if k in _NOT_ABOUT_THE_STUDENT else _swap_all(v, swap)
            for k, v in cast(Mapping[str, object], value).items()
        }
    if isinstance(value, list):
        return [_swap_all(v, swap) for v in cast(list[object], value)]
    return value


def pseudonymize_context(student: Student, context: dict[str, Any]) -> dict[str, Any]:
    """The context with the student, the promoter and the album number out.

    Every string goes through it, the meeting notes and the detail too: a
    promoter writes the student's name there as well. The document map is
    drawn again, because its offsets are into the text and a marker is not as
    long as the name it stands for (ADR 0023).
    """
    theses = [t for k in _THESIS_KEYS if isinstance(t := context.get(k), str)]
    swapped = cast(
        dict[str, Any], _swap_all(context, pseudonymizer_for(student.full_name, theses))
    )
    if "document_map" in swapped:
        # Counted again over the new text; the page count is the file's own.
        pages = cast(dict[str, Any], swapped["document_map"]).get("pages")
        swapped["document_map"] = {**outline_payload(swapped["text"]), "pages": pages}
    return swapped


def assemble_propose_topic_context(
    student: Student,
    recent_notes: Sequence[MeetingNote] = (),
    detail: str | None = None,
) -> dict[str, Any]:
    """Build the context for a topic proposal.

    Needs no document and no guidelines — the student record, the last few
    meeting notes and whatever the promoter typed are enough, which is why
    this is the first action to run end-to-end.
    """
    return {
        "field_of_study": student.field_of_study,
        "thesis_type": str(student.thesis_type),
        "current_topic": student.current_topic,
        "detail": detail,
        "recent_notes": [n.content for n in recent_notes[:_MAX_NOTES]],
    }


Guidelines = str | Mapping[str, str]
"""A rubric as it travels to `agent`: its four sections by key, or — for a
version published before rubrics had sections — the whole text."""


def _with_guidelines(
    context: dict[str, Any], guidelines: Guidelines | None
) -> dict[str, Any]:
    """Add the rubric of the student's guideline set.

    There are no built-in requirements to fall back on (ADR 0024): an action
    judged against a university's rules needs the promoter to have said
    which university's.
    """
    if guidelines is None:
        raise MissingContextError(
            "Choose the university guidelines for this student first"
        )
    rubric = guidelines if isinstance(guidelines, str) else dict(guidelines)
    return {**context, "guidelines": rubric}


def assemble_evaluate_methodology_context(
    student: Student,
    latest_draft: ThesisDraft | None,
    detail: str | None = None,
    guidelines: Guidelines | None = None,
) -> dict[str, Any]:
    """Build the context for a methodology review of the current version."""
    if latest_draft is None:
        raise MissingContextError(
            "Methodology can only be assessed once a draft has been uploaded"
        )
    return _with_guidelines(
        {
            "text": latest_draft.content,
            "document_map": _document_map(latest_draft),
            "thesis_type": str(student.thesis_type),
            "field_of_study": student.field_of_study,
            "current_topic": student.current_topic,
            **_research(student),
            "version_number": latest_draft.version_number,
            "detail": detail,
        },
        guidelines,
    )


def notes_between_versions(
    notes: Sequence[MeetingNote],
    latest_drafts: Sequence[ThesisDraft],
) -> list[MeetingNote]:
    """The meetings the newer version could answer to, oldest first.

    A note from before the older version is already in it, and one from after
    the newer version could not have been acted on. No `_MAX_NOTES` here: the
    two uploads bound the window, and the note dropped by a cap would be the
    oldest request, the one the student had the most time for.
    """
    if len(latest_drafts) < 2:
        return []
    current, previous = latest_drafts[0], latest_drafts[1]
    between = [
        n for n in notes if previous.created_at <= n.occurred_at <= current.created_at
    ]
    return sorted(between, key=lambda n: n.occurred_at)


def assemble_check_progress_context(
    student: Student,
    latest_drafts: Sequence[ThesisDraft],
    notes: Sequence[MeetingNote] = (),
    detail: str | None = None,
) -> dict[str, Any]:
    """Build the context for comparing the two newest versions.

    Takes exactly the two rows the action needs — newest first — rather than
    the student's whole upload history, and the notes `notes_between_versions`
    picked for them.
    """
    if len(latest_drafts) < 2:
        raise MissingContextError("Progress needs two uploaded versions to compare")
    current, previous = latest_drafts[0], latest_drafts[1]
    return {
        "current_text": current.content,
        "current_version": current.version_number,
        "previous_text": previous.content,
        "previous_version": previous.version_number,
        "current_topic": student.current_topic,
        "field_of_study": student.field_of_study,
        "thesis_type": str(student.thesis_type),
        **_research(student),
        "meeting_notes": [n.content for n in notes],
        "detail": detail,
    }


def assemble_review_fragment_context(
    student: Student,
    part: ThesisPart,
    fragment: ThesisFragment,
    previous: ThesisFragment | None,
    other_parts: Sequence[tuple[ThesisPart, PartState]],
    recent_notes: Sequence[MeetingNote],
    detail: str | None = None,
) -> dict[str, Any]:
    """Build the context for a word on one fragment.

    What is around it says what it is not expected to be: the names of the
    other parts keep the model from asking this one for them. The previous
    round is what makes a later round a follow-up rather than a fresh start.
    Its text may be purged while the feedback on it stays.

    No guidelines, on purpose: formal requirements are for the finished thesis.
    """
    if fragment.is_purged:
        raise MissingContextError("This fragment's text has been purged")
    context: dict[str, Any] = {
        "text": fragment.content,
        "part_name": part.name,
        "round_number": fragment.round_number,
        "other_parts": [
            {"name": other.name, "state": str(state)} for other, state in other_parts
        ],
        "field_of_study": student.field_of_study,
        "thesis_type": str(student.thesis_type),
        "current_topic": student.current_topic,
        **_research(student),
        "recent_notes": [n.content for n in recent_notes[:_MAX_NOTES]],
        "detail": detail or fragment.question,
    }
    if previous is not None:
        context["previous_verdict"] = (
            str(previous.verdict) if previous.verdict else None
        )
        context["previous_feedback"] = previous.feedback
        context["previous_text"] = previous.text
    return context


def assemble_draft_meeting_note_context(
    student: Student,
    recent_notes: Sequence[MeetingNote] = (),
    detail: str | None = None,
) -> dict[str, Any]:
    """Build the context for writing up a meeting from rough points."""
    if not (detail or "").strip():
        raise MissingContextError(
            "Rough notes from the meeting are what this action writes up"
        )
    return {
        "detail": detail,
        "current_topic": student.current_topic,
        "recent_notes": [n.content for n in recent_notes[:_MAX_NOTES]],
    }


def assemble_draft_student_email_context(
    student: Student,
    trial_review: AgentAction | None,
    detail: str | None = None,
) -> dict[str, Any]:
    """Build the context for a mail: the review and its findings, not the thesis."""
    review_text = (
        str(trial_review.structured_output().get("summary") or "").strip()
        if trial_review
        else ""
    )
    if trial_review is None or not review_text:
        raise MissingContextError(
            "A mail to the student is written from a trial review — run one first"
        )
    return {
        "current_topic": student.current_topic,
        "review_text": review_text,
        "findings": trial_review.findings(),
        "detail": detail,
    }


def assemble_defence_questions_context(
    student: Student,
    latest_draft: ThesisDraft | None,
    detail: str | None = None,
) -> dict[str, Any]:
    """Build the context for preparing defence questions."""
    if latest_draft is None:
        raise MissingContextError(
            "Defence questions are asked about a thesis — upload one first"
        )
    return {
        "text": latest_draft.content,
        "document_map": _document_map(latest_draft),
        "current_topic": student.current_topic,
        "field_of_study": student.field_of_study,
        "thesis_type": str(student.thesis_type),
        **_research(student),
        "version_number": latest_draft.version_number,
        "detail": detail,
    }


def assemble_verify_bibliography_context(
    student: Student,
    latest_draft: ThesisDraft | None,
) -> dict[str, Any]:
    """Build the context for checking the bibliography against Crossref.

    The whole text and its map: the agent cuts the bibliography out itself,
    and only the entries — never the text — go on to Crossref.
    """
    if latest_draft is None:
        raise MissingContextError(
            "The bibliography is checked in a thesis — upload one first"
        )
    return {
        "text": latest_draft.content,
        "document_map": _document_map(latest_draft),
        "thesis_type": str(student.thesis_type),
        "version_number": latest_draft.version_number,
    }


def assemble_generate_review_context(
    student: Student,
    latest_draft: ThesisDraft | None,
    detail: str | None = None,
    review_tone: str = "auto",
    guidelines: Guidelines | None = None,
    thresholds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the context for the full four-node review.

    `guidelines` is the rubric of the guideline set the promoter chose for
    this student; without one the review is refused. `thresholds` come from
    the same set: the requirements node compares them with the document map,
    ADR 0020.
    """
    if latest_draft is None:
        raise MissingContextError("There is no thesis to review yet")
    context = _with_guidelines(
        {
            "text": latest_draft.content,
            "document_map": _document_map(latest_draft),
            "metadata": _thesis_metadata(student),
            "thesis_type": str(student.thesis_type),
            **_research(student),
            "review_tone": review_tone,
            "version_number": latest_draft.version_number,
            "detail": detail,
        },
        guidelines,
    )
    return {**context, "thresholds": dict(thresholds)} if thresholds else context
