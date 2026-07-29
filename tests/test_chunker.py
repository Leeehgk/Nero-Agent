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


def test_first_chunk_is_not_cut_after_only_six_words() -> None:
    chunker = SpeechChunker(min_words=10, max_words=18, first_max_words=6)
    assert chunker.feed("um dois três quatro cinco seis sete") == []


def test_short_interjection_waits_for_sentence_end() -> None:
    chunker = SpeechChunker(min_words=10, max_words=18, first_max_words=6)
    assert chunker.feed("Claro, estou te ouvindo. ") == [
        "Claro, estou te ouvindo."
    ]


def test_comma_does_not_split_synthesis() -> None:
    chunker = SpeechChunker(max_words=18)
    assert chunker.feed("Claro, posso explicar isso com calma") == []
    assert chunker.feed(" e sem pausas artificiais.") == [
        "Claro, posso explicar isso com calma e sem pausas artificiais."
    ]


def test_sanitizer_normalizes_punctuation_spacing() -> None:
    assert sanitize_for_speech("Olá,mundo ! Tudo bem?Sim.") == (
        "Olá, mundo! Tudo bem? Sim."
    )
