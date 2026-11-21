import json
from pathlib import Path

import pytest
from manifest import Sources, build

TASKS = """
[[task]]
id = "pub-kettle"
doc_type = "README section"
reader = "Ana"
target_words = 180
notes = "- a fact"
sources = ["[1] stub"]
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def sources(tmp_path) -> Sources:
    corpus = tmp_path / "corpus"
    pairs = []
    for pair_id, register in (("techdoc-1", "techdoc"), ("forum-1", "forum")):
        write(corpus / "human" / f"{pair_id}.txt", f"A person wrote this {register} text.")
        write(corpus / "ai" / f"{pair_id}.txt", "A model wrote this text from the brief.")
        pairs.append(
            {
                "id": pair_id,
                "register": register,
                "human": {"file": f"human/{pair_id}.txt"},
                "ai": {"file": f"ai/{pair_id}.txt"},
            }
        )
    write(corpus / "pairs.json", json.dumps({"version": 1, "pairs": pairs}))
    write(
        tmp_path / "voice" / "voice-1-pitch.md", "| a | b |\n|---|---|\n\nMy own **plain** words."
    )
    write(tmp_path / "tasks.toml", TASKS)
    write(
        tmp_path / "generation" / "pub-kettle" / "merged" / "final.md", "The kettle switches off."
    )
    write(tmp_path / "texts" / "bheijden" / "forum-1" / "no-skill.md", "Today's model, no skill.")
    write(tmp_path / "texts" / "bheijden" / "forum-1" / "no-skill.json", "{}")
    return Sources(
        bheijden_corpus=corpus,
        voice_dir=tmp_path / "voice",
        pairwise_generation=tmp_path / "generation",
        pairwise_task_files=(tmp_path / "tasks.toml", tmp_path / "absent-private-tasks.toml"),
        detector_texts=tmp_path / "texts",
    )


class TestBuild:
    def test_every_source_lands_with_its_arm_topic_register_and_words(self, sources, tmp_path):
        texts = {text.id: text for text in build(sources, repo=tmp_path)}
        assert sorted(texts) == [
            "bheijden/corpus-claude-opus-5/forum-1",
            "bheijden/corpus-claude-opus-5/techdoc-1",
            "bheijden/human/forum-1",
            "bheijden/human/techdoc-1",
            "bheijden/no-skill/forum-1",
            "human-private/human-jan/voice-1-pitch",
            "pairwise/merged/pub-kettle",
        ]
        no_skill = texts["bheijden/no-skill/forum-1"]
        assert (no_skill.arm, no_skill.topic, no_skill.register) == ("no-skill", "forum-1", "forum")
        assert no_skill.path == "texts/bheijden/forum-1/no-skill.md"
        assert texts["pairwise/merged/pub-kettle"].register == "README section"
        assert texts["bheijden/human/techdoc-1"].register == "techdoc"
        assert texts["human-private/human-jan/voice-1-pitch"].words == 4

    def test_missing_private_dirs_leave_the_public_corpus(self, sources, tmp_path):
        public_only = Sources(
            bheijden_corpus=sources.bheijden_corpus,
            voice_dir=tmp_path / "no-voice",
            pairwise_generation=tmp_path / "no-generation",
            pairwise_task_files=(tmp_path / "no-tasks.toml",),
            detector_texts=tmp_path / "no-texts",
        )
        assert {text.corpus for text in build(public_only, repo=tmp_path)} == {"bheijden"}

    def test_passage_for_an_unknown_task_is_refused(self, sources):
        write(
            sources.pairwise_generation / "pub-unknown" / "merged" / "final.md", "Orphan passage."
        )
        with pytest.raises(ValueError):
            build(sources, repo=sources.bheijden_corpus.parent)

    def test_new_text_for_an_unknown_topic_is_refused(self, sources):
        write(sources.detector_texts / "bheijden" / "nope-9" / "no-skill.md", "Orphan text.")
        with pytest.raises(ValueError):
            build(sources, repo=sources.bheijden_corpus.parent)

    def test_text_with_no_words_is_refused(self, sources):
        write(sources.voice_dir / "voice-2-table.md", "| only | a | table |\n|---|---|---|\n")
        with pytest.raises(ValueError):
            build(sources, repo=sources.bheijden_corpus.parent)
