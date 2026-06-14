from figure_data.ai.retrieval_service import BuildRagIndexResult, SearchRagEvidenceResult


def format_build_rag_index_result(result: BuildRagIndexResult) -> list[str]:
    return [
        f"embedding_model\t{result.provider}\t{result.model_name}",
        f"rag_index\tsources_read\t{result.sources_read}",
        f"rag_index\tdocuments_indexed\t{result.documents_indexed}",
        f"rag_index\tembeddings_written\t{result.embeddings_written}",
    ]


def format_search_rag_evidence_result(result: SearchRagEvidenceResult) -> list[str]:
    lines = [
        f"rag_query\t{result.query}",
        f"embedding_model\t{result.provider}\t{result.model_name}",
    ]
    for index, item in enumerate(result.results):
        source_ref_id = "" if item.source_ref_id is None else str(item.source_ref_id)
        snippet = item.content_text.replace("\t", " ").replace("\n", " ")[:160]
        lines.append(
            "\t".join(
                [
                    "result",
                    str(index),
                    str(item.score),
                    item.source_kind,
                    source_ref_id,
                    snippet,
                ]
            )
        )
    return lines
