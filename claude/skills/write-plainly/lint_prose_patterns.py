"""Word lists for lint_prose.py and the regular expressions built from them."""

import re

LABEL_WORDS = (
    "step|phase|stage|round|option|arm|run|variant|approach|plan|track|wave|batch|tier|beat|route"
    "|decision|lever|item|question|ask|task|finding|candidate|idea|amendment"
)
LABEL_PATTERN = re.compile(
    rf"\b(?P<word>(?i:{LABEL_WORDS}))(?:\s+#?|-)(?P<label>\d+[a-z]?|[A-Z])\b(?!(?<=I)['’])"
)
PRONOUN_I_AFTER_LABEL = re.compile(rf"(?i:{LABEL_WORDS})\s+I\s+(?!(?:is|was|has|had)\b)[a-z]")
LIST_ENTRY_WORDS = {"step", "item"}
TRACKER_ID = re.compile(r"(?<![\w-])(?P<prefix>[A-Z][A-Z0-9]{1,9})-\d+(?:\.\d+)*(?![\w-])")
STANDARD_ID_PREFIXES = {"AES", "COVID", "CVE", "ECMA", "GLP", "GPT", "IEEE", "ISO", "MD", "PEP"}
STANDARD_ID_PREFIXES |= {"RFC", "SHA", "UTF"}
HEX_ID = re.compile(r"(?<![\w-])[a-z]{2,10}-(?=[0-9a-f]*\d)[0-9a-f]{6,12}(?![\w-])")
HASH_NUMBER = re.compile(r"(?<![\w/&#])#\d{1,5}\b")
SHORT_CODE = re.compile(r"(?<![\w.-])[A-Z]{1,2}\d{1,3}[a-z]?(?![\w-])")
PUBLIC_IDS = {"#1", "A4", "A100", "EC2", "F1", "H1", "H2", "H100", "K8s", "L4", "MP3", "MP4"}
PUBLIC_IDS |= {"P0", "P1", "P2", "P3", "Q1", "Q2", "Q3", "Q4", "R2", "S3", "T4", "V100"}
DESCRIBED_ID = re.compile(r"[A-Za-z][\w'’-]*\s+[A-Za-z][\w'’-]*\s*\((?P<inside>[^()\n]{1,40})\)")
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
ABSTRACT_NOUNS = (
    "arm|budget|card|change|comparison|cost|design|discount|display|fee|feature|gain|group|layout"
    "|lift|lineup|money|offer|page|policies|policy|price|ranking|revenue|shelf|shelves|strategy|table"
    "|treatment|variant"
)
TRANSACTION_VERBS = (
    "bought|buy|buys|carried|carries|carry|claw|claws|crowd|crowded|crowds|deserve|deserves|earn"
    "|earned|earns|held|hold|holds|paid|pay|pays|recoup|recoups|repay|repays|rescue|rescued"
    "|rescues|spend|spends|spent|win|wins|won"
)
CLAUSE_START = (
    r"(?:\A\s*|[.!?;:,]\s+|\(\s*|\b(?:and|but|or|so|because|if|when|whenever|while|until|unless"
    r"|that|since|although|though|then|where|once|after|before)\s+)"
)
SUBJECT_DETERMINER = r"(?:(?:the|this|that|these|those|our|your|its|their|my|each|every|a|an)\s+)?"
ARTIFACT_SUBJECT = rf"{SUBJECT_DETERMINER}(?:[a-z][\w-]*\s+)?(?:{ARTIFACT_NOUNS})s?"
THING_SUBJECT = rf"{SUBJECT_DETERMINER}(?:[a-z][\w-]*\s+)?(?:{ARTIFACT_NOUNS}|{ABSTRACT_NOUNS})s?"
ANIMATE_PREDICATE = (
    r"(?:(?:will|would|can|could|should|may|might|must|does|did|do|doesn't|didn't|don't"
    rf"|won't|can't|cannot)\s+(?:not\s+)?)?(?:{ANIMATE_VERBS})"
    rf"|(?:is|are|was|were)\s+(?:not\s+|still\s+)?(?:{ANIMATE_PROGRESSIVES})"
)
NOT_A_PREDICATE = r"(?!\s*(?:[,;:.!?)]|(?:and|or|are|is|were|was|such)\b))"
DISCOURSE_NOUNS = (
    "answer|ask|asks|command|commands|comment|decision|decisions|discussion|explanation|fix|list"
    "|message|note|option|options|plan|point|proposal|question|questions|reply|steps|suggestion"
    "|summary|update"
)
CANNOT = r"(?:can(?:not| not|['’]t)|could(?:n['’]t| not))"
ISE_STEMS = (
    "apolog|author|capital|categor|central|character|critic|custom|emphas|final|general|initial"
    "|local|maxim|memor|minim|modern|normal|optim|organ|parallel|personal|priorit|random|real"
    "|recogn|regular|serial|special|stabil|standard|summar|synchron|token|util|vector|visual"
)
# A closed list: "analyses", "catalogue" and "programming" are American spellings too.
BRITISH_SPELLING = (
    rf"(?:{ISE_STEMS})is(?:e|es|ed|er|ers|ing|ation|ations|ational)"
    r"|(?:analy|cataly|paraly)s(?:e|ed|er|ers|ing)"
    r"|(?:arm|behavi|col|endeav|fav|flav|harb|hon|hum|lab|neighb|rum|sav|vap)our"
    r"(?:s|ed|ing|ful|able|ite|ites|al|ally|hood|er|ers)?"
    r"|(?:cent|fib|lit|(?:centi|kilo|milli)?met)re[sd]?"
    r"|(?:defen|licen|offen|preten)ces?"
    r"|(?:model|label|travel|signal)l(?:ed|ing|er|ers)"
    r"|programmes?|practis(?:e|es|ed|ing)|judgements?|ageing"
)
NOTING = (
    r"note|noting|mention|mentioning|remember|emphasi[sz]e|stress|point out|pointing out"
    r"|highlight|keep in mind|recogni[sz]e"
)
ANNOUNCED_POINT = r"(?=\s+(?:that|how|why|what|whether|here)\b|\s*[,:.;!])"
IRREGULAR_PARTICIPLES = (
    r"beaten|bought|brought|built|caught|chosen|cut|dealt|done|drawn|driven|eaten|fed|found"
    r"|forgotten|given|grown|held|hidden|kept|known|laid|led|left|lent|lost|made|met|paid"
    r"|put|read|run|said|seen|sent|set|shown|sold|spent|spoken|stolen|struck|taken|taught|thought"
    r"|thrown|told|torn|understood|upheld|won|worn|written"
)
# "Sorted by date" names a key, and "surprised by" a feeling, not the actor of a passive.
NOT_AN_ACTOR_VERBS = (
    r"accompanied|divided|filtered|followed|grouped|indexed|keyed|multiplied|normali[sz]ed"
    r"|ordered|preceded|ranked|scaled|sorted|split|weighted"
    r"|alarmed|amazed|annoyed|astonished|baffled|bored|confused|delighted|disappointed"
    r"|depressed|embarrassed|excited|fascinated|frightened|frustrated|horrified|impressed|inspired"
    r"|interested|intrigued|moved|overwhelmed|pleased|puzzled|scared|shocked|struck|surprised"
    r"|terrified|thrilled|tired|worried"
)
NOT_AN_AGENT = (
    r"far|default|hand|design|now|then|itself|themselves|chance|accident|definition|contrast"
    r"|comparison|mistake|way|means|virtue|name|about|around|roughly|almost|nearly|up|over|more"
    r"|less|half|a factor|a margin"
)
INTENSIFIER = re.compile(
    r"(?i)\b(?:(?<!\bthe )(?<!\bthis )(?<!\bthat )very|extremely|exceptionally|incredibly"
    r"|remarkably|tremendously|immensely|hugely|insanely|truly|absolutely|utterly|totally)\b"
)
LESS_ABOUT = (
    r"(?<!\bit['’]s )(?<!\bit is )(?<!\bthis is )(?<!\bthat['’]s )(?<!\bthat is )"
    r"\bless about\b[^.;?!]{1,60}?\b(?:more|than) about\b"
)
FORMAL_WORDS = (
    r"utili[sz](?:e|es|ed|ing)|commenc(?:e|es|ed|ing)|ascertain(?:s|ed|ing)?|endeavou?r(?:s|ed)? to"
    r"|facilitat(?:e|es|ed|ing)|ameliorat(?:e|es|ed|ing)|cogni[sz]ant|necessitat(?:e|es|ed|ing)"
    r"|remunerat(?:e|es|ed|ing|ion)|heretofore|hitherto|thusly|at this juncture|prior to"
)
WORDY_PHRASES = (
    r"in order to|when it comes to|with (?:regard|regards|reference) to|in regard to|in relation to"
    r"|(?:due|owing) to the fact that|in spite of the fact that|despite the fact that"
    r"|in the event that|for the purpose of|at this point in time|at the present time"
    r"|a sufficient number of|in an effort to"
)
FINANCE_WORDS = (
    r"foregone\b(?! conclusion)|recoup(?:s|ed|ing)?\b"
    r"|repa(?:y|ys|id|ying) (?:its|their|the|our) (?:cost|costs|outlay|investment|price)\b"
    r"|carr(?:y|ies|ied|ying) (?:about |roughly |nearly |over |almost |only |just )?[-+]?\d[\d.,]*\s?%"
)
METAPHOR_IMAGES = (
    r"(?:raise[sd]?|raising|lower(?:s|ed|ing)?|clear(?:s|ed|ing)?|set(?:s|ting)?|meet(?:s|ing)?|met)"
    r" the bar|an? (?:high|low|higher|lower) bar"
    r"|(?:puts?|sets?|putting|setting) an? (?:hard |soft )?(?:floor|ceiling)|an? (?:hard|soft)"
    r" (?:floor|ceiling)|yardsticks?|(?:a|the) ladder of|climb(?:s|ed|ing)? the (?:\w+ )?ladder"
    r"|bridg(?:e|es|ed|ing) the gap|an? bridge (?:to|between)|through the lens of"
    r"|(?:a|the) lens (?:on|into|for)|(?:a|the) ledger of|an? window (?:into|onto)"
    r"|paint(?:s|ed|ing)? an? (?:\w+ )?picture|the backbone of|(?:no|an) echo of|a menu of"
    r"|bounc(?:e|es|ed|ing) back|flywheels?|(?:competitive|economic|defensible) moats?"
    r"|(?:tail|head)winds?|pain points?|heavy lifting|in the weeds|boil(?:s|ing)? the ocean"
    r"|doubl(?:e|es|ed|ing) down|lean(?:s|ed|ing)? into|tak(?:e|es|ing) a step back"
    r"|on the same page|rising tide|uphill (?:battle|climb)|(?:key|main|biggest|policy) levers?"
    r"|pull(?:s|ed|ing)? (?:the |a |every |a few )?(?:\w+ )?levers?"
)
CLICHES = (
    r"north star|mov(?:e|es|ed|ing) the needle|low-hanging fruit|double-edged sword"
    r"|tip of the iceberg|lion['’]s share|silver bullet|perfect storm|moving target|slippery slope"
    r"|elephant in the room|wake-?up call|sea change"
)
DOCUMENT_WORDS = r"section|document|post|article|guide|report|essay|chapter|paper|note|README"
SIGNPOSTS = (
    rf"in this (?:{DOCUMENT_WORDS}),? (?:we|I)(?:['’]ll| will| shall| are going to| am going to)"
    rf"|in the (?:next|following) (?:{DOCUMENT_WORDS}),? (?:we|I)\b"
    r"|let(?:['’]s| us) (?:dive|dig|jump) in(?:to)?"
    r"|as (?:we|you)(?:['’]ll| will) see (?:below|later|shortly|in the next)"
    r"|as (?:described|shown|explained|discussed|detailed|outlined) below"
    rf"|this (?:{DOCUMENT_WORDS}) (?:will )?(?:cover|describe|explain|outline|discuss|walk)(?:s|es)?\b"
    r"|(?<![a-z,] )(?:in short|in sum|in summary|to sum up|to summari[sz]e|to wrap up|in closing"
    r"|in conclusion|all in all|taken together)(?=,)"
)
PHRASE_RULES = {
    "stacked-hedge": re.compile(
        r"(?i)\b(?P<hit>(?:may|might|could|can)\s+(?:possibly|potentially|perhaps|conceivably))\b"
    ),
    "nominalization-of": re.compile(rf"(?i)\b(?P<hit>(?:{ACTION_NOUNS})\s+of)\b"),
    "inverted-animacy": re.compile(
        rf"(?i){CLAUSE_START}(?P<hit>{ARTIFACT_SUBJECT}\s+(?:{ANIMATE_PREDICATE}))\b"
        + NOT_A_PREDICATE
    ),
    "inverted-animacy-check": re.compile(
        rf"(?i){CLAUSE_START}(?P<hit>{THING_SUBJECT}\s+(?:(?:that|which)\s+)?"
        rf"(?:{TRANSACTION_VERBS}))\b" + NOT_A_PREDICATE
    ),
    "back-reference": re.compile(
        r"(?i)\b(?P<hit>as (?:discussed|mentioned|noted)\b(?!\s+(?:by|below|further below)\b)"
        r"|as (?:reported|listed)\b(?!\s+(?:by|in)\b)"
        r"|as (?:described|explained|shown) (?:above|earlier|before|previously)\b"
        r"|see above\b"
        rf"|the (?:above|earlier|previous|prior) (?:{DISCOURSE_NOUNS})\b"
        rf"|(?:{DISCOURSE_NOUNS})s? (?:above|from earlier|from before)\b"
        rf"|(?:my|our|your) (?:previous|earlier|last|prior) (?:{DISCOURSE_NOUNS}|instructions?)\b"
        r"|(?:suggested|listed|mentioned|proposed|gave|sent|shared) (?:[\w'’-]+ ){0,4}?earlier\b"
        r"|same (?:\w+ )?open (?:decisions?|questions?|asks?|items?)\b"
        rf"|(?:{DISCOURSE_NOUNS})s?(?: [\w'’-]+){{0,6}}?"
        r" (?:(?:are|is) still|remains?|stays?) open\b"
        r"|(?:stands?|open) as before\b"
        r"|per (?:the|our|my|your)(?: [\w'’-]+){0,2}"
        r" (?:rule|decision|discussion|brief|instructions?)\b)"
    ),
    "stock-emphasis": re.compile(
        r"(?i)\b(?P<hit>honest|honestly|to be (?:honest|frank)|in all honesty|frankly|candidly"
        r"|truth be told|let(?:['’]?s| me) be (?:honest|clear|real|frank|blunt)"
        r"|be honest (?:about|that|with)"
        r"|the honest (?:question|truth)|table stakes|(?:is|was) an? (?:[a-z]+ )?win"
        r"|(?<!\bnot )(?<!n't )(?:this|that|it|which|the (?:[a-z]+ ){0,2}[a-z]+)"
        r" (?:really |still |also )?matters?(?=\s*[.;!])"
        r"|it(?: is|['’]s) (?:important|worth|crucial|essential|vital|critical) (?:to )?"
        rf"(?:{NOTING}){ANNOUNCED_POINT}"
        r"|it (?:should|must) be (?:noted|mentioned|emphasi[sz]ed|stressed|pointed out)"
        rf"|it bears (?:mentioning|noting|repeating)|(?:is|are) worth (?:{NOTING}){ANNOUNCED_POINT}"
        r"|needless to say|it goes without saying|at (?:its|their) core(?=,)|the reality is"
        r"|the real (?:issue|problem|story) is"
        r"|(?<!\bmore )(?<!\bmost )(?:importantly|interestingly|notably|crucially)(?=,))\b"
    ),
    "history-in-document": re.compile(
        r"(?i)\b(?P<hit>(?:was|were|has been|have been) (?:changed|updated|revised|corrected"
        r"|switched) from\b"
        r"|(?:the|an|my|our|this|that) (?:earlier|previous|prior|last|original|old)"
        r" (?:draft|revision|write-?up)\b"
        r"|unlike (?:the|an|my|our) (?:earlier|previous|prior|last|original|old) version\b"
        r"|previously (?:said|stated|reported|read|showed|claimed|listed)\b"
        r"|(?:was|were) previously (?:called|named|listed|reported|stated|shown|given)\b"
        r"|this (?:revision|update|version|edit) (?:fixes|corrects|changes|replaces|removes"
        r"|adds)\b"
        r"|we (?:corrected|fixed|revised|updated) (?:the|an|our) (?:earlier|previous)\b"
        r"|(?:was|were) (?:[^.;,\n]|\.(?=\d)){1,30}, (?:and )?now\b"
        r"|now (?:[\w'’-]+ ){1,6}instead of\b"
        r"|correction:)"
    ),
    "cannot-rule-out": re.compile(
        rf"(?i)\b(?P<hit>(?:{CANNOT}|unable to)\s+(?:be\s+)?rul(?:e|ed)\s+out"
        rf"|(?:we|I)\s+{CANNOT}\s+exclude|{CANNOT}\s+be\s+excluded)\b"
    ),
    "rather-than": re.compile(rf"(?i)(?P<hit>\brather than\b|(?<!\w), not\b|{LESS_ABOUT})"),
    "american-spelling": re.compile(rf"(?i)\b(?P<hit>{BRITISH_SPELLING})\b"),
    "passive-by-agent": re.compile(
        r"(?i)\b(?P<hit>(?:is|are|was|were|be|been|being)\s+"
        r"(?:(?:\w+ly|not|also|often|still|only|then|now|never|always|first|later)\s+){0,2}"
        rf"(?!(?:{NOT_AN_ACTOR_VERBS})\b)(?!un\w+ed\b)(?:\w+ed|{IRREGULAR_PARTICIPLES})\s+by)"
        rf"\s+(?!(?:{NOT_AN_AGENT})\b)(?!(?:\w+ly\s+)?(?-i:[a-z][\w-]*ing)\b)(?=[A-Za-z])"
    ),
    "formal-word": re.compile(rf"(?i)\b(?P<hit>{FORMAL_WORDS})\b"),
    "wordy-phrase": re.compile(rf"(?i)\b(?P<hit>{WORDY_PHRASES})\b"),
    "finance-word": re.compile(rf"(?i)\b(?P<hit>{FINANCE_WORDS})"),
    "metaphor": re.compile(rf"(?i)\b(?P<hit>{METAPHOR_IMAGES}|{CLICHES})\b"),
    "signposting": re.compile(rf"(?i)\b(?P<hit>{SIGNPOSTS})\b"),
}
# Model-tell lists, written from Wikipedia's "Signs of AI writing" and stop-slop (sources.md).
SECTION_LABELS = (
    r"key takeaways?|takeaways|why (?:it|this|that) matters|the bottom line|bottom line"
    r"|final thoughts|closing thoughts|the big picture|wrapping up|key insights?"
    r"|the key insight|in a nutshell"
)
SECTION_LABEL_HEADING = re.compile(rf"(?i)^(?:{SECTION_LABELS})[.:!]?$")
SECTION_LABEL_RUN_IN = re.compile(
    rf"(?i)^\s*(?:\*\*|__)?(?P<hit>(?:{SECTION_LABELS}))"
    r"(?:[.:](?:\*\*|__)|(?:\*\*|__)?[.:])(?=\s|$)"
)

