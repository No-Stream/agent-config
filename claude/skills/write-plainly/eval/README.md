# Lint false-flag check

`false_flags.py` runs every rule in the three write-plainly linters (`lint_prose.py`, sloplint and slop-guard) over careful human prose and over model-written drafts on the same topics, then prints how often each rule fires on each side. A rule that fires more often on the human side flags careful writing more than it flags model writing, so if the rule exists to catch model habits, its message should say "check" rather than "fix", or the rule should go. The check exists because published AI-tell rule sets often fire more on good human technical writing than on model output.

## Running it

From the repo root:

```sh
uv run claude/skills/write-plainly/eval/false_flags.py > false-flags.md
```

It needs `uv`, `git` and `sloplint` on the PATH (sloplint is a Ruby gem). The script declares its own Python dependency (trafilatura, for turning HTML into markdown), and slop-guard runs through `uvx` at the version `check-prose.sh` uses, so nothing else needs installing. The first run fetches the web pages and a pinned commit of the `bheijden/slop` repository into `.cache/`, about 60 MB in all. Later runs reuse the cache; delete a file or directory there to fetch it again.

The cache is gitignored and must stay that way. The human texts are other people's copyrighted work, kept locally only to measure the linters. Each run writes `.cache/rights.tsv` with the source, date and known rights status of every public text.

`--private` adds the corpora listed in `.private/eval/corpora-private.toml` at the repo root (a gitignored file) and writes the result to `.private/eval/false-flags-private.md` instead of printing it. Use it for prose that must not be published, such as your own work documents.

The tests in `tests/` run the script end to end on small fixture texts, with stand-in `sloplint` and `uvx` executables:

```sh
uv run --no-project --with pytest --with trafilatura==2.3.1 python -m pytest claude/skills/write-plainly/eval/tests
```

## Corpora and the table

