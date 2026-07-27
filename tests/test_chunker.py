from nero.chunker import SpeechChunker, sanitize_for_speech


def test_chunker_waits_for_useful_phrase() -> None:
    chunker = SpeechChunker(min_words=5, max_words=8)
    assert chunker.feed("Essa é uma resposta ") == []
    assert chunker.feed("curta e natural.") == [
        "Essa é uma resposta curta e natural."
    ]


def test_chunker_emits_short_sentence() -> None:
    chunker = SpeechChunker()
    assert chunker.feed("Com certeza.") == ["Com certeza."]
    assert chunker.flush() == []


def test_sanitizer_removes_markdown_and_emoji() -> None:
    assert sanitize_for_speech("**Olá** 👋 `mundo`") == "Olá mundo"


def test_first_short_sentence_is_emitted_immediately() -> None:
    chunker = SpeechChunker(min_words=10, max_words=18, first_max_words=6)
    assert chunker.feed("Tudo certo por aqui. ") == ["Tudo certo por aqui."]


def test_first_chunk_is_bounded_without_punctuation() -> None:
    chunker = SpeechChunker(min_words=10, max_words=18, first_max_words=6)
    assert chunker.feed("um dois três quatro cinco seis sete") == [
        "um dois três quatro cinco seis"
    ]


def test_short_interjection_waits_for_sentence_end() -> None:
    chunker = SpeechChunker(min_words=10, max_words=18, first_max_words=6)
    assert chunker.feed("Claro, estou te ouvindo. ") == [
        "Claro, estou te ouvindo."
    ]
