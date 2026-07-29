from __future__ import annotations

import re


_MARKDOWN = re.compile(r"[*_`#>\[\]{}]")
_EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE,
)


def sanitize_for_speech(text: str) -> str:
    text = _MARKDOWN.sub("", text)
    text = _EMOJI.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"([,.;:!?])(?=\w)", r"\1 ", text)


class SpeechChunker:
    """Converte deltas do LLM em trechos curtos, sem cortar palavras."""

    def __init__(
        self,
        min_words: int = 10,
        max_words: int = 28,
        first_max_words: int = 14,
    ) -> None:
        self.min_words = min_words
        self.max_words = max_words
        self.first_max_words = first_max_words
        self._buffer = ""
        self._first_chunk = True

    def feed(self, delta: str) -> list[str]:
        self._buffer += delta
        return self._extract(force=False)

    def flush(self) -> list[str]:
        return self._extract(force=True)

    def reset(self) -> None:
        self._buffer = ""
        self._first_chunk = True

    def _extract(self, force: bool) -> list[str]:
        chunks: list[str] = []
        while self._buffer.strip():
            text = self._buffer
            words = list(re.finditer(r"\S+", text))
            if not words:
                break

            boundary: int | None = None
            for match in re.finditer(r"[.!?;:](?:\s+|$)", text):
                boundary = match.end()
                break

            if boundary is None and len(words) >= self.max_words:
                search_end = words[self.max_words - 1].end()
                # Cada chunk inicia uma síntese separada. Cortar em vírgulas ou
                # após poucas palavras cria uma pausa artificial no meio da ideia.
                boundary = search_end

            if boundary is None:
                if force:
                    boundary = len(text)
                else:
                    break

            chunk = sanitize_for_speech(text[:boundary])
            self._buffer = text[boundary:].lstrip()
            if chunk:
                chunks.append(chunk)
                self._first_chunk = False
        return chunks
