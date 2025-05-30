import pickle
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

import papis.cli
import papis.config
from papis.config import get_lib
from papis.api import get_all_documents_in_lib
import papis.logging
from papis.utils import get_cache_home

import click
from click_default_group import DefaultGroup
import asyncio

from papis_ask.config import SECTION_NAME, create_paper_qa_settings
from papis_ask.output import (
    to_terminal_output,
    to_json_output,
    to_markdown_output,
    transform_answer,
)

logger = papis.logging.get_logger(__name__)

settings = None

FILE_ENDINGS = (".pdf", ".txt", ".html")


def remove_document_from_index(docs_index: Any, dockey: str) -> Tuple[str, str]:
    """Remove a document from the index."""
    # Get the document from the index
    doc = docs_index.docs.get(dockey)

    # Get file_location if it exists
    file_location = doc.file_location
    ref = doc.other["ref"]

    # Get docname for removal
    docname = doc.docname

    # Remove document from index
    docs_index.delete(dockey=dockey)
    docs_index.deleted_dockeys.remove(dockey)
    docs_index.docnames.remove(docname)

    return file_location, ref


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

    try:
        if docname := await docs_index.aadd(
            file_path,
            dockey=dockey,
            docname=ref,  # to give somewhat sensible docnames (we don't depend on it)
            citation=ref,  # to avoid unnecessary llm calls
            settings=settings,
        ):
            if ref := await update_index_metadata(
                file_path=file_path,
                file_last_indexed=time.time(),
                dockey=dockey,
                docname=docname,
                doc_papis=doc_papis,
                docs_index=docs_index,
                clients=clients,
                settings=settings,
            ):
                return ref
            else:
                logger.warning("Couldn't upgrade Doc to DocDetails.")
                logger.warning("Usually, this means the 'info.yaml' has faults.")

    except ValueError as e:
        if "This does not look like a text document" in str(e):
            logger.warning(f"File not recognised as text document: {file_path}")
            logger.warning("Usually, this means the file is faulty or not ocr'ed")
        else:
            # Re-raise other ValueErrors
            raise

    return None