TELL_RULES = {
    "borrowed-jargon": re.compile(
        r"(?i)\b(?P<hit>orthogonal(?:ly)?|inflection points?|quantum leaps?|paradigm shifts?"
        r"|non-?zero (?:chance|risk|possibility|likelihood))\b"
    ),
    "chat-phrasing": re.compile(
        r"(?i)\b(?P<hit>let me know (?:if|whether|what|how|when|which|in)"
        r"|would you like (?:me to|to|a|an|more)|(?:I )?hope this helps"
        r"|feel free to (?:reach out|ask|contact|let|ping)"
        r"|(?:I['’]d be|I would be|I['’]m|I am) happy to|happy to (?:help|iterate|expand|clarify)"
        r"|great question|is there anything else|you['’]re absolutely right)\b"
    ),
}
# Pictographic emoji blocks, BMP emoji shown as pictures, and arrows; the footnote return "↩" passes.
EMOJI = (
    r"\U0001F300-\U0001F64F\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF\U0001FA70-\U0001FAFF"
    r"\u2614\u2615\u26A1\u26D4\u2705\u274C\u2728\u2753-\u2755\u2757\u2B50"
)
ARROWS = r"\u2190-\u21A8\u21AB-\u21FF\u27A1\u27F0-\u27FF\u2900-\u297F\u2B05-\u2B07"
SYMBOL_IN_PROSE = re.compile(rf"[{EMOJI}{ARROWS}]|(?<=\w) -?-> (?=\w)")
INLINE_MATH = re.compile(r"\$[^$\n]+\$")
QUOTATION = re.compile(r'"[^"]{1,300}"|“[^”]{1,300}”')

