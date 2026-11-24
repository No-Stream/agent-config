"""Syntactic features of markdown prose, read from spaCy dependency parses of its sentences.

The features follow Clark, Martin and Mahowald (arXiv:2610.29162, Section 3.1 and Appendix B.1)
with their transformer parser, and the text is prepared as their Appendix A.5 prepares it, by
`lint_prose_markdown.stretches`; eval/README.md, "Syntax rules from a paper on AI-generated
language", gives the preparation and the differences.

Interface:

- `load_model()` returns spaCy's `en_core_web_trf` at the newest version compatible with the
  installed spaCy, fetched once into `cache_dir()`, which is `$XDG_CACHE_HOME/write-plainly`
  (default `~/.cache`).
- `analyze(text, nlp, noun_lemmas)` returns the document's `Sentence`s in order, and
  `analyze_texts(texts, nlp, noun_lemmas)` does the same for many documents in one parsing pass.
  `noun_lemmas`, the lemmas a human corpus uses mostly as nouns, is the reference for denominal
  verbs; `noun_dominant_lemmas(sentences)` builds it from that corpus's analyzed sentences.
- Each feature has a `Span`: offsets into the analyzed text, the 1-based line and column of its
  start, and the source text it covers. A `Sentence` has `words` (its non-punctuation tokens,
  with code, URLs and paths as `lint_prose_markdown.PLACEHOLDER`), `arc_lengths` (in words, for
  every arc with no punctuation end, root excluded), `noun_stacks` (three or more nouns in a compound chain),
  `object_relatives` (the relativizer or None when dropped, a preposition before it, and the
  clause subject's length), `subject_verb_gaps` (words between a subject and its verb), and the
  unjudged candidates `inanimate_subjects` and `denominal_verbs`. `doc` is the spaCy parse and
  `placeholders` the indices of its PLACEHOLDER tokens.
- `length_bin(words)` gives the paper's sentence-length bin for dependency-length
  standardization (Appendix B.3), or None for a sentence over 30 words.
"""

from __future__ import annotations

import fcntl
import functools
import json
import os
import shutil
import tempfile
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import spacy
from spacy.cli.download import get_model_filename
from spacy.language import Language
from spacy.tokens import Doc, Token
from spacy.util import get_minor_version, is_compatible_version

from lint_prose_markdown import (
    PLACEHOLDER,
    Section,
    Stretch,
    prose_blocks,
    sentence_spans,
    stretches,
)

MODEL_NAME = "en_core_web_trf"
NOUN_STACK_MIN_NOUNS = 3
LENGTH_BINS = ((1, 5), (6, 10), (11, 15), (16, 20), (21, 30))
PIPE_BATCH_SIZE = 256

NOUN_POS = {"NOUN", "PROPN"}
RELATIVE_HEAD_POS = {"NOUN", "PROPN", "PRON"}
RELATIVIZERS = {"that", "which", "who", "whom"}
RELATIVE_WORDS = RELATIVIZERS | {"whose", "where", "when", "why"}
# A relative clause on these nouns usually has an adverbial gap ("the way she paints").
ADVERBIAL_HEADS = {"way", "reason", "time", "day", "moment", "year", "week", "month", "hour"}
ADVERBIAL_HEADS |= {"minute", "place"}
DEMONSTRATIVE_SUBJECTS = {"it", "this", "that", "these", "those"}
FREE_RELATIVES = {"what", "whatever", "whoever", "whichever", "how"}
# A noun after one of these opens a question ("ask which house the plant came from").
QUESTION_WORDS = {"which", "what", "whichever", "whatever"}
OBJECTS = ("dobj", "dative")
# Verbs that take an object and then a clause ("told the team the build failed").
OBJECT_AND_CLAUSE_VERBS = {"tell", "remind", "warn", "show", "assure", "reassure", "promise"}
OBJECT_AND_CLAUSE_VERBS |= {"inform", "notify", "convince", "persuade", "teach", "ask"}
OBJECT_AND_CLAUSE_VERBS |= {"advise", "bet"}
CLAUSE_OPENERS = {"CCONJ", "SCONJ", "PUNCT"}
PERSON_ENTITIES = {"PERSON", "NORP"}
# Forms the lemmatizer gets wrong ("hopes" as "hop", plural "species" as "specie").
LEMMA_CORRECTIONS = {"hopes": "hope", "hoped": "hope", "hoping": "hope", "species": "species"}


