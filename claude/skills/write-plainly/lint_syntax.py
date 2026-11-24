#!/usr/bin/env -S uv run --upgrade --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["nltk", "spacy", "spacy-curated-transformers", "torch"]
#
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
#
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# ///
"""Find sentence structures that spaCy's parse can see and a pattern cannot, in prose.

check-prose.sh runs this as a uv script, whose header above declares spaCy, its transformer
support, CPU-only torch and NLTK, which reads the newest Open English WordNet to tell a person
from a thing. syntax_features.py documents the parse, and eval/README.md the measurement behind
the rules and the rules that were tried and dropped.
"""

from __future__ import annotations

import argparse
import fcntl
import functools
import re
import warnings
from collections.abc import Sequence
from pathlib import Path

import nltk
from nltk.corpus.reader.wordnet import Synset, WordNetCorpusReader
from spacy.language import Language

from lint_prose_markdown import Finding, excerpt, write_findings
from lint_prose_patterns import PHRASE_RULES, QUOTATION
from syntax_features import InanimateSubject, Sentence, Span, analyze_texts, cache_dir, load_model

DROPPED_RELATIVIZER_SUBJECT_WORDS = 2
# Readers found "that" no help after these ("anything one survey can show").
INDEFINITE_PRONOUNS = {"anything", "everything", "nothing", "something", "anyone", "everyone"}
INDEFINITE_PRONOUNS |= {"someone", "anybody", "everybody", "nobody", "somebody"}
NOUN_STACK_WORDS = 4
SUBJECT_VERB_GAP_WORDS = 16

WORDNET_RELEASE = re.compile(r"wordnet\d{4}")
# A table or a network is a group too, but not a social group.
ANIMATE_SYNSETS = {"person.n.01", "animal.n.01", "people.n.01", "social_group.n.01"}
# People, animals and groups that WordNet ranks below another sense ("lead", "none of us").
PERSON_NOUNS = {"agent", "bank", "city", "development", "everybody", "everyone", "fan", "founder"}
PERSON_NOUNS |= {"group", "lab", "labeler", "lead", "leadership", "market", "media", "museum"}
PERSON_NOUNS |= {"newspaper", "office", "operator", "org", "rater", "session", "shop"}
PERSON_NOUNS |= {"species", "startup", "store", "streamer", "subagent", "superintelligence", "we"}
PERSON_NOUNS |= {"world"}
# Software and models whose first WordNet sense is a person ("the interpreter knows").
THING_NOUNS = {"allocator", "bandit", "branch", "classifier", "client", "compiler", "doc"}
THING_NOUNS |= {"dropout", "host", "interpreter", "ranker", "router", "tagger", "tracker"}
THING_NOUNS |= {"translator"}
# Words that stand for people as often as for things ("no one knows", "thousands bought").
STAND_IN_NOUNS = {"one", "other", "dozen", "hundred", "thousand", "million", "billion"}
# A part, amount or kind of what follows "of" ("the rest of the team", "a share of households").
PARTITIVE_HEADS = {"%", "all", "any", "bulk", "circle", "each", "few", "fraction", "group"}
PARTITIVE_HEADS |= {"half", "kind", "lot", "majority", "many", "minority", "most", "next"}
PARTITIVE_HEADS |= {"none", "number", "part", "percent", "portion", "proportion", "quarter"}
PARTITIVE_HEADS |= {"remainder", "rest", "share", "some", "sort", "third", "type"}
PARTITIVE_HEADS |= STAND_IN_NOUNS
INTENT_VERBS = {"eat", "hope", "know", "misunderstand", "promise", "want"}
AGENCY_VERBS = {"buy", "carry", "crowd", "earn", "recoup", "repay"}
RULE_BY_VERB = dict.fromkeys(INTENT_VERBS, "inanimate-subject")
RULE_BY_VERB |= dict.fromkeys(AGENCY_VERBS, "inanimate-subject-check")
# "Promises to be dry" says what is likely, which a thing can do.
LIKELY_COMPLEMENTS = {"be", "become"}
LINT_PROSE_ANIMACY = (PHRASE_RULES["inverted-animacy"], PHRASE_RULES["inverted-animacy-check"])