ANNOUNCING_COLON = re.compile(
    r"(?i)^(?![^:]*\b(?:we|i|you)\b)(?:(?:two|three|four|five|six|several|a few|\d+) [a-z]+"
    r"(?: [a-z]+){0,6}|here(?:'s| is| are)\b(?: [^\s:]+){0,8}|the following(?: [a-z]+)?):(?:\s|$)"
)
ANNOUNCING_QUESTION = re.compile(
    r"(?i)^we (?:asked|wanted to know|looked at|set out to (?:see|learn|test))"
    r" (?:what|whether|how|why)\b[^.]*\.$"
)
CLEFT = re.compile(
    r"(?i)^(?:what\s[^.?!]{3,80}?\b(?:is|was|are|were)\b"
    r"|it (?:is|was) (?:not |also |only |even )?(?:the|this|these|those|his|her|their|its|our"
    r"|my|your|by|in|with|from|because|when|then|something|what|how|why)\b[^.?!]{0,60}?"
    r" (?:that|who)\b)"
)
SERIES_ITEM = r"(?!(?:and|or)\b)[\w'’-]+(?:\s+[\w'’-]+){0,3}"
SERIES = re.compile(
    rf"\b(?P<before_conjunction>{SERIES_ITEM}(?:,\s+{SERIES_ITEM})+),?\s+(?:and|or)\s+[\w'’-]+"
)
# A clause of four or more words before the first comma is the sentence's own, not an opening.
OPENING_PHRASE = re.compile(
    r"(?i)\s*(?:in|on|at|after|before|during|since|for|by|with|when|while|if|although|because"
    r"|however|meanwhile|today|now|then|also|finally|instead)\b(?:\s+[^\s,.]+){0,3},\s+"
)