`corpora.toml` lists the corpora. The human side has seven long-form explanatory web pages that `../sources.md` names as models (two each by Karpathy, Amodei and METR, plus Google's guide to paragraphs) and the human halves of the `bheijden/slop` matched corpus. The agent side is that corpus's model halves. Each of its 24 pairs is one topic written twice: once by a person before 2022, and once by `claude-opus-5` from the same topic, audience and points, without seeing the human text. The pairs cover twelve registers, with three pairs each for academic, forum, government, journalism, literary and techdoc writing and one pair each for six more.

For each rule that fired at least once, the main table gives hits per 1,000 words on each side and their ratio. It also marks whether the human rate is higher and counts the texts on each side with at least one hit. A word is what `lint_prose.py` counts as one: a run of letters and digits, which may continue across an apostrophe, hyphen, period or comma ("don't", "well-known", "3.5"). Table pipes and list bullets are not words, and "A/B" counts as two. The second table splits the same rates by corpus and register: the `bheijden-slop all` columns are the matched comparison, and the techdoc and academic columns are the registers closest to what this skill is used for. The output ends with the enabled rules that never fired, which these corpora say nothing about.

slop-guard is counted by its per-category hit counts (the `--counts` view), so its rows are categories such as `slop_words` and `structural`, not individual words. sloplint runs with its default rules, including the one `check-prose.sh` skips (see Results), so that rule's rate stays visible. slop-guard runs with `../slop-guard.jsonl`, so a rule removed from that file no longer shows up here.

## What it does not show

The numbers are counts of pattern matches. They say how often a rule fires on each kind of text. Whether a reader would agree that a flagged sentence should change is a separate question, which only reading the flagged text answers. A rule can fire more on human prose and still enforce a style you want: the skill bans em dashes by preference, even though careful writers use them. These limits matter when you read the table:

- The corpora are small. The matched corpus has three pairs per register in its main registers, about 3,000 words per side, so one text can move a rate several times over. Hits cluster in a few texts, so read the docs columns beside the rates.
- One model wrote every agent text, prompted one way. Other models, other prompts or real agent drafts from your own work can fire rules at different rates.
- The two sides differ in more than authorship. The seven web pages (about 33,000 words) have no agent counterpart, and the matched corpus is plain text with no headings, bold or lists. Rules about markdown structure can therefore fire only on the human web pages, and their agent rate of zero is not evidence. The corpus table counts the texts with markdown structure on each side. HTML conversion can also add or drop structure, such as a bold lead-in or a caption, so when a markdown rule's rate looks wrong, read the converted page in `.cache/pages/`.
- A third of the matched corpus's human texts were published before 1930, all in non-technical registers: three literary texts and one each of biography, how-to, letters, review and travel. Prose that old differs from the technical documents this skill is for.
- `lint_prose.py` and the modules it imports (`lint_prose_markdown.py`, `lint_prose_document.py` and the word lists in `lint_prose_patterns.py`) change over time. The output header records one sha256 of all four files, so compare runs only when the hashes match. The tables below name the hash each run used.

## Results

The table comes from runs on 2026-11-20 with `lint_prose.py` and `lint_prose_patterns.py` at sha256 `c5638c2cb0e3`, sloplint 0.10.0 and slop-guard 0.5.0. slop-guard ran with the version of `slop-guard.jsonl` from before the changes below, so the rules they removed still have rates. The three-item part of `structural` is the difference between that run and a run with the current file. The human side has 56,689 words and the agent side 23,484.

Each rule falls into one of two groups, and only tell rules can be demoted:

- House-style rules encode this skill's own preferences: no em dashes, no dashes as pauses, few numbers in body prose, paragraph shape and sentence length. The markdown rules from the skill's Format section are house style too: no bold run-in labels or bold lead-ins, bold only for a decision or a label, sentence-case headings and no thin top-level sections. They stay whatever their human rate, and their rates are reported for information. A rule from another linter that contradicts one of them is removed whatever its rates.
- Tell rules exist to catch model habits. A tell rule that fires more often per 1,000 words on the human side than on the agent side, on at least three human texts, gets an advisory "Check:" message or is removed. The three-text minimum exists because two texts against none is within noise for corpora this small, and it is provisional until the skill's owner confirms it. Without it, `stacked-hedge` would get a "Check:" message, `check-prose.sh` would also skip sloplint's `same-determiner-chain` and `stands-serves-as`, and slop-guard's `pithy_fragment` would be turned off.

Two tell rules are about markdown structure: slop-guard's `bullet_density`, and the bold-header and bullet-run checks in its `structural` rule. They cannot fire on the matched corpus, which is plain text, so they are meant to be judged on the passages that the pairwise evaluation in `pairwise/` generated, as "Markdown rules on generated passages" describes. The public passages have no heading, bold or list, so neither rule is judged yet, and both stay on.

Rates are hits per 1,000 words. "Human" is every human text, "agent" is the model halves of the matched corpus, and "matched human" is the human halves written on the same topics. The texts columns count texts with at least one hit.

| rule | linter | group | human | agent | matched human | human texts | agent texts | outcome |
|---|---|---|---|---|---|---|---|---|
| `slop_words` | slop-guard | tell | 1.01 | 0.47 | 0.76 | 15/31 | 9/24 | removed |
| `slop_phrases` | slop-guard | tell | 0.55 | 0.13 | 0.46 | 14/31 | 2/24 | removed |
| `structural`, three-item lists | slop-guard | tell | 0.49 | 0.21 | 0.59 | 17/31 | 4/24 | turned off |
| `tone` | slop-guard | tell | 0.07 | 0.00 | 0.04 | 3/31 | 0/24 | removed |
| `nominalization-of` | lint_prose | tell | 0.30 | 0.17 | 0.30 | 8/31 | 4/24 | advisory |
| `impact-noun-bare` | sloplint | tell | 0.11 | 0.00 | 0.08 | 4/31 | 0/24 | skipped by `check-prose.sh` |
| `contrast_pairs` | slop-guard | tell | 0.44 | 0.51 | 0.63 | 16/31 | 9/24 | kept |
| `setup_resolution` | slop-guard | tell | 0.09 | 0.13 | 0.08 | 5/31 | 3/24 | kept |
| `not-just-x-but-y` | sloplint | tell | 0.05 | 0.17 | 0.08 | 3/31 | 2/24 | kept |
| `exact-exactly` | sloplint | tell | 0.04 | 0.09 | 0.04 | 2/31 | 1/24 | kept |
| `punch-sentence` | sloplint | tell | 0.02 | 0.09 | 0.04 | 1/31 | 2/24 | kept |
| `stacked-hedge` | lint_prose | tell | 0.05 | 0.00 | 0.04 | 2/31 | 0/24 | kept, two texts |
| `same-determiner-chain` | sloplint | tell | 0.04 | 0.00 | 0.04 | 2/31 | 0/24 | kept, two texts |
| `stands-serves-as` | sloplint | tell | 0.04 | 0.00 | 0.08 | 2/31 | 0/24 | kept, two texts |
| `pithy_fragment` | slop-guard | tell | 0.04 | 0.00 | 0.04 | 2/31 | 0/24 | kept, two texts |
| `not-x-but-y` | sloplint | tell | 0.00 | 0.21 | 0.00 | 0/31 | 5/24 | kept |
| `isnt-x-its-y` | sloplint | tell | 0.00 | 0.21 | 0.00 | 0/31 | 3/24 | kept |
| `no-x-no-y` | sloplint | tell | 0.00 | 0.13 | 0.00 | 0/31 | 2/24 | kept |
| `em-dash` | lint_prose, sloplint | house | 2.06 | 1.36 | 1.39 | 11/31 | 3/24 | kept |
| `em-dash-overuse` | sloplint | house | 0.18 | 0.09 | 0.08 | 4/31 | 2/24 | kept |
| `em_dash` | slop-guard | house | 0.02 | 0.09 | 0.04 | 1/31 | 2/24 | kept |
| `dash-substitute` | lint_prose | house | 1.25 | 0.13 | 1.69 | 14/31 | 1/24 | kept |
| `number-density` | lint_prose | house | 0.93 | 0.26 | 1.01 | 16/31 | 5/24 | kept |
| `short-paragraph-run` | lint_prose | house | 0.26 | 0.04 | 0.42 | 10/31 | 1/24 | kept |
| `long-sentence` | lint_prose | house | 0.99 | 0.68 | 0.76 | 15/31 | 11/24 | kept |
| `complex-sentence` | lint_prose | house | 4.04 | 4.43 | 3.38 | 25/31 | 23/24 | kept |
| `paragraph_cv` | slop-guard | house | 0.25 | 0.98 | 0.59 | 14/31 | 23/24 | removed, contradicts the paragraph minimum |
| `paragraph_balance` | slop-guard | house | 0.02 | 0.00 | 0.04 | 1/31 | 0/24 | removed, contradicts the paragraph minimum |
| `bold-run-in` | lint_prose | house | 1.68 | 0.00 | 0.00 | 6/31 | 0/24 | kept |
| `structural`, bold headers and bullet runs | slop-guard | tell | 0.23 | 0.00 | 0.00 | 4/31 | 0/24 | not judged, no bold or list in the passages |
| `bold_bullet_list` | slop-guard | house | 0.21 | 0.00 | 0.00 | 5/31 | 0/24 | kept |
| `title-case-heading` | lint_prose | house | 0.05 | 0.00 | 0.00 | 3/31 | 0/24 | kept |
| `bullet_density` | slop-guard | tell | 0.05 | 0.00 | 0.00 | 3/31 | 0/24 | not judged, no list in the passages |
| `thin-h2-section` | lint_prose | house | 0.05 | 0.00 | 0.00 | 3/31 | 0/24 | kept |
| `intrasentence_keyword_bold` | slop-guard | house | 0.02 | 0.00 | 0.00 | 1/31 | 0/24 | kept |

Nine more rules fired on a single text, too few to read: sloplint's `not-by-x-but-by-y`, `actually-not-x`, `impact-verb`, `real-x-real-y` and `is-is` and slop-guard's `ai_disclosure` on one human text each, and sloplint's `short-run`, `notice-what` and `thats-how-x` on one agent text each. Most of sloplint's default rules, two in five of slop-guard's categories and `lint_prose.py`'s `heading-density` never fired, so these corpora say nothing about them; the last section of the output lists them.

### Changes

- slop-guard's word list (`SlopWordRule`) is removed from `slop-guard.jsonl`. The human hits are common words in their usual sense, most often "societal", "crucial", "paradigm" and "robust". The two Amodei essays carry over half the human hits, and the rule still leans human on the matched corpus alone.
- slop-guard's stock-phrase rule (`SlopPhraseRule`) is removed. Most human hits are "in addition" and "in other words", written as ordinary transitions or as "in addition to". The rule also matches inside longer words ("gain additional" counts as "in addition", and "AI can also" as "I can also"). Without those matches the human rate is still several times the agent rate (0.48 against 0.09), so this bug does not explain the gap.
- slop-guard's tone rule (`ToneMarkerRule`) is removed. Its human hits are "As mentioned above" in a research post, "As mentioned in the introduction" in an essay and "Certainly," in a memoir, plus "areas mentioned", which is the same substring bug. It is the closest call among the tell-rule changes. It sits exactly at three texts, and the agent texts are essays, which cannot show the chat phrasing the rule mostly looks for ("would you like", "let me know if").
- slop-guard's `structural` rule keeps its bold-header and bullet-run checks, but its three-item list check is off: `triadic_record_cap` and `triadic_penalty` are 0, and `triadic_advice_min` is set higher than any document reaches. Its hits are plain lists of three, such as "film, television, and music".
- slop-guard's paragraph rhythm rules (`ParagraphBalanceRule` and `ParagraphCVRule`) are removed as house-style conflicts. They ask for a mix of short and long paragraphs, which contradicts the skill's minimum of four sentences per body paragraph, and `paragraph_cv` fired on nearly every agent text.
- `nominalization-of` in `lint_prose.py` now starts its message with "Check:" and calls itself advisory. Its hits are real nominalizations. Some are what the rule is for ("The creation of this PEP was prompted by"), and some are fine as written ("an implementation of a standard algorithm"), so the rule stays as a prompt to look.
- `check-prose.sh` runs sloplint with `--ignore impact-noun-bare`. Every human hit is research wording, such as "the impact of AI on developer productivity". sloplint's own rationale for the rule calls "the impact of X on Y" ordinary research wording, yet the rule fires on that form.
- Two false positives in `lint_prose.py` are fixed. `inverted-animacy` read "a substantial number said" as an artifact speaking, so it now matches "numbers" ("the numbers tell us") and not "number". `coined-label` read the pronoun in "every plan I have" as a label named "I". These were the only hits of either rule on either side, so neither rule fires on these corpora now and neither has a row in the table.

A run with the current `slop-guard.jsonl` shows the five removed slop-guard categories gone and `structural` firing only on the four web pages with bullet runs or bold headers.

The house-style rules fire more often on careful human prose, as expected. `dash-substitute` (spaced hyphens and en dashes in blog posts, journalism and forum comments, and double hyphens in older printed texts), `short-paragraph-run` and `number-density` all fire several times as often on the human side. `number-density` counts spelled-out numbers from ten up as well as digits; counting digits alone, it would flag one agent text instead of five. The em dash rate is nearly equal on the matched corpus. `complex-sentence` is the most frequent rule on both sides and does not separate them.

One kept tell rule flips between the two comparisons: `contrast_pairs` fires more often on the matched human halves than on the agent texts, and less often over all human text. It stays because the triage compares the whole human side.

### Markdown rules on generated passages

The pairwise evaluation generated one passage per task and pipeline, and two of its tasks are public. The 10 graded passages on those two tasks (2,320 words) contain no markdown structure, because the prompt asks for body text with no heading. `bullet_density` and slop-guard's bold-header and bullet-run checks never fire on them, so these rules stay unjudged until a source of agent-written documents with markdown structure is added. The human side for these rules is the seven web pages, since no other human text has markdown structure. The bold and heading rules in `lint_prose.py` are house style and need no judgment.

### Threats to these results

Beyond the general limits in "What it does not show", four threats bear on these changes:

- The corpora are small. The matched corpus has at most three pairs per register, about 1,000 words per text, so one text can move a rate several times over. Hits cluster: the two Amodei essays carry more than half of the human `slop_words` hits.
- One model wrote every agent text, `claude-opus-5` prompted one way. Other models, other prompts and real agent drafts can fire these rules at different rates.
- The rates are counts of matches. They do not say whether a reader would want a flagged sentence changed. The notes under "Changes" quote the hits that were read for this triage.
- The matched agent texts are plain text, and the public generated passages have no markdown structure, so no markdown tell rule is judged. The human side's 33,024 words of web pages have no agent counterpart on the same topics or at their length. Each tell-rule change above points the same way on the matched corpus alone, where both sides are plain text on the same topics, though `tone` and `impact-noun-bare` fire on only one matched human text each.

## Rules from the owner's corrections

The skill's owner collected the writing corrections they had given to models and merged them into rules. The rules below implement the ones a pattern can catch, as new rules in `lint_prose.py` and a wider `coined-label`. The table comes from a run on 2026-11-22 with the four `lint_prose*.py` files at sha256 `25ca59e44102`, on the same corpora as the table above. Each rule was also run on the model text the owner had corrected; that text and those results stay private.

The owner gave these rules, so they are house style and stay even where careful human writers break them. A rule that fires on three or more human texts, or whose verdict depends on the reader, has a message that starts with "Check:". Most of the corrections were about chat and status messages: labels coined during the work, pointers back to an earlier message, acronyms nobody defined. The agent texts here are essays written from a brief, which rarely do these things, so an agent rate of zero means the rule stays quiet on essays. It says nothing about how often the rule catches model habits in messages.

| rule | what it flags | message | human | agent | human texts | agent texts |
|---|---|---|---|---|---|---|
| `coined-label` | labels and IDs coined during the work ("route C", "phase-3", "task #42", `LIB-12`, "C3") | check | 0.35 | 0.00 | 4/31 | 0/24 |
| `back-reference` | pointers to earlier text ("as discussed", "in my previous message", "the fix above", "per the rule", "the two questions about parking are still open") | check | 0.14 | 0.00 | 4/31 | 0/24 |
| `announcing-sentence` | a sentence that only names what follows ("Two changes help wheelchair users:", "We wanted to know whether late opening helps.") | check | 0.02 | 0.00 | 1/31 | 0/24 |
| `stock-emphasis` | "honest", "honestly", "frankly", "to be honest", "table stakes", "is a big win", "and that matters.", and the announcing phrases "it is important to note", "it should be noted", "it's worth noting", "needless to say", "at its core", "the reality is", "let me be clear" and "Importantly," | fix | 0.07 | 0.21 | 3/31 | 5/24 |
| `history-in-document` | edit history ("was changed from", "the earlier draft", "now counts loans instead of visits", "this revision corrects") | fix | 0.00 | 0.00 | 0/31 | 0/24 |
| `all-caps-emphasis` | ordinary words in capitals ("NOT", "VERY", "IMPORTANT FOR EVERYONE") | fix | 0.09 | 0.00 | 2/31 | 0/24 |
| `american-spelling` | British spellings from a closed list ("colour", "organise", "centre", "licence", "modelling") | fix | 0.56 | 2.04 | 11/31 | 15/24 |
| `rather-than` | "rather than", a ", not" contrast after a number, bracket or inline code, and "less about X and more about Y" when a noun is the subject (sloplint flags the "It's less about" form) | check | 0.11 | 1.11 | 5/31 | 12/24 |
| `cannot-rule-out` | "cannot be ruled out", "can't rule out", "we cannot exclude" | fix | 0.00 | 0.00 | 0/31 | 0/24 |
| `cleft-sentence` | "What keeps the queue short is the second desk.", "It is the narrow door that causes the delay." | check | 0.14 | 0.72 | 7/31 | 11/24 |
| `triad-density` | the third and later sentence in a section with an "A, B and C" series | check | 1.62 | 2.60 | 24/31 | 17/24 |
| `tldr-shape` | a TL;DR, Summary or Abstract section of more than eight sentences or four numbers | fix | 0.02 | 0.00 | 1/31 | 0/24 |
| `supporting-statistic` | a sentence outside the back matter quoting a test statistic, degrees of freedom, a p-value, an interval, a plus-minus spread or two decimal rates set against each other ("a t of 3.10 on 14 df", "4.0% [2.5%, 5.5%]", "0.92 against 0.97") | check | 0.04 | 0.00 | 1/31 | 0/24 |
| `undefined-acronym` | the first use of an acronym that comes before its definition | check | 1.50 | 0.55 | 20/31 | 9/24 |
| `inverted-animacy-check` | a thing that earns, holds, buys, wins, crowds or rescues ("The window display earns most of the new members.") | check | 0.00 | 0.04 | 0/31 | 1/24 |

The human hits were read. `coined-label` fires on product, chip and robot names (R1, V3, H800, PR2), on "L2 regularization" and on two real "described in #3" pointers. `back-reference` fires on cross-references inside long essays ("as noted above"), which the advisory message leaves the writer free to keep. `undefined-acronym` fires mostly on well-known abbreviations outside its skip list (SGD, RNN, IRS, BBC), which is why it is advisory. The `all-caps-emphasis`, `tldr-shape` and `announcing-sentence` hits are real instances: capitals for emphasis in a nineteenth-century biography, a 50-sentence Summary section, and "A few tips and tricks for this step:" before a list. Every `american-spelling` hit is a British spelling, and the rule fires on more model texts than matched human texts: the model wrote "behaviour" and "licence" even in technical documents whose human halves use none. Its message says fix although it fires on more than three human texts, because every hit is a British spelling, which the owner's rule changes in any text. `history-in-document` and `cannot-rule-out` never fired: these corpora have no revised drafts and no statistical readouts. Both `supporting-statistic` hits are in one post, a pair of log probabilities and a pair of screen coordinates, written as bracketed pairs.

How the rules decide:

- `coined-label` reads label words followed by a number or a capital letter ("decision 7", "Track C's", "phase-3"), tracker IDs (`LIB-8.3`), word-and-hex IDs (`req-7c21be`), hash numbers and short letter-and-digit codes. Inside backticks it reads only tracker IDs, hex IDs and hash numbers, because a short code there is usually a variable name such as `W1`. An ID passes when it sits in parentheses right after a plain description ("the roof repair (LIB-12)"), and so do its later uses. Standard prefixes (UTF, SHA, ISO and a few more), common public codes (S3, Q3, P0, A100) and "#1" as a rank also pass.
- `undefined-acronym` looks for an all-caps word of two to six letters before any "(ACR)" or "ACR (spelled out)" in the document. A parenthesis after the acronym defines it only when its words spell the acronym, by their initials (with or without small words such as "of" and "the") or by their capitals. So "NASA (National Aeronautics and Space Administration)" defines NASA, and "NOT (under any circumstances)" defines nothing. It skips about 40 universal ones (API, URL, JSON, GPU and others), Roman numerals, ordinary words in capitals, code and link text.
- `all-caps-emphasis` flags a run of capitals that contains one of about 180 common words that are not also acronyms; an acronym the document defines, in the same way `undefined-acronym` reads definitions, passes ("The WHO (World Health Organization)").
- `triad-density` allows two sentences with a three-item series per H1 or H2 section, as the owner asked, and counts paragraphs, captions and footnotes. It reads the whole comma series and counts it only when it has exactly three items, so a list of four or more does not count. It skips an opening phrase of up to four words that starts with a word such as "in", "after", "when" or "however" and ends at the first comma. So "In winter, the branch opens late and closes early" holds a pair, while "In winter, the branch lends sledges, skates and scarves" counts. A list that starts right after such a word is read as the opening phrase and missed ("In Paris, Rome and Berlin, the museums open late"). slop-guard's three-item check stays off, because it flags single plain lists.
- `american-spelling` reads a closed list of British spellings: -ise and -isation forms of 37 verbs ("organise", "optimisation"), -our words, "centre" and "metre", "licence" and "defence", "modelling" and "labelled", "analyse", "programme", "judgement" and "ageing". It never matches a bare -ise ending, so "advertise", "exercise" and "precise" pass, and so do "analyses" and "catalogue", which are American spellings too.
- `supporting-statistic` reads every paragraph and list item outside the back matter, the summary included, since a summary carries no statistical detail either. Two decimal rates count only when a contrast word joins them: against, versus, vs., while, compared with or compared to. Threshold settings ("an alarm at humidity 0.05 and 0.2"), a headline change ("rose from 0.81 to 0.84") and a line of arithmetic pass. A range counts as an interval only after a confidence level or qualifier ("95% CI", "a 95% Wilson interval", "a credible interval"), so "CI takes 10 to 15 minutes" passes. A pair of years ("(2023, 2024)") and one number with a thousands separator ("($14,200)") are never read as an interval's endpoints. A bracket of whole numbers reads as a citation ("[3, 7]") unless an interval label comes before it ("the 95% confidence interval is [12, 18]"). A cap of one number per body sentence or per body paragraph would flag more careful human prose than `number-density` does (1.61 and 1.46 hits per 1,000 human words, on 17 and 19 of 31 texts). A cap of two per sentence flags nothing that `number-density`'s cap of two per paragraph does not already flag.
- `rather-than` leaves the word-comma-not form ("open, not closed") to slop-guard's `contrast_pairs`, which already flags it.
- The phrase and sentence rules skip double-quoted spans, which hold someone else's words. `coined-label` and `undefined-acronym` read quoted text, because a quoted button or ticket name is still an unexplained ID.

No rule was dropped.

## Rules for model tells from public catalogs

The rules below catch model habits that sloplint and slop-guard, as `check-prose.sh` runs them, do not catch. Their word and phrase lists, in `lint_prose_patterns.py`, come from Wikipedia's "Signs of AI writing" and "Words to watch" and the phrase list of hardikpandya/stop-slop (see `../sources.md`). The rules marked house style enforce rules the skill already states: cut intensifiers and padding, write in active voice and literally, prefer the everyday word, open with the information instead of a signpost, and use no emojis or arrows in prose. `finance-word` comes from the owner's corrections. `stock-emphasis` also flags the announcing phrases the skill tells writers to cut, and `rather-than` also flags "less about X and more about Y"; both rules' rows are in the table above. The plain-language lists come from the Federal Plain Language Guidelines and digital.gov, and the stock images and idioms from "Words to watch" and stop-slop. The table comes from a run on 2026-11-22 with the four `lint_prose*.py` files at sha256 `25ca59e44102`, on the same corpora as the tables above.

| rule | what it flags | message | group | human | agent | human texts | agent texts |
|---|---|---|---|---|---|---|---|
| `borrowed-jargon` | "orthogonal", "inflection point", "paradigm shift", "a non-zero chance" | check | tell | 0.04 | 0.04 | 2/31 | 1/24 |
| `chat-phrasing` | "let me know if", "would you like me to", "I hope this helps", "happy to iterate" | check | tell | 0.00 | 0.00 | 0/31 | 0/24 |
| `section-label` | a heading, bold run-in or colon label such as "Key takeaways", "Why it matters." or "Bottom line:" | fix | tell | 0.00 | 0.00 | 0/31 | 0/24 |
| `intensifier` | the third and later intensifier in an H1 or H2 section ("very", "extremely", "incredibly", "truly") | check | house | 1.45 | 0.17 | 12/31 | 3/24 |
| `passive-by-agent` | a passive that names its actor ("the shelves were built by volunteers") | check | house | 0.67 | 0.89 | 14/31 | 13/24 |
| `wordy-phrase` | "in order to", "when it comes to", "with regard to", "due to the fact that", "in the event that" | check | house | 0.21 | 0.00 | 5/31 | 0/24 |
| `formal-word` | a formal word with an everyday synonym ("utilize", "commence", "ascertain", "prior to") | check | house | 0.04 | 0.00 | 2/31 | 0/24 |
| `metaphor` | an image or stock idiom ("raises the bar", "a yardstick", "a ledger of", "through the lens of", "bounce back", "low-hanging fruit") | check | house | 0.02 | 0.04 | 1/31 | 1/24 |
| `signposting` | "in this section, we will", "let's dive in", "as shown below", and recap openers ("In summary,", "In short,", "All in all,") | check | house | 0.09 | 0.04 | 4/31 | 1/24 |
| `finance-word` | "foregone", "recoups", "repays its cost", "carries 30%" | check | house | 0.00 | 0.00 | 0/31 | 0/24 |
| `symbol-in-prose` | an emoji or arrow in prose or a heading ("📚 Hours", "the queue fell → the desk worked", "a miss -> a slow read") | check | house | 0.00 | 0.00 | 0/31 | 0/24 |

Each list started from the catalogs, and an entry stayed only if it fired rarely on the human texts here. For the plain-language rules, "in terms of" ("performance in terms of task length"), "with respect to" (a gradient with respect to a parameter), "on the basis of" and "in the context of", which careful writers use in their plain sense, were dropped, and so were the noun "utilization", "blind spot", "playbook", "unpack", "recipe for" and "ecosystem". Phrases sloplint already flags are left to it: "underscores", "tapestry", "testament", "vibrant", "Here's what nobody tells you", "read that again", "Here's the kicker:" and "The takeaway:".

The tell rules were also checked on text their lists were not written from: 339,966 words of model text the owner had corrected and 14 public engineering and research pages (54,199 words) outside these corpora. A tell rule stayed only if it caught problems in that model text without flagging the held-out human pages more often than the house-style rules do. `chat-phrasing` (9 true hits), `section-label` (4) and `borrowed-jargon` (6, all "orthogonal" meaning "unrelated") passed. Nine rules were removed: `vague-quantifier` caught nothing and fired on 5 of the 14 human pages, all 12 `ai-vocabulary` hits were noise, and `promotional-word`, `era-framing`, `stock-concession`, `dead-transition`, `whether-range`, `insight-teaser` and `engagement-bait` caught nothing in the model text.

The human hits were read. `stock-emphasis` fires on three human texts, and its message says fix because every human hit is an announcing phrase the skill cuts in any text ("It's worth noting that", "It goes without saying that", "It should be noted in this context that", "Importantly,"), the same reasoning as for `american-spelling`. `intensifier` fires eight times as often on the human side, and "very" makes up 74 of its 86 hits; it stays because the skill asks writers to cut intensifiers whoever writes them, and it says "check" because one or two strong adverbs per section are often earned. Ten of the twelve `wordy-phrase` hits are "in order to", which the skill names as padding, and the other two are "when it comes to". Each reads the same with the short form, but the rule is advisory because "in order" can mean a sequence ("written in order to disk"). The `signposting` hits are recaps and section signposts in long essays ("In summary,", "In conclusion,", "So in this section, I'll"), which is why it is advisory. `formal-word` fires on "ameliorate" and "Prior to", and `metaphor` on "pulling a few key levers" in an essay and "the backbone of a liberal education" in an agent text. `passive-by-agent` fires at about the same rate on both sides; "by" followed by a means ("by replacing two tiles"), a sort key ("sorted by date") or a feeling ("surprised by") is not an actor and passes.

Four of the new rules (`chat-phrasing`, `section-label`, `finance-word` and `symbol-in-prose`) never fired on these corpora, so the corpora say nothing about their false-flag rate. The agent texts are essays written from a brief, and those rarely carry chat phrasing or section labels, so an agent rate of zero says nothing about how often the rules catch model habits in documents. Because the lists were pruned on these same corpora, the human rates above are lower than they would be on new text.

Three checks were tried and left out. A rule for a phrase repeated three or more times would contradict the skill's rule to keep one term per concept, and it fires mostly on careful prose: sloplint's off-by-default `phrase-echo` fires 1.66 times per 1,000 words on the human texts against 0.30 on the agent texts (21 of 31 human texts, 4 of 24 agent). A rule against a size in words with no number ("improved considerably") would contradict the skill's Evidence and numbers section, which keeps the numbers in tables and asks the prose for the size in plain words. A count of bold spans per word adds nothing to `bold-run-in` and slop-guard's bold checks, which flag each bold lead-in and inline keyword, and on the human pages it would flag Karpathy's recipe post (1.03 bold spans per 100 words), whose bold lead-ins `bold-run-in` already flags.

How the new rules decide:

- The tell rules read paragraphs, list items, captions, footnotes and headings, and skip double-quoted spans. Every phrase rule reads a paragraph with its line breaks joined, so a phrase wrapped across two lines still matches. `section-label` reads a heading's whole text, or the start of a paragraph or list item, so "the bottom line of the form" passes.
- In `stock-emphasis`, "it is important to note" and "worth noting" need "that", "how", "why" or a punctuation mark after them, so "it is critical to note each failed request" passes, and "at its core" counts only before a comma.
- `formal-word` reads "utilize" only as a verb and "endeavor" only before "to", so "resource utilization" and "a long endeavor" pass. `finance-word` passes "a foregone conclusion", reads "repays" only before "its cost" or a similar object, and "carries" only before a percentage, so "the borrower repays the loan" and "the van carries 30 boxes" pass.
- `metaphor` reads each image in its figurative frame only: "bar" after "raise", "lower", "clear", "set" or "meet", or as "a high bar"; "floor" and "ceiling" after "put a" or "set a", or as "a hard floor"; "lens" in "through the lens of"; "ledger" in "a ledger of"; "lever" as "key levers" or "pull ... levers". So "the café has a bar and a ledger" and "the jaw works as a lever" pass.
- `signposting` reads a recap opener only at the start of a sentence before a comma, so "in short weeks" passes.
- `symbol-in-prose` reads emoji and arrow characters and " -> " between words. Code, tables, double-quoted text and `$...$` math are masked, and the "↩" that marks a footnote's return link passes, as do ordinary symbols such as "♯" and "✓". It is advisory because a menu path such as "File → Save" is ordinary notation.
- `intensifier` allows two per H1 or H2 section, as `triad-density` allows two lists of three, and passes "the very first" and "this very room".
- `passive-by-agent` reads a form of "be", up to two adverbs, a past participle and "by", followed by a word that is not "far", "default", "hand", a number or a lowercase gerund, so "designed by Ming" counts and "fixed by replacing" passes.