MESSAGES = {
    "dropped-relativizer": (
        'Check: a clause that describes a noun starts without "that" (advisory). When its'
        ' subject is a noun phrase, add "that" ("the bread that the old baker sold") so the'
        " reader sees where the clause starts."
    ),
    "noun-stack": (
        f'Stack of {NOUN_STACK_WORDS} or more nouns; split it with "of" or "for" ("the schedule'
        ' for training library volunteers"), or name the thing in plain words. Hyphenating the'
        " stack is not a fix."
    ),
    "subject-verb-gap": (
        f"Subject {SUBJECT_VERB_GAP_WORDS} or more words before its verb; move the subject next to"
        " its verb, for example by giving the description its own sentence or putting it after"
        " the verb."
    ),
    "inanimate-subject": (
        'A thing that wants, knows, hopes, promises, misunderstands or eats ("the cache knows",'
        ' "the backup ate the disk"). Say what the thing does, shows or contains, or who acts.'
    ),
    "inanimate-subject-check": (
        "Check: a thing that carries, earns, buys, crowds, recoups or repays (advisory). If the"
        ' verb is a figure of speech ("the memo carries a warning"), say what the thing'
        ' contains, costs or causes, or who acts; a literal use ("the truck carries gravel") is'
        " fine."
    ),
}


@functools.lru_cache(maxsize=1)
def load_wordnet() -> WordNetCorpusReader:
    """Load the newest Open English WordNet in NLTK's index, fetched once into the cache."""
    downloader = nltk.downloader.Downloader()
    release = max(
        package.id for package in downloader.packages() if WORDNET_RELEASE.fullmatch(package.id)
    )
    data_dir = cache_dir() / "nltk_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(data_dir / f"{release}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not (data_dir / "corpora" / release).is_dir() and not downloader.download(
            release, download_dir=str(data_dir), quiet=True
        ):
            raise RuntimeError(f"NLTK could not download {release}")
    nltk.data.path.insert(0, str(data_dir))
    with warnings.catch_warnings():
        # The newer releases have no multilingual data, which nothing here reads.
        warnings.filterwarnings("ignore", message="The multilingual functions")
        return WordNetCorpusReader(nltk.data.find(f"corpora/{release}"), None)


def _names_a_person(word: str, wordnet: WordNetCorpusReader) -> bool:
    """Whether a noun names a person, an animal or a social group in its most common sense in
    WordNet, unless one of the two lists says otherwise."""
    if word in THING_NOUNS | PERSON_NOUNS:
        return word in PERSON_NOUNS
    senses = wordnet.synsets(word, pos="n")
    if not senses:
        return False
    kinds = {senses[0].name(), *(sense.name() for sense in senses[0].closure(Synset.hypernyms))}
    return bool(kinds & ANIMATE_SYNSETS)


def names_people(candidate: InanimateSubject, wordnet: WordNetCorpusReader) -> bool:
    """Whether a subject names people: its lemma decides, or after a partitive head the noun
    after "of" ("the rest of the team" names people, "an audit of the residents" a thing)."""
    if candidate.of_lemma is not None and candidate.subject_lemma in PARTITIVE_HEADS:
        return _names_a_person(candidate.of_lemma, wordnet)
    return _names_a_person(candidate.subject_lemma, wordnet)


def _flagged_by_lint_prose(sentence: Sentence, candidate: InanimateSubject) -> bool:
    """Whether lint_prose.py's inverted-animacy rules already flag this subject and verb."""
    start = candidate.span.start - sentence.span.start
    end = candidate.span.end - sentence.span.start
    return any(
        match.start("hit") <= start and end <= match.end("hit")
        for rule in LINT_PROSE_ANIMACY
        for match in rule.finditer(sentence.span.text)
    )


