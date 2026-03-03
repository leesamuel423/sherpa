import json

from sherpa.context import RetrievedContext
from sherpa.schema import RetrievedSource

MOCK_WIKI_TEXT = (
    "Quantum computing is a type of computation whose operations can harness "
    "the phenomena of quantum mechanics, such as superposition, interference, "
    "and entanglement. Devices that perform quantum computations are known as "
    "quantum computers. Though current quantum computers may be too small to "
    "outperform usual (classical) computers for practical applications, larger "
    "realizations are believed to be capable of solving certain computational "
    "problems, such as integer factorization, substantially faster than "
    "classical computers."
)

MOCK_ARXIV_TEXT = (
    "We present a comprehensive review of quantum error correction codes "
    "and fault-tolerant quantum computation. Quantum error correction is "
    "essential for building reliable quantum computers, as quantum bits are "
    "inherently fragile and susceptible to decoherence."
)

MOCK_CONTEXT = RetrievedContext(
    sources={
        "wikipedia": [
            RetrievedSource(
                source_type="wikipedia",
                title="Quantum computing",
                url="https://en.wikipedia.org/wiki/Quantum_computing",
                text=MOCK_WIKI_TEXT,
            )
        ],
        "arxiv": [
            RetrievedSource(
                source_type="arxiv",
                title="Quantum Error Correction Review",
                url="http://arxiv.org/abs/2401.00001",
                text=MOCK_ARXIV_TEXT,
            )
        ],
    },
    display_names={
        "wikipedia": "Wikipedia",
        "arxiv": "arXiv",
    },
)

WIKI_ONLY_CONTEXT = RetrievedContext(
    sources={
        "wikipedia": MOCK_CONTEXT.sources["wikipedia"],
        "arxiv": [],
    },
    display_names={
        "wikipedia": "Wikipedia",
        "arxiv": "arXiv",
    },
)

_GOOD_OUTPUT = {
    "query": "quantum computing",
    "summary": "Quantum computing harnesses quantum mechanical phenomena for computation.",
    "findings": [
        {
            "claim": "Quantum computers harness phenomena like superposition and entanglement.",
            "supporting_sources": [
                {
                    "source_type": "wikipedia",
                    "title": "Quantum computing",
                    "url": "https://en.wikipedia.org/wiki/Quantum_computing",
                    "retrieved_snippet": "Quantum computing is a type of computation whose operations can harness the phenomena of quantum mechanics, such as superposition, interference, and entanglement.",
                }
            ],
            "confidence": 0.95,
        },
        {
            "claim": "Quantum error correction is essential for reliable quantum computers.",
            "supporting_sources": [
                {
                    "source_type": "arxiv",
                    "title": "Quantum Error Correction Review",
                    "url": "http://arxiv.org/abs/2401.00001",
                    "retrieved_snippet": "Quantum error correction is essential for building reliable quantum computers, as quantum bits are inherently fragile and susceptible to decoherence.",
                }
            ],
            "confidence": 0.9,
        },
    ],
    "sources_consulted": [
        {
            "source_type": "wikipedia",
            "title": "Quantum computing",
            "url": "https://en.wikipedia.org/wiki/Quantum_computing",
            "retrieved_snippet": "Quantum computing is a type of computation whose operations can harness the phenomena of quantum mechanics",
        },
        {
            "source_type": "arxiv",
            "title": "Quantum Error Correction Review",
            "url": "http://arxiv.org/abs/2401.00001",
            "retrieved_snippet": "We present a comprehensive review of quantum error correction codes",
        },
    ],
    "audit": {
        "passed": True,
        "attempts": 1,
        "errors": [],
        "wall_clock_seconds": 2.5,
    },
}

GOOD_JSON = json.dumps(_GOOD_OUTPUT)

BAD_SCHEMA_JSON = json.dumps({"query": "test"})

