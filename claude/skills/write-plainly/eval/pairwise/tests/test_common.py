from common import word_count


class TestWordCount:
    def test_contractions_decimals_and_hyphenated_words_count_once(self) -> None:
        assert word_count("The model's error fell 3.5% — a well-known drop.") == 8
