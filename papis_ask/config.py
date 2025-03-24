import papis.config
from papis.config import PapisConfigType

SECTION_NAME = "ask"

DEFAULTS: PapisConfigType = {
    SECTION_NAME: {
        "evidence-k": 10,
        "max-sources": 5,
        "context": True,
        "excerpt": False,
    }
}


papis.config.register_default_settings(DEFAULTS)


def create_paper_qa_settings():
    from paperqa import Settings

    settings = Settings()

    settings.llm = papis.config.getstring("llm", SECTION_NAME)
    settings.summary_llm = papis.config.getstring("summary-llm", SECTION_NAME)
    settings.embedding = papis.config.getstring("embedding", SECTION_NAME)
    settings.answer.answer_max_sources = (
        papis.config.getint("max-sources", SECTION_NAME)
        or DEFAULTS[SECTION_NAME]["max-sources"]  # TODO: redundancy
    )
    settings.answer.evidence_k = (
        papis.config.getint("evidence-k", SECTION_NAME)
        or DEFAULTS[SECTION_NAME]["evidence-k"]  # TODO: redundancy
    )
    settings.parsing.use_doc_details = False
    return settings
