import pickle
import os
import re
import json
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

import papis.cli
import papis.config
from papis.api import get_all_documents_in_lib
import papis.logging
from papis.utils import get_cache_home

import click
from click_default_group import DefaultGroup
import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

logger = papis.logging.get_logger(__name__)

settings = None

FILE_ENDINGS = (".pdf", ".txt", ".html")


def remove_document_from_index(docs_index: Any, dockey: str) -> Optional[str]:
    """Remove a document from the index."""
    # Get the document from the index
    doc = docs_index.docs.get(dockey)
    if not doc:
        logger.warning(f"Document {dockey} not found in index")
        return None

    # Get file_location if it exists
    file_location = getattr(doc, "file_location", None)

    # Get docname for removal
    docname = doc.docname

    # Remove document from index
    docs_index.delete(dockey=dockey)
    docs_index.deleted_dockeys.remove(dockey)
    docs_index.docnames.remove(docname)

    return file_location


def convert_answer_to_json(answer: Any) -> Dict[str, Any]:
    """Convert the answer object to a JSON-serializable dictionary."""
    return {
        "question": answer.question,
        "answer": answer.answer,
        "references": [context.text.name for context in answer.contexts],
        "contexts": [
            {
                "name": context.text.name,
                "pages": context.text.pages,
                "summary": to_latex_math(context.context),
                "score": context.score,
                "excerpt": context.text.text,
            }
            for context in answer.contexts
        ],
    }


async def add_file_to_index(
    file_path: Path,
    doc_papis: Dict[str, Any],
    docs_index: Any,
    clients: Any,
    settings: Any,
) -> Optional[str]:
    """Add a file to the paperqa index."""
    from paperqa.utils import md5sum

    dockey = md5sum(file_path)

    ref, _, _ = extract_doc_papis_metadata(doc_papis)

    if docname := await docs_index.aadd(
        file_path,
        dockey=dockey,
        docname=ref,  # to give somewhat sensible docnames (we don't depend on it)
        citation=ref,  # to avoid unnecessary llm calls
        settings=settings,
    ):
        if ref := await update_index_metadata(
            file_path=file_path,
            dockey=dockey,
            docname=docname,
            doc_papis=doc_papis,
            docs_index=docs_index,
            clients=clients,
            settings=settings,
        ):
            return ref


async def update_index_metadata(
    file_path: Path,
    dockey: str,
    docname: str,
    doc_papis: Dict[str, Any],
    docs_index: Any,
    clients: Any,
    settings: Any,
) -> Optional[str]:
    """Update metadata for a file in the paperqa index."""
    # Extract metadata from Papis document
    ref, papis_id, _ = extract_doc_papis_metadata(doc_papis)

    # Fetch document details from metadata client
    if doc_details := await clients["papis"].query(
        settings=settings,
        papis_id=papis_id,
        file_location=str(file_path),
    ):
        query_args = {
            "settings": settings,
            # we don't need the doi, title, and authors but they are needed
            # for semantic scholar search
            "fields": [
                "citation_count",
                "source_quality",
                "is_retracted",
                "doi",
                "title",
                "authors",
            ],
            **{
                key: value
                for key, value in {
                    # we can do this being sure that the fields exist as PapisProvider
                    # assigns `None` if a value doesn't exist
                    "title": doc_details["title"],
                    "doi": doc_details["doi"],
                    "authors": doc_details["authors"],
                    "journal": doc_details["journal"],
                }.items()
                if value is not None
            },
        }
        if other_details := await clients["other"].query(**query_args):
            doc_details = other_details + doc_details
        doc_details.fields_to_overwrite_from_metadata = {
            "citation"
        }  # Restrict what can be overwritten, needed for below
        doc_details.doc_id = dockey
        doc_details.dockey = dockey
        doc_details.docname = docname
        doc_details.key = docname

        # Overwrite the Doc with a DocDetails
        docs_index.docs[dockey] = doc_details

        # Update doc reference in all Text objects that point to this document
        for text in docs_index.texts:
            if text.doc.dockey == dockey:
                text.doc = doc_details

        # Save the updated index
        save_index(docs_index)
        return ref


