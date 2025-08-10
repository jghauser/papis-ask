import re
import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table


def to_latex_math(text: str) -> str:
    return (
        text.replace(r"\(", "$")
        .replace(r"\)", "$")
        .replace(r"\[", "$$")
        .replace(r"\]", "$$")
    )


def transform_answer(answer: Any) -> Any:
    """Transform the answer to format references correctly using Papis references."""
    # Convert to latex math
    answer.answer = to_latex_math(answer.answer)

    # Create a mapping of document names to references
    papis_id_to_ref = {}

    # First pass: collect all document names and their references and convert to latex math
    for context in answer.contexts:
        context.context = to_latex_math(context.context)
        ref = context.text.doc.other.get("ref", context.text.doc.other.get("papis_id"))
        papis_id_to_ref[context.text.name.split()[0]] = ref

    # Replace references in the answer text
    # Pattern: (papis_id pages X-N) -> [@ref, p. X-N]
    def replace_citation(match):
        papis_id = match.group(1)
        pages = match.group(2)

        ref = papis_id_to_ref.get(papis_id, papis_id)
        # Format pages as p. X-N
        formatted_pages = f"p. {pages}" if pages else ""

        if formatted_pages:
            return f"[@{ref}, {formatted_pages}]"
        else:
            return f"[@{ref}]"

    # Pattern to match citations like (papis_id pages X-N)
    citation_pattern = r"\(([^)\s]+?)(?:\s+pages\s+([^)]+))?\)"
    answer.answer = re.sub(citation_pattern, replace_citation, answer.answer)

    return answer


def to_terminal_output(
    answer: Any,
    context: bool,
    excerpt: bool,
) -> None:
    """Format and print the answer with optional context and excerpts."""
    answer = transform_answer(answer)
    console = Console()

    # Format question
    question_md = Text(answer.question)
    console.print(
        Panel(
            question_md,
            title=Text("Question", style="magenta bold"),
            border_style="bright_black",
        )
    )

    # Create a Text object for the answer
    answer_text = Text(answer.answer)

    # Define a regex pattern for citations like [@XYZ]
    citation_pattern = r"\[@[^\]]+\]"

    # Highlight all matches in blue
    answer_text.highlight_regex(citation_pattern, style="blue")

    # Display in panel
    console.print(
        Panel(
            answer_text,
            title=Text("Answer", style="green bold"),
            border_style="bright_black",
        )
    )

    # Create references with colored names
    references = []
    for answer_context in answer.contexts:
        filename = Path(answer_context.text.doc.file_location).name
        ref = answer_context.text.doc.other.get(
            "ref", answer_context.text.doc.other.get("papis_id")
        )
        pages = answer_context.text.doc.pages
        reference_line = Text("- ")
        reference_line.append(f"@{ref}, p. {pages}", style="blue")
        reference_line.append(f" ({filename})")
        references.append(reference_line)

    from rich.console import Group

    references_group = Group(*references)
    console.print(
        Panel(
            references_group,
            title=Text("References", style="yellow bold"),
            border_style="bright_black",
        )
    )

    # Format context if requested
    if context or excerpt:
        for answer_context in answer.contexts:
            # Format summary
            summary = answer_context.context
            summary_table = Table(show_header=False, box=None)
            summary_table.add_row(Text("Summary:", style="bold"), Text(summary))
            summary_table.add_row(
                Text("Score:", style="bold"), Text(str(answer_context.score))
            )
            if excerpt:
                summary_table.add_row(
                    Text("Excerpt:", style="bold"), Text(answer_context.text.text)
                )

            # Print context
            filename = Path(answer_context.text.doc.file_location).name
            ref = answer_context.text.doc.other.get(
                "ref", answer_context.text.doc.other.get("papis_id")
            )
            pages = answer_context.text.doc.pages
            title = Text()
            title.append(f"@{ref}, p. {pages}", style="blue bold")
            title.append(f" ({filename})", style="white")
            console.print(
                Panel(
                    summary_table,
                    title=Text("\n") + title,  # Add newline before the title
                    border_style="bright_black",
                )
            )


def to_json_output(answer: Any) -> str:
    """Convert the answer object to a JSON-serializable dictionary."""
    output = {
        "question": answer.question,
        "answer": answer.answer,
        "references": [
            {
                "papis_id": context.text.doc.other.get("papis_id"),
                "pages": context.text.doc.pages,
            }
            for context in answer.contexts
        ],
        "contexts": [
            {
                "papis_id": context.text.doc.other.get("papis_id"),
                "pages": context.text.doc.pages,
                "summary": context.context,
                "score": context.score,
                "excerpt": context.text.text,
            }
            for context in answer.contexts
        ],
    }
    return json.dumps(output, indent=2)


def to_markdown_output(
    answer: Any,
    context: bool = False,
    excerpt: bool = False,
) -> str:
    """Format the answer as a well-formatted markdown document."""
    answer = transform_answer(answer)

    markdown = []

    # Question section
    markdown.append("# Question\n")
    markdown.append(answer.question + "\n")

    # Answer section
    markdown.append("# Answer\n")

    # Process answer text to adjust heading levels
    answer_text = answer.answer
    lines = answer_text.split("\n")

    # First, determine if we need to adjust heading levels
    min_heading_level = float("inf")
    for line in lines:
        if line.strip().startswith("#"):
            # Count the number of # symbols at the start
            level = 0
            for char in line.strip():
                if char == "#":
                    level += 1
                else:
                    break
            min_heading_level = min(min_heading_level, level)

    # If the minimum heading level is 1, shift all headings
    if min_heading_level == 1:
        adjusted_lines = []
        for line in lines:
            if line.strip().startswith("#"):
                adjusted_lines.append("#" + line)  # Add one # to increase heading level
            else:
                adjusted_lines.append(line)
        answer_text = "\n".join(adjusted_lines)

    markdown.append(answer_text + "\n")

    # References section
    markdown.append("## References\n")
    for answer_context in answer.contexts:
        filename = Path(answer_context.text.doc.file_location).name
        ref = answer_context.text.doc.other.get(
            "ref", answer_context.text.doc.other.get("papis_id")
        )
        pages = answer_context.text.doc.pages
        markdown.append(f"- [@{ref}, p. {pages}] ({filename})")

    # Context section (only if requested)
    if context or excerpt:
        markdown.append("\n# Context\n")

        for answer_context in answer.contexts:
            # Context metadata
            filename = Path(answer_context.text.doc.file_location).name
            ref = answer_context.text.doc.other.get(
                "ref", answer_context.text.doc.other.get("papis_id")
            )
            pages = answer_context.text.doc.pages

            markdown.append(f"## @{ref}, p. {pages} ({filename})\n")

            # Summary
            markdown.append(to_latex_math(answer_context.context) + "\n")

            # Score
            markdown.append(f"**Score:** {answer_context.score}\n")

            # Excerpt (only if requested)
            if excerpt:
                markdown.append("### Excerpt\n")
                markdown.append(answer_context.text.text + "\n")

    return "\n".join(markdown)
