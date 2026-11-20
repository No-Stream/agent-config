"""Word lists for lint_prose.py and the regular expressions built from them."""

import re

LABEL_WORDS = "step|phase|stage|round|option|arm|run|variant|approach|plan|track|wave|batch|tier"
LABEL_PATTERN = re.compile(rf"\b(?P<word>(?i:{LABEL_WORDS}))\s+(?P<label>\d+[a-z]?|[A-Z])\b")
PRONOUN_I_AFTER_LABEL = re.compile(rf"(?i:{LABEL_WORDS})\s+I\s+(?!(?:is|was|has|had)\b)[a-z]")
TITLE_SMALL_WORDS = {"a", "an", "the", "of", "and", "or", "to", "in", "on", "for", "with", "vs"}

ACTION_NOUNS = (
    "acquisition|adoption|alteration|assessment|calculation|completion|consideration"
    "|construction|creation|deployment|determination|development|elimination|enhancement"
    "|establishment|evaluation|examination|execution|exploration|facilitation"
    "|identification|implementation|installation|introduction|investigation|migration"
    "|modification|preparation|prioritization|provision|refinement|standardization"
    "|utilization|validation|verification"
)
ARTIFACT_NOUNS = (
    "algorithm|analyses|analysis|api|benchmark|chart|classifier|code|compiler|data|dataset"
    "|estimator|evidence|experiment|function|graph|hook|libraries|library|linter|loss"
    "|losses|method|metric|model|net|network|numbers|optimizer|parser|pipeline|plot|program"
    "|queries|query|result|script|server|system|test|tool"
)
ANIMATE_VERBS = (
    "argue|argues|believe|believes|care|cares|claim|claims|complain|complained|complains"
    "|hate|hates|hope|hoped|hopes|insist|insisted|insists|knew|know|knows|likes|loves"
    "|prefer|prefers|pretend|pretended|pretends|promise|promises|refuse|refused|refuses"
    "|said|say|says|tell|tells|think|thinks|told|tried|tries|try|understand|understands"
    "|want|wanted|wants|wish|wished|wishes|worries|worry"
)
ANIMATE_PROGRESSIVES = (
    "complaining|hoping|insisting|pretending|refusing|saying|telling|thinking|trying|wanting"
)
CLAUSE_START = (
    r"(?:\A\s*|[.!?;:,]\s+|\(\s*|\b(?:and|but|or|so|because|if|when|whenever|while|until|unless"
    r"|that|since|although|though|then|where|once|after|before)\s+)"
)
ARTIFACT_SUBJECT = (
    r"(?:(?:the|this|that|these|those|our|your|its|their|my|each|every|a|an)\s+)?"
    rf"(?:[a-z][\w-]*\s+)?(?:{ARTIFACT_NOUNS})s?"
)
ANIMATE_PREDICATE = (
    r"(?:(?:will|would|can|could|should|may|might|must|does|did|do|doesn't|didn't|don't"
    rf"|won't|can't|cannot)\s+(?:not\s+)?)?(?:{ANIMATE_VERBS})"
    rf"|(?:is|are|was|were)\s+(?:not\s+|still\s+)?(?:{ANIMATE_PROGRESSIVES})"
)
PHRASE_RULES = {
    "stacked-hedge": re.compile(
        r"(?i)\b(?P<hit>(?:may|might|could|can)\s+(?:possibly|potentially|perhaps|conceivably))\b"
    ),
    "nominalization-of": re.compile(rf"(?i)\b(?P<hit>(?:{ACTION_NOUNS})\s+of)\b"),
    "inverted-animacy": re.compile(
        rf"(?i){CLAUSE_START}(?P<hit>{ARTIFACT_SUBJECT}\s+(?:{ANIMATE_PREDICATE}))\b"
        r"(?!\s*(?:[,;:.!?)]|(?:and|or|are|is|were|was|such)\b))"
    ),
}

MONTH = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?"
)
NOT_A_NUMBER = re.compile(
    rf"\b{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?\b(?:,?\s+\d{{4}}\b)?"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH}(?:\s+\d{{4}}\b)?"
    r"|(?i:\b(?:fig(?:ure)?s?|tables?|sections?|chapters?|appendix|eqs?|equations?|pages?|pp"
    r"|lines?|steps?|items?|parts?|footnotes?)\.?\s+\d+(?:\.\d+)*[a-z]?\b)"
    r"|§\s*\d+(?:\.\d+)*"
    r"|\[\d+(?:\s*[,–-]\s*\d+)*(?:\]|(?=\s|$))"
)
NUMBER = re.compile(
    r"(?<![\w.,/:-])[-+−]?[$€£]?\d+(?:[.,]\d+)*(?:%|×|[A-Za-zµ]{1,3}\b)?(?![\w/-]|[.,:]\d)"
)
# A small count in words ("two directions") is ordinary prose: only ten up and multiples count.
SMALL_NUMBER_WORD = r"(?:one|two|three|four|five|six|seven|eight|nine)"
LARGE_NUMBER_WORD = (
    r"(?:ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty"
    r"|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)"
)
NUMBER_WORD = rf"(?:{SMALL_NUMBER_WORD}|{LARGE_NUMBER_WORD})"
SPELLED_NUMBER = re.compile(
    rf"(?i)\b{NUMBER_WORD}(?:(?:-|\s+|(?:(?<=hundred)|(?<=thousand))\s+and\s+){NUMBER_WORD})*\b"
    r"(?P<times>\s+times\b)?"
)
LARGE_SPELLED_NUMBER = re.compile(rf"(?i)\b{LARGE_NUMBER_WORD}\b")
YEAR_ORDINAL_OR_VERSION = re.compile(r"(?:1[6-9]|20)\d\ds?|\d+(?:st|nd|rd|th)|\d+(?:\.\d+){2,}")
ARITHMETIC = re.compile(r"\d[\s)]*[=×*][\s(]*[-+−$€£]?\d|=\s*[-+−$€£]?\d")