async def update_index_metadata(
    file_path: Path,
    file_last_indexed: float,
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
        file_last_indexed=file_last_indexed,
        metadata_last_updated=time.time(),
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


def get_index_file() -> Path:
    """Get the path of the paperqa index file."""
    return Path(get_cache_home()) / "{}.qa".format(get_lib().name)


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


def determine_file_status(
    file_path: Path,
    info_yaml_path: Path,
    index_files_to_dockey: Dict[str, str],
    docs_index: Any,
) -> Tuple[bool, bool]:
    """Determine if a file needs to be re-indexed or just have its metadata updated."""
    dockey = index_files_to_dockey.get(str(file_path))

    # If file isn't in the index, it needs indexing
    if dockey is None:
        return True, False

    doc = docs_index.docs.get(dockey)
    if doc is None:
        return True, False

    # Get timestamps
    file_last_modified = get_last_modified(file_path)
    info_yaml_last_modified = (
        get_last_modified(info_yaml_path) if info_yaml_path.exists() else 0
    )

    # Get stored timestamps
    file_last_indexed = getattr(doc, "other", {}).get("file_last_indexed", 0)
    metadata_last_updated = getattr(doc, "other", {}).get("metadata_last_updated", 0)

    # Check if file content has changed since last indexing
    needs_indexing = file_last_modified > file_last_indexed

    # Check if metadata has changed since last update
    needs_metadata_update = info_yaml_last_modified > metadata_last_updated

    # If we need to re-index, we don't need to separately update metadata
    if needs_indexing:
        needs_metadata_update = False

    return needs_indexing, needs_metadata_update


@click.group("ask", cls=DefaultGroup, default="query", default_if_no_args=True)
@click.help_option("-h", "--help")
def cli():
    """Ask questions about your library."""
    pass


@cli.command("query")
@click.argument("query", type=str)
@click.help_option("--help", "-h")
@click.option(
    "--output",
    "-o",
    help="Output format.",
    type=str,
    default=lambda: papis.config.getint("output", SECTION_NAME),
)
@click.option(
    "--evidence-k",
    "-e",
    help="Number of evidence pieces to retrieve.",
    type=int,
    default=lambda: papis.config.getint("evidence-k", SECTION_NAME),
)
@click.option(
    "--max-sources",
    "-m",
    help="Maximum number of sources for an answer.",
    type=int,
    default=lambda: papis.config.getint("max-sources", SECTION_NAME),
)
@click.option(
    "--answer-length",
    "-l",
    help="Length of the answer.",
    type=str,
    default=lambda: papis.config.getstring("answer-length", SECTION_NAME),
)
@papis.cli.bool_flag(
    "--context/--no-context",
    "-c",
    help="Show context for each source.",
    default=lambda: papis.config.getboolean("context", SECTION_NAME),
)
@papis.cli.bool_flag(
    "--excerpt/--no-excerpt",
    "-x",
    help="Show context including excerpt for each source.",
    default=lambda: papis.config.getboolean("excerpt", SECTION_NAME),
)
def query_cmd(
    query: str,
    output: str,
    evidence_k: int,
    max_sources: int,
    answer_length: str,
    context: bool,
    excerpt: bool,
) -> None:
    """Ask questions about your library."""
    logger.debug(
        f"Starting 'ask' with query={query}, output={output}, evidence_k={evidence_k}, max_sources={max_sources}, answer_length={answer_length}, context={context}, excerpt={excerpt} "
    )

    settings = create_paper_qa_settings()
    settings.answer.answer_max_sources = max_sources
    settings.answer.evidence_k = evidence_k
    settings.answer.answer_length = answer_length

    if evidence_k <= max_sources:
        logger.error("evidence_k must be larger than max_source")
        return

    docs_index = get_index()

    if docs_index:
        answer = docs_index.query(query, settings=settings)
        answer = transform_answer(answer)

        if output == "json":
            output = to_json_output(answer)
            print(output)
        elif output == "markdown":
            output = to_markdown_output(answer, context, excerpt)
            print(output)
        else:
            to_terminal_output(answer, context, excerpt)

    else:
        logger.info(
            "The index is empty. Please index some files before asking question."
        )


@cli.command("index")
@papis.cli.query_argument()
@click.option(
    "--force",
    "-f",
    help="Force regeneration of the entire index.",
    is_flag=True,
    default=False,
)
def index_cmd(query: Optional[str], force: bool):
    """Update the library index."""
    logger.debug(f"Starting 'index' with query={query}, force={force}")
    asyncio.run(_index_async(query, force))


async def _index_async(query: Optional[str], force: bool) -> None:
    # importing all this here rather than globally since
    # it slows down shell autocmplete otherwise
    from papis_ask.metadata_provider import PapisProvider
    from paperqa.clients import DocMetadataClient

    from paperqa.clients.semantic_scholar import SemanticScholarProvider
    from paperqa.clients.journal_quality import JournalQualityPostProcessor
    from paperqa.types import DocDetails

    settings = create_paper_qa_settings()

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

    files_to_index: Set[Tuple[Path, str]] = set()
    files_to_update_metadata: Set[Tuple[Path, str]] = set()
    files_to_delete: Set[Path] = set()

    # Track existing files to later determine which ones to delete
    files_on_disk: Set[Path] = set()

    # Create a mapping of filenames to dockeys
    index_files_to_dockey: Dict[str, str] = {}
    for dockey, doc in docs_index.docs.items():
        if type(doc) is DocDetails and hasattr(doc, "file_location"):
            index_files_to_dockey[str(doc["file_location"])] = dockey

    # check all files in the library
    for papis_id, doc_papis in papis_id_to_doc.items():
        info_yaml_path = Path(doc_papis.get_info_file())

        # Figure out what documents need to be indexed
        for file_path in doc_papis.get_files():
            file_path = Path(file_path)
            file_ending = file_path.suffix
            if file_ending in FILE_ENDINGS:
                files_on_disk.add(file_path)

                # Skip processing if force is enabled (everything will be re-indexed)
                if force:
                    files_to_index.add((file_path, papis_id))
                    continue

                # Use the function to determine file status
                needs_indexing, needs_metadata_update = determine_file_status(
                    file_path, info_yaml_path, index_files_to_dockey, docs_index
                )

                if needs_indexing:
                    logger.debug(f"File {file_path} needs to be indexed")
                    files_to_index.add((file_path, papis_id))
                elif needs_metadata_update:
                    logger.debug(f"File {file_path} needs metadata update")
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
    logger.info(f"{len(files_to_delete)} file(s) will be removed from the index")

    unchanged_files = max(
        0,
        (
            len(index_files_to_dockey)
            - len(files_to_update_metadata)
            - len(files_to_index)
            - len(files_to_delete)
        ),
    )
    logger.info(f"{unchanged_files} file(s) will remain unchanged")

    # Find files to be deleted because they don't exist on disk anymore
    dockeys_to_delete_bc_missing: list[str] = [
        index_files_to_dockey[str(file)] for file in files_to_delete
    ]

    # find files to be deleted because they changed and will be replaced with new ones
    dockeys_to_delete_bc_updated: list[str] = [
        index_files_to_dockey[str(file)]
        for file, _ in files_to_index
        if str(file) in index_files_to_dockey
    ]

    # Delete files that have been updated (to avoid having duplicates of same file with different hashes)
    for dockey in dockeys_to_delete_bc_updated:
        remove_document_from_index(docs_index, dockey)

    # Delete files that have been deleted
    counter = 0
    total_files = len(dockeys_to_delete_bc_missing)
    for dockey in dockeys_to_delete_bc_missing:
        counter += 1
        file_location, ref = remove_document_from_index(docs_index, dockey)
        if file_location:
            logger.info(
                "%d/%d: Removed %s (%s)",
                counter,
                total_files,
                ref,
                file_location,
            )

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

    # update metadata for papis documents that have changed
    counter = 0
    total_files = len(files_to_update_metadata)
    for file_path, papis_id in files_to_update_metadata:
        counter += 1

        doc_papis = papis_id_to_doc[papis_id]
        dockey = index_files_to_dockey.get(str(file_path))
        doc_index = docname = docs_index.docs[dockey]
        docname = doc_index.docname
        if type(doc_index) is DocDetails:
            file_last_indexed = docs_index.docs[dockey].other["file_last_indexed"]  # type: ignore (they should all be DocDetails)

            if not dockey:
                logger.warning(
                    "File %s is not in the index, skipping metadata update",
                    file_path,
                )
                continue
            if ref := await update_index_metadata(
                file_path=file_path,
                file_last_indexed=file_last_indexed,
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
        else:
            logger.warning(f"Skipped {file_path} because it is not a DocDetails object")

    save_index(docs_index)