@dataclass(frozen=True)
class Span:
    """A stretch of the analyzed text: offsets into it, where it starts, and what it says."""

    start: int
    end: int
    line: int
    column: int
    text: str


@dataclass(frozen=True)
class NounStack:
    """Nouns joined by compound arcs; `nouns` counts common and proper nouns, not PLACEHOLDER, and
    `common_words` the common nouns, a hyphen or slash compound ("error-message", "I/O") as one."""

    span: Span
    nouns: int
    proper_nouns: int
    common_words: int


@dataclass(frozen=True)
class ObjectRelative:
    """A relative clause whose gap is the object of its verb or of a preposition; `preposition`
    is the one before the relativizer ("on which"), and `subject_words` counts the words of the
    clause's own subject."""

    span: Span
    head: str
    verb: str
    relativizer: str | None
    preposition: str | None
    subject_words: int


@dataclass(frozen=True)
class SubjectVerbGap:
    """A subject and the first word of its verb group after it, with the words between them;
    `crosses_clause` is a ";", ":" or clause-level "and" between them, which marks a misparse."""

    span: Span
    subject: str
    verb: str
    words_between: int
    crosses_clause: bool


@dataclass(frozen=True)
class InanimateSubject:
    """An active verb whose subject is a pronoun such as "it", code, or a noun not naming a
    person; `subject_kind` is "pronoun", "code", "noun" or "name", and `verb_lemma` keeps a
    phrasal verb's particle ("carry out"). `of_lemma` is the lemma of the noun after "of" in the
    subject ("team" in "the rest of the team"), and `complement_lemma` that of the verb's
    infinitive complement ("be" in "promises to be dry"), each or None."""

    span: Span
    subject: str
    subject_lemma: str
    verb_lemma: str
    subject_kind: str
    of_lemma: str | None
    complement_lemma: str | None


@dataclass(frozen=True)
class DenominalVerb:
    """A verb whose lemma the reference corpus uses mostly as a noun."""

    span: Span
    lemma: str


@dataclass(frozen=True)
class Sentence:
    """One parsed sentence of prose and the features found in it."""

    span: Span
    section: Section
    words: tuple[str, ...]
    arc_lengths: tuple[int, ...]
    noun_stacks: tuple[NounStack, ...]
    object_relatives: tuple[ObjectRelative, ...]
    subject_verb_gaps: tuple[SubjectVerbGap, ...]
    inanimate_subjects: tuple[InanimateSubject, ...]
    denominal_verbs: tuple[DenominalVerb, ...]
    doc: Doc = field(compare=False, repr=False)
    placeholders: frozenset[int] = field(compare=False, repr=False)


def cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "write-plainly"


def _latest_compatible_version() -> str:
    """Return the newest model version spaCy's compatibility table lists for this spaCy."""
    with urllib.request.urlopen(spacy.about.__compatibility__, timeout=30) as response:
        table = json.load(response)["spacy"]
    minor = get_minor_version(spacy.about.__version__)
    if minor not in table or MODEL_NAME not in table[minor]:
        raise LookupError(f"spaCy's compatibility table has no {MODEL_NAME} for spaCy {minor}")
    return table[minor][MODEL_NAME][0]


def _fetch_model(version: str, model_dir: Path) -> None:
    """Download the model's wheel and unpack it into model_dir, which appears complete or not at
    all."""
    url = f"{spacy.about.__download_url__}/{get_model_filename(MODEL_NAME, version)}"
    with tempfile.TemporaryDirectory(dir=model_dir.parent) as scratch:
        wheel = Path(scratch) / "model.whl"
        with urllib.request.urlopen(url, timeout=300) as response, wheel.open("wb") as copy:
            shutil.copyfileobj(response, copy)
        unpacked = Path(scratch) / "unpacked"
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(unpacked)
        unpacked.rename(model_dir)


