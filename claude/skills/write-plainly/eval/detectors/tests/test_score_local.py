from score_local import gpttrace_normalize


class TestGpttraceNormalize:
    def test_drops_variation_selectors_in_text_with_no_lookalikes(self):
        assert gpttrace_normalize("a heart \u2764\ufe0f here") == "a heart \u2764 here"

    def test_folds_lookalike_letters_in_latin_text_and_leaves_greek_words(self):
        assert gpttrace_normalize("p\u0430ssword and \u03bb\u03cc\u03b3\u03bf\u03c2") == (
            "password and \u03bb\u03cc\u03b3\u03bf\u03c2"
        )