def transform_answer(answer: Any) -> Any:
    """Transform the answer to format references correctly using Papis references."""
    # Create a mapping of document names to references
    docname_to_ref = {}

    # First pass: collect all document names and their references
    for context in answer.contexts:
        ref = context.text.doc.other.get("ref", context.text.doc.other.get("papis_id"))
        ref = f"@{ref}"
        context.text.doc.pages = context.text.name.split()[2]
        docname_to_ref[context.text.name.split()[0]] = ref

    # Replace references in the answer text
    # Pattern: (docname pages X-N) -> [@ref, p. X-N]
    def replace_citation(match):
        docname = match.group(1)
        pages = match.group(2)

        ref = docname_to_ref.get(docname, docname)
        # Format pages as p. X-N
        formatted_pages = f"p. {pages}" if pages else ""

        if formatted_pages:
            return f"[{ref}, {formatted_pages}]"
        else:
            return f"[{ref}]"

    # Pattern to match citations like (@docname pages X-N)
    citation_pattern = r"\(([^)\s]+?)(?:\s+pages\s+([^)]+))?\)"
    answer.answer = re.sub(citation_pattern, replace_citation, answer.answer)

    return answer


def format_answer(
    answer: Any,
    context: bool,
    excerpt: bool,
) -> None:
    """Format and print the answer with optional context and excerpts."""
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
            summary = to_latex_math(answer_context.context)
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


def get_settings():
    from paperqa import Settings

    settings = Settings()

    llm = papis.config.get("ask-llm")
    if llm:
        settings.llm = llm
    summary_llm = papis.config.get("ask-summary-llm")
    if summary_llm:
        settings.summary_llm = summary_llm
    embedding = papis.config.get("ask-embedding")
    if embedding:
        settings.embedding = embedding
    settings.parsing.use_doc_details = False
    return settings


def to_latex_math(text: str) -> str:
    return (
        text.replace(r"\(", "$")
        .replace(r"\)", "$")
        .replace(r"\[", "$$")
        .replace(r"\]", "$$")
    )


def get_index_file() -> Path:
    """Get the path of the paperqa index file."""
    return Path(get_cache_home()) / "{}.qa".format(papis.config.get_lib().name)


def get_last_modified(file_path: Path) -> float:
    """Get the last modified time of a file."""
    return os.path.getmtime(file_path)


# NOTE: no types because we'd have to globally import Docs
def get_index():
    """Load the paperqa index from disk."""
    file = get_index_file()
    try:
        if file.exists():
            with open(file, "rb") as f:
                return pickle.load(f)
        return None
    except (OSError, pickle.PickleError) as e:
        logger.error(f"Failed to load index: {e}")
        raise


# NOTE: no types because we'd have to globally import Docs
def save_index(docs):
    """Save the paperqa index to disk."""
    try:
        with open(get_index_file(), "wb") as f:
            pickle.dump(docs, f)
    except OSError as e:
        logger.error(f"Failed to save index: {e}")
        raise


def extract_doc_papis_metadata(
    doc_papis,
) -> tuple[str, str, Optional[str]]:
    """Extract standard metadata from a papis document."""
    ref: str = doc_papis.get("ref") or ""
    papis_id: str = doc_papis.get("papis_id")
    # fallback ref based on papis_id
    if ref.strip() == "":
        ref = papis_id
    ref = f"@{ref}"

    doi: Optional[str] = doc_papis.get("doi")

    return ref, papis_id, doi


def needs_indexing(
    file_path: Path, index_files_to_dockey: Dict[str, str], prev_index_time: float
) -> bool:
    """Determine if a file needs to be indexed based on presence in index and modification time."""
    # Check if file exists in the index
    if str(file_path) not in index_files_to_dockey:
        # File not in index, needs indexing
        return True

    # File exists in index, check if it's been modified since it was indexed
    file_last_modified = get_last_modified(file_path)

    return file_last_modified > prev_index_time


@click.group("ask", cls=DefaultGroup, default="query", default_if_no_args=True)
@click.help_option("-h", "--help")
def cli():
    """Ask questions about your library"""
    pass