@functools.lru_cache(maxsize=1)
def load_model() -> Language:
    """Load en_core_web_trf at the newest version compatible with the installed spaCy."""
    version = _latest_compatible_version()
    cache = cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    model_dir = cache / f"{MODEL_NAME}-{version}"
    with open(cache / f"{MODEL_NAME}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not model_dir.is_dir():
            _fetch_model(version, model_dir)
    nlp = spacy.load(model_dir / MODEL_NAME / f"{MODEL_NAME}-{version}")
    if not is_compatible_version(spacy.about.__version__, nlp.meta["spacy_version"]):
        raise RuntimeError(f"{MODEL_NAME} {version} needs spaCy {nlp.meta['spacy_version']}")
    return nlp


def length_bin(words: int) -> int | None:
    """Return the index of the paper's sentence-length bin, or None past 30 words."""
    return next(
        (index for index, (low, high) in enumerate(LENGTH_BINS) if low <= words <= high), None
    )


def _lemma(token: Token) -> str:
    return LEMMA_CORRECTIONS.get(token.lower_, token.lemma_.lower())


def _prepare(text: str) -> list[Stretch]:
    """The sentences of a markdown text's prose, prepared as the paper prepares them."""
    return [
        stretch.part(start, end)
        for block in prose_blocks(text)
        for stretch in stretches(block)
        for start, end in sentence_spans(stretch.text)
    ]


def _tokenized(nlp: Language, prepared: Stretch) -> Doc:
    """A sentence as the parser's tokenizer splits it, with each placeholder a token of its own,
    since the tokenizer keeps "foo(Xyzzy" and "@Xyzzy" together."""
    doc = nlp.make_doc(prepared.text)
    edges = {
        edge for start in prepared.placeholder_starts for edge in (start, start + len(PLACEHOLDER))
    }
    with doc.retokenize() as retokenizer:
        for token in doc:
            cuts = sorted(edge - token.idx for edge in edges if 0 < edge - token.idx < len(token))
            if cuts:
                pieces = [token.text[a:b] for a, b in zip([0, *cuts], [*cuts, len(token)])]
                heads = [(token, index) for index in range(len(pieces))]
                retokenizer.split(token, pieces, heads=heads)
    return doc


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for line in text.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    return starts


class _Reader:
    """Maps one parsed sentence's tokens back to spans of the analyzed text."""

    def __init__(self, prepared: Stretch, doc: Doc, text: str, line_starts: list[int]) -> None:
        self.prepared = prepared
        self.doc = doc
        self.text = text
        self.line_starts = line_starts
        self.placeholders = frozenset(
            token.i for token in doc if token.idx in prepared.placeholder_starts
        )
        words = [token for token in doc if not (token.is_punct or token.is_space)]
        self.word_index = {token.i: index for index, token in enumerate(words)}
        self.words = tuple(token.text for token in words)

    def _offset(self, block_offset: int) -> int:
        line, column = self.prepared.block.position(block_offset)
        return self.line_starts[line - 1] + column - 1

    def span(self, first: Token, last: Token) -> Span:
        line, column = self.prepared.block.position(self.prepared.starts[first.idx])
        start = self.line_starts[line - 1] + column - 1
        end = self._offset(self.prepared.ends[last.idx + len(last.text) - 1] - 1) + 1
        return Span(start, end, line, column, self.text[start:end])

    def pair(self, one: Token, other: Token) -> Span:
        first, last = sorted((one, other), key=lambda token: token.i)
        return self.span(first, last)

    def is_word(self, token: Token) -> bool:
        return token.i in self.word_index

    def is_placeholder(self, token: Token) -> bool:
        return token.i in self.placeholders


def _arc_lengths(reader: _Reader) -> tuple[int, ...]:
    return tuple(
        abs(reader.word_index[token.i] - reader.word_index[token.head.i])
        for token in reader.doc
        if token.head.i != token.i and reader.is_word(token) and reader.is_word(token.head)
    )


def _compound_nouns(token: Token) -> list[Token]:
    nouns = [token]
    for child in token.children:
        if child.dep_ == "compound" and child.pos_ in NOUN_POS:
            nouns.extend(_compound_nouns(child))
    return nouns


def _noun_stacks(reader: _Reader) -> tuple[NounStack, ...]:
    stacks: list[NounStack] = []
    for token in reader.doc:
        if token.pos_ not in NOUN_POS or token.dep_ == "compound":
            continue
        chain = sorted(_compound_nouns(token), key=lambda noun: noun.i)
        nouns = [noun for noun in chain if reader.is_word(noun) and not reader.is_placeholder(noun)]
        if len(nouns) < NOUN_STACK_MIN_NOUNS:
            continue
        proper = sum(1 for noun in nouns if noun.pos_ == "PROPN")
        common_words = sum(
            1 for noun in nouns if noun.pos_ == "NOUN" and not _continues_word(reader.doc, noun)
        )
        stacks.append(NounStack(reader.span(chain[0], chain[-1]), len(nouns), proper, common_words))
    return tuple(stacks)


def _continues_word(doc: Doc, token: Token) -> bool:
    """Whether a token continues a word joined by a hyphen or slash ("error-message", "I/O")."""
    if token.i < 2:
        return False
    joiner, before = doc[token.i - 1], doc[token.i - 2]
    return joiner.text in ("-", "/") and not joiner.whitespace_ and not before.whitespace_


def _clause_end(reader: _Reader, verb: Token) -> Token:
    last = reader.doc[verb.right_edge.i]
    while last.i > verb.i and not reader.is_word(last):
        last = reader.doc[last.i - 1]
    return last


def _subject_words(reader: _Reader, subject: Token) -> int:
    return sum(1 for token in subject.subtree if reader.is_word(token))


def _opened_by_whose(head: Token) -> bool:
    """Whether a noun follows "whose", so the clause on it opens with "whose" ("stacks whose
    grouping a reader has to guess")."""
    return any(child.lower_ == "whose" for child in head.children)


def _object_relative(reader: _Reader, verb: Token) -> ObjectRelative | None:
    head = verb.head
    if verb.dep_ != "relcl" or verb.pos_ != "VERB" or head.pos_ not in RELATIVE_HEAD_POS:
        return None
    if head.i > verb.i or _lemma(head) in ADVERBIAL_HEADS or _opened_by_whose(head):
        return None
    subject = next(
        (
            child
            for child in verb.children
            if child.dep_ == "nsubj" and child.lower_ not in RELATIVIZERS and head.i < child.i
        ),
        None,
    )
    if subject is None:
        return None
    before_subject = reader.doc[head.i + 1 : subject.i]
    relativizer = next((token for token in before_subject if token.lower_ in RELATIVE_WORDS), None)
    if relativizer is None:
        # A dropped relativizer leaves the clause's subject right after the noun it modifies.
        adjacent = subject.left_edge.i == head.i + 1
        if not adjacent or any(child.dep_ in OBJECTS for child in verb.children):
            return None
    elif relativizer.lower_ not in RELATIVIZERS or relativizer.dep_ not in (*OBJECTS, "pobj"):
        return None
    preposition = None
    if (
        relativizer is not None
        and relativizer.dep_ == "pobj"
        and relativizer.head.i < relativizer.i
    ):
        preposition = relativizer.head.lower_
    return ObjectRelative(
        reader.span(head, _clause_end(reader, verb)),
        head.text,
        verb.text,
        None if relativizer is None else relativizer.lower_,
        preposition,
        _subject_words(reader, subject),
    )


def _opens_clause(doc: Doc, noun: Token) -> bool:
    """Whether a noun sits in a prepositional phrase that opens its clause ("and in May")."""
    while noun.dep_ == "pobj":
        preposition = noun.head
        previous = doc[preposition.i - 1] if preposition.i else None
        if previous is None or previous.pos_ in CLAUSE_OPENERS or previous.lower_ in ("so", "then"):
            return True
        noun = preposition.head
    return False


def _relative_after_noun(reader: _Reader, subject: Token) -> ObjectRelative | None:
    """Read the noun right before a clause's subject as the head of a relative clause that dropped
    its relativizer, where the parser attached that clause to another word."""
    verb, doc = subject.head, reader.doc
    if subject.dep_ != "nsubj" or verb.pos_ != "VERB" or verb.dep_ == "ROOT" or verb.i < subject.i:
        return None
    if subject.left_edge.i == 0 or any(child.dep_ in OBJECTS for child in verb.children):
        return None
    head = doc[subject.left_edge.i - 1]
    if (
        head.pos_ not in RELATIVE_HEAD_POS
        or head.tag_ in ("PRP", "EX")
        or reader.is_placeholder(head)
    ):
        return None
    if head.lower_ in RELATIVE_WORDS | FREE_RELATIVES or _lemma(head) in ADVERBIAL_HEADS:
        return None
    if subject.left_edge.lower_ in RELATIVE_WORDS or _opens_clause(doc, head):
        return None
    if _opened_by_whose(head):
        return None
    if any(child.dep_ == "det" and child.lower_ in QUESTION_WORDS for child in head.children):
        return None
    told = head.dep_ in OBJECTS and _lemma(head.head) in OBJECT_AND_CLAUSE_VERBS
    if told and head.head.i == verb.head.i:
        return None
    return ObjectRelative(
        reader.span(head, _clause_end(reader, verb)),
        head.text,
        verb.text,
        None,
        None,
        _subject_words(reader, subject),
    )


def _object_relatives(reader: _Reader) -> tuple[ObjectRelative, ...]:
    """Each verb's object relative, read from the parse, or else from a noun right before the
    verb's subject."""
    found: dict[int, ObjectRelative] = {}
    for verb in reader.doc:
        relative = _object_relative(reader, verb)
        if relative is not None:
            found[verb.i] = relative
    for subject in reader.doc:
        relative = None if subject.head.i in found else _relative_after_noun(reader, subject)
        if relative is not None:
            found[subject.head.i] = relative
    return tuple(found[index] for index in sorted(found))


def _subject_verb_gaps(reader: _Reader) -> tuple[SubjectVerbGap, ...]:
    gaps: list[SubjectVerbGap] = []
    for subject in reader.doc:
        if subject.dep_ not in ("nsubj", "nsubjpass"):
            continue
        group = [subject.head, *(c for c in subject.head.children if c.dep_ in ("aux", "auxpass"))]
        following = [token for token in group if token.i > subject.i and reader.is_word(token)]
        if not following or not reader.is_word(subject):
            continue
        verb = min(following, key=lambda token: token.i)
        between = reader.word_index[verb.i] - reader.word_index[subject.i] - 1
        span = reader.span(subject, verb)
        crosses = _crosses_clause(reader.doc, subject, verb)
        gaps.append(SubjectVerbGap(span, subject.text, verb.text, between, crosses))
    return tuple(gaps)


def _crosses_clause(doc: Doc, subject: Token, verb: Token) -> bool:
    """Whether a ";" or ":", or an "and" that joins two verbs, lies between a subject and its
    verb; an "and" inside a phrase ("after weeks of debate and two votes") joins no clauses."""
    subject_phrase = {token.i for token in subject.subtree}
    return any(
        token.text in (";", ":")
        or (
            token.dep_ == "cc"
            and token.head.pos_ in ("VERB", "AUX")
            and token.head.i not in subject_phrase
            and token.head.i != verb.i
        )
        for token in doc[subject.i + 1 : verb.i]
    )


def _active_subject(verb: Token) -> Token | None:
    """Return a verb's active subject, the antecedent of a relative pronoun subject, or the
    subject a coordinated verb shares with the verb before it."""
    subject = next((child for child in verb.children if child.dep_ == "nsubj"), None)
    if subject is None and verb.dep_ == "conj" and verb.head.pos_ == "VERB":
        if any(child.dep_ == "nsubjpass" for child in verb.children):
            return None
        return _active_subject(verb.head)
    if subject is not None and subject.tag_ in ("WDT", "WP") and verb.dep_ == "relcl":
        return verb.head
    return subject


def _subject_kind(reader: _Reader, subject: Token) -> str | None:
    if reader.is_placeholder(subject):
        return "code"
    if subject.pos_ == "PRON":
        return "pronoun" if subject.lower_ in DEMONSTRATIVE_SUBJECTS else None
    if subject.pos_ == "NOUN":
        return "noun"
    if subject.pos_ == "PROPN" and subject.ent_type_ not in PERSON_ENTITIES:
        return "name"
    return None


def _child(token: Token, dep: str) -> Token | None:
    return next((child for child in token.children if child.dep_ == dep), None)


def _of_object(subject: Token) -> Token | None:
    """The noun after "of" in a subject such as "the rest of the team"."""
    of = next((c for c in subject.children if c.dep_ == "prep" and c.lower_ == "of"), None)
    return None if of is None else _child(of, "pobj")


def _verb_lemma(verb: Token) -> str:
    """A verb's lemma, with its particle for a phrasal verb ("carry out")."""
    particle = _child(verb, "prt")
    return _lemma(verb) if particle is None else f"{_lemma(verb)} {particle.lower_}"


def _optional_lemma(token: Token | None) -> str | None:
    return None if token is None else _lemma(token)


def _inanimate_subjects(reader: _Reader) -> tuple[InanimateSubject, ...]:
    candidates: list[InanimateSubject] = []
    for verb in reader.doc:
        # A participle with no auxiliary describes its noun ("their existence known").
        if verb.pos_ != "VERB" or (verb.tag_ == "VBN" and _child(verb, "aux") is None):
            continue
        subject = _active_subject(verb)
        kind = None if subject is None else _subject_kind(reader, subject)
        if subject is None or kind is None:
            continue
        candidates.append(
            InanimateSubject(
                reader.pair(subject, verb),
                subject.text,
                _lemma(subject),
                _verb_lemma(verb),
                kind,
                _optional_lemma(_of_object(subject)),
                _optional_lemma(_child(verb, "xcomp")),
            )
        )
    return tuple(candidates)


def _denominal_verbs(reader: _Reader, noun_lemmas: frozenset[str]) -> tuple[DenominalVerb, ...]:
    return tuple(
        DenominalVerb(reader.span(token, token), _lemma(token))
        for token in reader.doc
        if token.pos_ == "VERB" and _lemma(token) in noun_lemmas
    )


def _sentence(reader: _Reader, noun_lemmas: frozenset[str]) -> Sentence:
    return Sentence(
        span=reader.span(reader.doc[0], reader.doc[-1]),
        section=reader.prepared.block.section,
        words=reader.words,
        arc_lengths=_arc_lengths(reader),
        noun_stacks=_noun_stacks(reader),
        object_relatives=_object_relatives(reader),
        subject_verb_gaps=_subject_verb_gaps(reader),
        inanimate_subjects=_inanimate_subjects(reader),
        denominal_verbs=_denominal_verbs(reader, noun_lemmas),
        doc=reader.doc,
        placeholders=reader.placeholders,
    )


def analyze_texts(
    texts: Sequence[str], nlp: Language, noun_lemmas: frozenset[str] = frozenset()
) -> list[list[Sentence]]:
    """Parse the prose of each markdown text and return its sentences with their features."""
    prepared = [_prepare(text) for text in texts]
    docs = iter(
        nlp.pipe(
            (_tokenized(nlp, sentence) for sentences in prepared for sentence in sentences),
            batch_size=PIPE_BATCH_SIZE,
        )
    )
    analyzed: list[list[Sentence]] = []
    for text, sentences in zip(texts, prepared):
        line_starts = _line_starts(text)
        analyzed.append(
            [
                _sentence(_Reader(sentence, next(docs), text, line_starts), noun_lemmas)
                for sentence in sentences
            ]
        )
    return analyzed


def analyze(text: str, nlp: Language, noun_lemmas: frozenset[str] = frozenset()) -> list[Sentence]:
    """Parse the prose of one markdown text and return its sentences with their features."""
    return analyze_texts([text], nlp, noun_lemmas)[0]


def noun_dominant_lemmas(sentences: Iterable[Sentence]) -> frozenset[str]:
    """Return the lemmas these sentences tag as nouns more often than as verbs."""
    counts: Counter[tuple[str, str]] = Counter(
        (_lemma(token), token.pos_)
        for sentence in sentences
        for token in sentence.doc
        if token.pos_ in ("NOUN", "VERB") and token.i not in sentence.placeholders
    )
    return frozenset(
        lemma
        for (lemma, pos), count in counts.items()
        if pos == "NOUN" and count > counts[(lemma, "VERB")]
    )
