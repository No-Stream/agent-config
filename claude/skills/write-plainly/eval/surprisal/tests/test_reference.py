import pytest

from reference import clean_row, sample_paragraphs, wikitext_articles

ROWS = [
    "",
    " = Harbour Seal = \n",
    "",
    " The harbour seal is a true seal found along temperate coasts . \n",
    " It hauls out on rocky shores , sand @-@ bars and ice floes ; adults weigh 55 @.@ 5 kg . \n",
    "",
    " = = Behaviour = = \n",
    "",
    " Seals do n't migrate far , and a pup 's first swim comes within hours of birth . \n",
    "",
    " = Basalt = \n",
    "",
    " Basalt is a fine @-@ grained volcanic rock that covers 1 @,@ 000 km2 here . \n",
]


class TestWikitextArticles:
    def test_splits_articles_at_titles_drops_headings_and_undoes_markers(self):
        articles = list(wikitext_articles(ROWS))
        assert articles == [
            [
                "The harbour seal is a true seal found along temperate coasts.",
                "It hauls out on rocky shores, sand-bars and ice floes; adults weigh 55.5 kg.",
                "Seals don't migrate far, and a pup's first swim comes within hours of birth.",
            ],
            ["Basalt is a fine-grained volcanic rock that covers 1,000 km2 here."],
        ]


class TestCleanRow:
    def test_closes_the_space_before_closing_punctuation(self):
        row = " The pass ( 2 @,@ 100 m ) is open : walkers cross it , and why not ? \n"
        assert clean_row(row) == "The pass ( 2,100 m) is open: walkers cross it, and why not?"

    def test_keeps_the_space_before_a_word_that_starts_with_a_period(self):
        row = " The team ported the .NET runtime and batted .263 that year . \n"
        assert clean_row(row) == "The team ported the .NET runtime and batted .263 that year."


class TestSampleParagraphs:
    def test_draws_whole_paragraphs_from_every_article_until_the_word_target(self):
        articles = [
            [f"article{index} paragraph{number} " * 5 for number in range(4)] for index in range(6)
        ]
        sample = sample_paragraphs(articles, words=100, seed=7)
        assert len(sample) == 10
        assert len({paragraph.split()[0] for paragraph in sample}) > 1
        assert sample == sample_paragraphs(articles, words=100, seed=7)
        assert sample != sample_paragraphs(articles, words=100, seed=8)

    def test_too_few_words_is_an_error(self):
        with pytest.raises(ValueError):
            sample_paragraphs([["a short article"]], words=100, seed=7)
