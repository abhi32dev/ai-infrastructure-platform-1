# Retrieval-Augmented Generation

A production RAG pipeline includes ingestion, normalization, chunking, embedding, indexing, retrieval, context assembly, and grounded generation. Retrieval quality and generation quality must be evaluated separately because a fluent answer cannot repair missing evidence.

Hybrid retrieval combines lexical matching, such as BM25, with dense-vector similarity. Lexical search preserves exact identifiers and technical terms; dense retrieval can find conceptually related language. Score normalization or rank fusion is needed because the two scoring systems have different ranges. A reranker can improve precision after initial retrieval at additional latency and cost.

Chunk size changes the recall and context tradeoff. Small chunks are precise but may lose surrounding meaning. Large chunks preserve context but consume more tokens and can bury relevant evidence. Production experiments therefore measure retrieval recall, answer groundedness, citation validity, latency, and cost together.