CAPITALIZED_RUN = re.compile(
    r"(?<![\w'’-])[A-Z]{2,}(?:['’][A-Z]+)?(?:\s+[A-Z]{2,}(?:['’][A-Z]+)?)*(?![\w'’-])"
)
# In capitals these words are emphasis; words that are also acronyms (IT, US, OR) are left out.
ORDINARY_WORDS = (
    "about|above|after|again|against|all|also|always|an|any|anyone|anything|are|as|at|bad|be"
    "|because|been|before|being|below|best|better|between|big|both|but|by|can|can't|cannot|careful"
    "|clear|completely|could|critical|crucial|definitely|did|didn't|different|do|does|doesn't|doing"
    "|don't|done|each|either|else|enough|entire|entirely|essential|even|ever|every|everybody"
    "|everyone|everything|exactly|few|first|for|from|fully|good|great|had|has|have|having|he|her"
    "|here|him|his|how|huge|if|important|into|is|isn't|its|just|key|last|least|less|lot|many|may"
    "|might|more|most|much|must|my|need|needs|never|new|no|nobody|none|nor|not|note|nothing|now|of"
    "|off|once|one|only|our|out|over|own|please|really|required|right|same|seriously|should|so"
    "|some|something|still|stop|such|sure|than|that|the|their|them|then|there|these|they|this"
    "|those|through|to|too|totally|under|until|urgent|very|warning|was|way|we|well|were|what|when"
    "|where|which|while|who|whole|why|will|with|without|won't|wrong|yes|yet|you|your"
)
ORDINARY_WORD = re.compile(rf"(?:{ORDINARY_WORDS})")
ACRONYM = re.compile(r"(?<![\w&'’-])(?P<acronym>[A-Z]{2,6})s?(?![\w&]|-[\dA-Z]|['’][A-Z])")
ACRONYM_DEFINITION = re.compile(
    r"\((?P<short>[A-Z]{2,6})s?\)"
    r"|\b(?P<long>[A-Z]{2,6})s?\s+\((?P<spelled>[A-Za-z][\w'’-]*(?:\s+[\w'’-]+)+)[^)]*\)"
)
UNIVERSAL_ACRONYMS = {"AI", "AM", "API", "CEO", "CPU", "CSS", "CSV", "DR", "EU", "FAQ", "GB", "GPU"}
UNIVERSAL_ACRONYMS |= {"HTML", "HTTP", "HTTPS", "ID", "IT", "JSON", "KB", "LLM", "MB", "ML", "OK"}
UNIVERSAL_ACRONYMS |= {"OS", "PC", "PDF", "PM", "PR", "README", "SQL", "TB", "TL", "TODO", "TV"}
UNIVERSAL_ACRONYMS |= {"UI", "UK", "UN", "URL", "US", "USB", "UTC", "XML"}
ROMAN_NUMERALS = {"II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII"}

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
# A small count in words ("two directions") is prose; ten up, multiples, shares and percents count.
SMALL_NUMBER_WORD = r"(?:one|two|three|four|five|six|seven|eight|nine)"
LARGE_NUMBER_WORD = (
    r"(?:ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty"
    r"|thirty|forty|fifty|sixty|seventy|eighty|ninety"
    r"|(?<!\d )(?:hundred|thousand|million|billion|trillion|(?<!half )(?<!half a )dozen))"
)
NUMBER_WORD = rf"(?:{SMALL_NUMBER_WORD}|{LARGE_NUMBER_WORD})"
SPELLED_COMPOUND = (
    rf"(?<![\w-]){NUMBER_WORD}(?:(?:-|\s+|(?:(?<=hundred)|(?<=thousand))\s+and\s+){NUMBER_WORD})*"
)
SPELLED_NUMBER = re.compile(
    rf"(?i){SPELLED_COMPOUND}(?:(?P<not_a_count>\s+times\b|-?fold\b"
    r"|\s+(?:percent|per cent|percentage points?)\b"
    rf"|\s+(?:in|out of)\s+{SPELLED_COMPOUND}\b)|\b)"
)
LARGE_SPELLED_NUMBER = re.compile(rf"(?i)\b{LARGE_NUMBER_WORD}\b")
MULTIPLE_WITHOUT_NUMBER_WORD = re.compile(
    r"(?i)\b(?:twice|thrice)\s+(?:as|the|that|what|this|its|their|our|his|her|my|your)\b"
    r"|\b(?:doubl|tripl|quadrupl|halv)ed\b|(?<![\w.-])\d+(?:\.\d+)?-?fold\b"
)
YEAR = r"(?:1[6-9]|20)\d\d"
YEAR_ORDINAL_OR_VERSION = re.compile(rf"{YEAR}s?|\d+(?:st|nd|rd|th)|\d+(?:\.\d+){{2,}}")
ENDPOINT = rf"(?!{YEAR}\b)[-+−]?[$€£]?\d[\d.,]*%?"
INTERVAL_PAIR = rf"\s*{ENDPOINT}\s*,(?!\d{{3}}(?!\d))\s*{ENDPOINT}\s*"
NUMERAL = rf"(?:\d+(?:\.\d+)?|(?i:{SPELLED_COMPOUND}))"
CONFIDENCE_LEVEL = rf"{NUMERAL}(?:%|\s+(?i:percent|per cent)\b)"
INTERVAL_LABEL = (
    rf"(?:{CONFIDENCE_LEVEL}\s*(?:[\w-]+\s+)?|(?i:confidence|credible)\s+)(?:CI|(?i:intervals?))\b"
    r"[^.;]{0,25}?"
)
P_COMPARISON = r"(?:[<>=≤≥]|\b(?:below|under|above|over|(?:less|greater|smaller) than))"
SUPPORTING_STATISTIC = re.compile(
    r"(?<![\w.-])(?:[tzF]|t-stat(?:istic)?|z-score|chi-squared?|χ²)"
    r"\s*(?:\(\s*\d[\d.,\s]*\))?\s*(?:=|of|was|is)\s*[-+−]?\d"
    rf"|\b{NUMERAL}\s*(?:df|degrees of freedom)\b|\bdf\s*=\s*\d"
    rf"|(?<![\w.-])p\s*{P_COMPARISON}\s*0?\.\d"
    rf"|\bp-?values?\b[^.;\d]{{0,20}}?(?:{P_COMPARISON}|\b(?:of|was|is|were|are))\s*0?\.\d"
    rf"|[\[(]{INTERVAL_PAIR}[\])]"
    rf"|{INTERVAL_LABEL}{ENDPOINT}\s*(?:to|and|–|-)\s*[-+−]?\d"
    r"|\d\s*(?:±|\+/-|(?i:plus or minus))\s*\d"
)
LABELED_BRACKET_INTERVAL = re.compile(rf"{INTERVAL_LABEL}\[{INTERVAL_PAIR}\]")
DECIMAL_RATE = r"(?<![\d.])[-+−]?0?\.\d+(?!\.\d)"
RATE_CONTRAST = re.compile(
    rf"{DECIMAL_RATE}[^.;]*?\b(?:against|versus|vs\.?|while|compared (?:with|to))(?!\w)"
    rf"[^.;]*?{DECIMAL_RATE}"
)
ARITHMETIC = re.compile(r"\d[\s)]*[=×*][\s(]*[-+−$€£]?\d|=\s*[-+−$€£]?\d")