@cli.command("query")
@click.argument("query", type=str)
@click.help_option("--help", "-h")
@papis.cli.bool_flag("--to-json", "-j", help="Json output", type=bool, default=False)
@click.option(
    "--evidence-k",
    "-e",
    help="Number of evidence pieces to retrieve",
    type=int,
    default=10,
)
@click.option(
    "--max-sources",
    "-m",
    help="Max number of sources for an answer",
    type=int,
    default=5,
)
@click.option(
    "--context",
    "-c",
    help="Show context for each source",
    type=bool,
    default=False,
    is_flag=True,
)
@click.option(
    "--excerpt",
    "-x",
    help="Show context including excerpt for each source",
    type=bool,
    default=False,
    is_flag=True,
)
def query_cmd(
    query: str,
    to_json: bool,
    evidence_k: int,
    max_sources: int,
    context: bool,
    excerpt: bool,
) -> None:
    """Ask questions about your library"""
    logger.debug(
        f"Starting 'ask' with query={query}, to_json={to_json}, evidence_k={evidence_k}, max_sources={max_sources}, context={context}, excerpt={excerpt} "
    )

    settings = get_settings()

    if evidence_k <= max_sources:
        logger.error("evidence_k must be larger than max_source")
        return

    settings.answer.answer_max_sources = max_sources
    settings.answer.evidence_k = evidence_k

    docs_index = get_index()

    if docs_index:
        answer = docs_index.query(query, settings=settings)
        answer = transform_answer(answer)
        answer.answer = to_latex_math(answer.answer)

        if to_json:
            output = convert_answer_to_json(answer)
            print(json.dumps(output, indent=2))
        else:
            format_answer(answer, context, excerpt)

    else:
        logger.info(
            "The index is empty. Please index some files before asking question."
        )


@cli.command("index")
@papis.cli.query_argument()
@click.option(
    "--force",
    "-f",
    help="Force regeneration of the entire index",
    is_flag=True,
    default=False,
)
def index_cmd(query: Optional[str], force: bool):
    """Update the library index"""
    logger.debug(f"Starting 'index' with query={query}, force={force}")
    asyncio.run(_index_async(query, force))