_BAD_GROUNDING_OUTPUT = {
    "query": "quantum computing",
    "summary": "Quantum computing summary.",
    "findings": [
        {
            "claim": "Quantum computers are very fast.",
            "supporting_sources": [
                {
                    "source_type": "wikipedia",
                    "title": "Quantum computing",
                    "url": "https://en.wikipedia.org/wiki/Quantum_computing",
                    "retrieved_snippet": "This snippet was completely fabricated and does not exist anywhere in the retrieved context at all.",
                }
            ],
            "confidence": 0.8,
        }
    ],
    "sources_consulted": [
        {
            "source_type": "wikipedia",
            "title": "Quantum computing",
            "url": "https://en.wikipedia.org/wiki/Quantum_computing",
            "retrieved_snippet": "Also fabricated snippet here.",
        }
    ],
    "audit": {
        "passed": True,
        "attempts": 1,
        "errors": [],
        "wall_clock_seconds": 1.0,
    },
}

BAD_GROUNDING_JSON = json.dumps(_BAD_GROUNDING_OUTPUT)

_DUPLICATE_FINDINGS_OUTPUT = {
    "query": "quantum computing",
    "summary": "Quantum computing summary.",
    "findings": [
        {
            "claim": "Quantum computing uses superposition.",
            "supporting_sources": [
                {
                    "source_type": "wikipedia",
                    "title": "Quantum computing",
                    "url": "https://en.wikipedia.org/wiki/Quantum_computing",
                    "retrieved_snippet": "Quantum computing is a type of computation whose operations can harness the phenomena of quantum mechanics, such as superposition",
                }
            ],
            "confidence": 0.9,
        },
        {
            "claim": "Quantum computing uses superposition.",
            "supporting_sources": [
                {
                    "source_type": "wikipedia",
                    "title": "Quantum computing",
                    "url": "https://en.wikipedia.org/wiki/Quantum_computing",
                    "retrieved_snippet": "Quantum computing is a type of computation whose operations can harness the phenomena of quantum mechanics, such as superposition",
                }
            ],
            "confidence": 0.85,
        },
    ],
    "sources_consulted": [
        {
            "source_type": "wikipedia",
            "title": "Quantum computing",
            "url": "https://en.wikipedia.org/wiki/Quantum_computing",
            "retrieved_snippet": "Quantum computing is a type of computation whose operations can harness the phenomena of quantum mechanics",
        }
    ],
    "audit": {
        "passed": True,
        "attempts": 1,
        "errors": [],
        "wall_clock_seconds": 1.0,
    },
}

DUPLICATE_FINDINGS_JSON = json.dumps(_DUPLICATE_FINDINGS_OUTPUT)

_BAD_GROUNDING_AND_DUPLICATE_OUTPUT = {
    "query": "quantum computing",
    "summary": "Quantum computing summary.",
    "findings": [
        {
            "claim": "Quantum computing uses superposition.",
            "supporting_sources": [
                {
                    "source_type": "wikipedia",
                    "title": "Quantum computing",
                    "url": "https://en.wikipedia.org/wiki/Quantum_computing",
                    "retrieved_snippet": "This snippet is completely fabricated and not in the context.",
                }
            ],
            "confidence": 0.9,
        },
        {
            "claim": "Quantum computing uses superposition.",
            "supporting_sources": [
                {
                    "source_type": "wikipedia",
                    "title": "Quantum computing",
                    "url": "https://en.wikipedia.org/wiki/Quantum_computing",
                    "retrieved_snippet": "Also fabricated and not present at all.",
                }
            ],
            "confidence": 0.85,
        },
    ],
    "sources_consulted": [
        {
            "source_type": "wikipedia",
            "title": "Quantum computing",
            "url": "https://en.wikipedia.org/wiki/Quantum_computing",
            "retrieved_snippet": "Quantum computing is a type of computation whose operations can harness the phenomena of quantum mechanics",
        }
    ],
    "audit": {
        "passed": True,
        "attempts": 1,
        "errors": [],
        "wall_clock_seconds": 1.0,
    },
}

BAD_GROUNDING_AND_DUPLICATE_JSON = json.dumps(_BAD_GROUNDING_AND_DUPLICATE_OUTPUT)