# Shape rules from the owner's document feedback: worded measurements, staccato runs, PR names.
MEASURE_NUMBER_WORD = r"(?:two|three|four|five|six|seven|eight|nine)"
MEASURE_UNIT = (
    r"(?:cents?|dollars?|euros?|points?|basis points?|degrees?|seconds?|minutes?|hours?|days?"
    r"|weeks?|months?|years?|meters?|miles?|grams?|kilograms?|pounds?)"
)
FRACTION_WORD = r"(?:half|halves|third|thirds|quarter|quarters|fifth|fifths|tenth|tenths)"
# A fraction word is a share only before "of", a comparative, a preposition or punctuation.
AFTER_A_SHARE = (
    r"(?=\s+(?:of|as|than|more|less|fewer|sooner|later|faster|slower|higher|lower|longer|shorter"
    r"|at|in|on|for|from|by)\b|\s*[,.;:!?)]|\s*$)"
)
MEASURED_NUMBER_WORD = re.compile(
    rf"(?i)\b(?:{MEASURE_NUMBER_WORD}\s+{MEASURE_UNIT}\b"
    r"|(?<!\bat )one\s+(?:cent|dollar|euro|point)\b(?!\s+of\b)"
    rf"|(?:a|one|two|three|four)[- ]{FRACTION_WORD}\b{AFTER_A_SHARE}"
    r"|half (?:a|an)\b(?!\s+dozen)|half (?:of|as|the)\b"
    r"|(?:than|about|nearly|roughly|almost|over|under) half\b"
    r"|(?:one|two|three) and a half\b"
    rf"|(?:under|over|nearly|roughly|almost)\s+{MEASURE_NUMBER_WORD}\b(?!\s+(?:of|in|or|and|to)\b)"
    rf"|by\s+{MEASURE_NUMBER_WORD}(?=\s*[,.;:!?)]|\s*$))"
)
STACCATO_DETERMINERS = {"a", "an", "the", "each", "every", "one", "another", "some", "most", "no"}
STACCATO_DETERMINERS |= {"our", "their", "its", "this", "that", "these", "those"}
PULL_REQUEST_FILE_NAME = re.compile(r"(?i)(?:^|[_-])(?:pr|cr)[-_]?(?:description|body)\b")
