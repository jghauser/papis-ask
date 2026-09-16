"""Citation recognition must leave ordinary parenthesized text intact."""

import json
from types import SimpleNamespace

import pytest

from papis_ask.output import (
    to_json_output,
    to_markdown_output,
    to_terminal_output,
    transform_answer,
)


def make_answer(text, *, with_context=True):
    doc = SimpleNamespace(
        other={"ref": "Kalman_1960", "papis_id": "abc123"},
        pages="35-45",
        file_location="/library/paper.pdf",
    )
    context = SimpleNamespace(
        text=SimpleNamespace(name="abc123 pages 6-7", doc=doc, text="Evidence"),
        context="Summary",
        score=5,
    )
    return SimpleNamespace(
        question="Question",
        answer=text,
        contexts=[context] if with_context else [],
    )


@pytest.mark.parametrize(
    "text",
    [
        "Evaluate f(x).",
        "At step (k+1).",
        "The extended Kalman filter (EKF).",
        "An unknown source (unknown).",
        "An unknown source (unknown pages 6-7).",
    ],
)
def test_preserves_unrecognized_parentheses(text):
    assert transform_answer(make_answer(text)).answer == text


def test_preserves_parentheses_without_contexts():
    text = "Evaluate f(x) at (k+1); (abc123 pages 6) is unverified."
    assert transform_answer(make_answer(text, with_context=False)).answer == text


@pytest.mark.parametrize(
    ("citation", "expected"),
    [
        ("(abc123)", "[@Kalman_1960]"),
        ("(abc123 pages 6)", "[@Kalman_1960, p. 6]"),
        ("(abc123 pages 6-7)", "[@Kalman_1960, p. 6-7]"),
    ],
)
def test_converts_recognized_citations(citation, expected):
    assert transform_answer(make_answer(citation)).answer == expected


def test_handles_citations_and_ordinary_parentheses_together():
    text = "Evaluate f(x) (abc123 pages 6-7), then (k+1) (abc123)."
    expected = "Evaluate f(x) [@Kalman_1960, p. 6-7], then (k+1) [@Kalman_1960]."
    assert transform_answer(make_answer(text)).answer == expected


def test_markdown_preserves_parentheses_and_formats_citations():
    result = to_markdown_output(make_answer("Use f(x) (abc123 pages 6)."))
    assert "Use f(x) [@Kalman_1960, p. 6]." in result


def test_terminal_preserves_parentheses_and_formats_citations(capsys):
    to_terminal_output(
        make_answer("Use f(x) (abc123 pages 6)."), context=False, excerpt=False
    )
    assert "Use f(x) [@Kalman_1960, p. 6]." in capsys.readouterr().out


def test_json_keeps_original_answer():
    text = "Use f(x) (abc123 pages 6)."
    result = json.loads(to_json_output(make_answer(text)))
    assert result["answer"] == text