async def _index_async(query: Optional[str], force: bool) -> None:
    # importing all this here rather than globally since
    # it slows down shell autocmplete otherwise
    from papis_ask.metadata_provider import PapisProvider
    from paperqa.clients import DocMetadataClient

    from paperqa.clients.semantic_scholar import SemanticScholarProvider
    from paperqa.clients.journal_quality import JournalQualityPostProcessor

    settings = get_settings()

    docs_index = get_index()
    if docs_index is None or force:
        from paperqa import Docs

        logger.debug("Creating new empty Docs instance")
        docs_index = Docs()

    logger.debug(f"The paper-qa index contains {len(docs_index.docs)} document(s)")

    if query:
        docs_papis = papis.cli.handle_doc_folder_or_query(query, None)
    else:
        docs_papis = get_all_documents_in_lib()

    logger.debug(f"The Papis library contains {len(docs_papis)} document(s)")

    # Configure PapisProvider with the documents dictionary
    papis_id_to_doc = {doc["papis_id"]: doc for doc in docs_papis}
    PapisProvider.configure(docs_by_id=papis_id_to_doc)

    clients = {
        "papis": DocMetadataClient(
            clients={
                PapisProvider,
                JournalQualityPostProcessor,
            }
        ),
        "other": DocMetadataClient(
            clients={
                SemanticScholarProvider,
            }
        ),
    }

    prev_index_time = (
        get_last_modified(get_index_file())
        if get_index_file().exists() and not force
        else 0
    )

    files_to_index: Set[Tuple[Path, str]] = set()
    files_to_update_metadata: Set[Tuple[Path, str]] = set()
    files_to_delete: Set[Path] = set()

    # Track existing files to later determine which ones to delete
    files_on_disk: Set[Path] = set()

    # Create a mapping of filenames to dockeys
    index_files_to_dockey: Dict[str, str] = {}
    malformed_dockeys: Set[str] = set()
    for dockey, doc in docs_index.docs.items():
        file_location = getattr(doc, "file_location", None)
        if file_location is None:
            malformed_dockeys.add(dockey)
        else:
            index_files_to_dockey[file_location] = dockey

    # sometimes files get added but not properly, we remove them
    # TODO: we should catch this by deleting docs when upgrading
    #       to docdetails fails
    for dockey in malformed_dockeys:
        remove_document_from_index(docs_index, dockey)
        logger.warning(
            f"Removing document '{dockey}' from index because it's missing 'file_location'"
        )

    # check all files in the library
    for papis_id, doc_papis in papis_id_to_doc.items():
        info_yaml_path = Path(doc_papis.get_info_file())

        # Figure out what documents need to be indexed
        for file_path in doc_papis.get_files():
            file_path = Path(file_path)
            file_ending = file_path.suffix
            if file_ending in FILE_ENDINGS:
                files_on_disk.add(file_path)

                # Use the function to check if we need to index this file
                if needs_indexing(file_path, index_files_to_dockey, prev_index_time):
                    logger.debug(f"File {file_path} needs to be indexed")
                    files_to_index.add((file_path, papis_id))

            # Figure out which documents need to have metadata updated
            if info_yaml_path.exists():
                # Either check if metadata in index is outdated or simply use timestamp logic
                info_yaml_last_modified = get_last_modified(info_yaml_path)
                if info_yaml_last_modified > prev_index_time:
                    files_to_update_metadata.add((file_path, papis_id))

    logger.info(f"{len(files_to_index)} file(s) will be indexed")

    # Removing all files needing to be indexed from those that need metadata updated
    files_to_update_metadata -= files_to_index
    logger.info(
        f"{len(files_to_update_metadata)} file(s) will have their metadata updated"
    )

    # Figure out which documents need to be deleted
    files_to_delete = {
        Path(file) for file in index_files_to_dockey.keys()
    } - files_on_disk
    logger.info(f"{len(files_to_delete)} file(s) will be deleted from the index")

    # Find files to be deleted because they don't exist on disk anymore
    dockeys_to_delete_bc_missing: Set[str] = {
        index_files_to_dockey[str(file)] for file in files_to_delete
    }

    # find files to be deleted because they changed and will be replaced with new ones
    dockeys_to_delete_bc_updated: Set[str] = {
        index_files_to_dockey[str(file)]
        for file, _ in files_to_index
        if str(file) in index_files_to_dockey
    }

    # Delete files that have been updated (to avoid having duplicates of same file with different hashes)
    for dockey in dockeys_to_delete_bc_updated:
        remove_document_from_index(docs_index, dockey)

    # Delete files that have been deleted
    counter = 0
    total_files = len(dockeys_to_delete_bc_missing)
    for dockey in dockeys_to_delete_bc_missing:
        file_location = remove_document_from_index(docs_index, dockey)
        if file_location:
            logger.info("Removing from index: %s", file_location)

    # index all new files or changed files
    counter = 0
    total_files = len(files_to_index)
    for file_path, papis_id in files_to_index:
        counter += 1

        doc_papis = papis_id_to_doc[papis_id]

        if ref := await add_file_to_index(
            file_path=file_path,
            doc_papis=doc_papis,
            docs_index=docs_index,
            clients=clients,
            settings=settings,
        ):
            logger.info(
                "%d/%d: Indexed %s (%s)",
                counter,
                total_files,
                ref,
                file_path.name,
            )
        else:
            logger.warning("Failed to index file: %s", file_path)

    counter = 0
    total_files = len(files_to_update_metadata)
    # update metadata for papis documents that have changed
    for file_path, papis_id in files_to_update_metadata:
        counter += 1

        doc_papis = papis_id_to_doc[papis_id]
        dockey = index_files_to_dockey.get(str(file_path))
        docname = docs_index.docs[dockey].docname

        if not dockey:
            logger.warning(
                "File %s is not in the index, skipping metadata update",
                file_path,
            )
            continue
        if ref := await update_index_metadata(
            file_path=file_path,
            doc_papis=doc_papis,
            docs_index=docs_index,
            dockey=dockey,
            docname=docname,
            clients=clients,
            settings=settings,
        ):
            logger.info(
                "%d/%d: Updated metadata for %s (%s)",
                counter,
                total_files,
                ref,
                file_path.name,
            )
        else:
            logger.warning("Failed to update metadata for file: %s", file_path)

    save_index(docs_index)