def _inanimate_subject_rule(
    sentence: Sentence, candidate: InanimateSubject, wordnet: WordNetCorpusReader
) -> str | None:
    """The rule a thing with a person's verb breaks, or None."""
    verb = candidate.verb_lemma
    if candidate.subject_kind != "noun" or candidate.subject_lemma in STAND_IN_NOUNS:
        return None
    if verb == "promise" and candidate.complement_lemma in LIKELY_COMPLEMENTS:
        return None
    rule = RULE_BY_VERB.get(verb)
    if rule is None or names_people(candidate, wordnet):
        return None
    return None if _flagged_by_lint_prose(sentence, candidate) else rule


def _quoted(sentence: Sentence, span: Span) -> bool:
    """Whether a span starts inside a double-quoted span of its sentence."""
    offset = span.start - sentence.span.start
    return any(
        quote.start() <= offset < quote.end() for quote in QUOTATION.finditer(sentence.span.text)
    )


def _flagged_spans(sentence: Sentence, wordnet: WordNetCorpusReader) -> list[tuple[str, Span]]:
    """The rule and span of each finding in one sentence."""
    flagged = [
        ("dropped-relativizer", relative.span)
        for relative in sentence.object_relatives
        if relative.relativizer is None
        and relative.subject_words >= DROPPED_RELATIVIZER_SUBJECT_WORDS
        and relative.head.lower() not in INDEFINITE_PRONOUNS
    ]
    flagged += [
        ("noun-stack", stack.span)
        for stack in sentence.noun_stacks
        if stack.common_words >= NOUN_STACK_WORDS
    ]
    gaps = [
        gap
        for gap in sentence.subject_verb_gaps
        if gap.words_between >= SUBJECT_VERB_GAP_WORDS and not gap.crosses_clause
    ]
    if gaps:
        flagged.append(("subject-verb-gap", max(gaps, key=lambda gap: gap.words_between).span))
    for candidate in sentence.inanimate_subjects:
        rule = _inanimate_subject_rule(sentence, candidate, wordnet)
        if rule is not None:
            flagged.append((rule, candidate.span))
    return [(rule, span) for rule, span in flagged if not _quoted(sentence, span)]


def _findings(sentences: list[Sentence], lines: list[str]) -> list[Finding]:
    wordnet = load_wordnet()
    findings = [
        Finding(rule, span.line, span.column, excerpt(lines[span.line - 1], span.column))
        for sentence in sentences
        for rule, span in _flagged_spans(sentence, wordnet)
    ]
    return sorted(findings, key=lambda finding: (finding.line, finding.column, finding.rule))


def lint_texts(texts: Sequence[str], nlp: Language) -> list[list[Finding]]:
    """Return each markdown text's findings, parsing all of them in one pass."""
    analyzed = analyze_texts(texts, nlp)
    return [_findings(sentences, text.splitlines()) for text, sentences in zip(texts, analyzed)]


def lint_text(text: str, nlp: Language) -> list[Finding]:
    return lint_texts([text], nlp)[0]


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write findings as JSON")
    parser.add_argument("inputs", nargs="+", metavar="INPUT", help="markdown or plain-text file")
    options = parser.parse_args(arguments)
    missing = [path for path in options.inputs if not Path(path).is_file()]
    if missing:
        parser.error(f"no such file: {', '.join(missing)}")
    texts = [Path(path).read_text(encoding="utf-8") for path in options.inputs]
    findings = lint_texts(texts, load_model())
    return write_findings(zip(options.inputs, findings), MESSAGES, as_json=options.json)


if __name__ == "__main__":
    # spacy-curated-transformers calls the deprecated torch.jit.script; nothing here can fix that.
    warnings.filterwarnings(
        "ignore", message=r"`torch\.jit\.script` is deprecated", category=FutureWarning
    )
    raise SystemExit(main())
