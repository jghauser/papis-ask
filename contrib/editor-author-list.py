#!/usr/bin/env python3

import papis.api
import papis.document


def main():
    # Get all documents from the library
    documents = papis.api.get_all_documents_in_lib()

    print(f"Found {len(documents)} documents in the library")

    # Filter documents with 'editor' but without 'editor_list'
    matching_docs = [
        doc for doc in documents if "editor" in doc and "editor_list" not in doc
    ]

    print(f"Found {len(matching_docs)} documents with 'editor' but no 'editor_list'")

    # Process each matching document
    for doc in matching_docs:
        # Create editor_list in the same way author_list is created
        doc["editor_list"] = papis.document.split_authors_name(doc["editor"])

        # Save the updated document
        doc.save()

        print(
            f"Updated document: {doc['title'] if 'title' in doc else 'Unknown title'}"
        )

    # Filter documents with 'author' but without 'author_list'
    matching_docs = [
        doc for doc in documents if "author" in doc and "author_list" not in doc
    ]

    print(f"Found {len(matching_docs)} documents with 'author' but no 'author_list'")

    # Process each matching document
    for doc in matching_docs:
        # Create author_list in the same way author_list is created
        doc["author_list"] = papis.document.split_authors_name(doc["author"])

        # Save the updated document
        doc.save()

        print(
            f"Updated document: {doc['title'] if 'title' in doc else 'Unknown title'}"
        )

    print("Done!")


if __name__ == "__main__":
    main()
