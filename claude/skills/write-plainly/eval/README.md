# Lint false-flag check

`false_flags.py` runs every rule in the three write-plainly linters (`lint_prose.py`, sloplint and slop-guard) over careful human prose and over model-written drafts on the same topics, then prints how often each rule fires on each side. A rule that fires more often on the human side flags careful writing more than it flags model writing, so if the rule exists to catch model habits, it should become advisory, with a message that starts with "Check:", or go. The check exists because published AI-tell rule sets often fire more on good human technical writing than on model output.

## Running it

From the repo root:

```sh
uv run --upgrade claude/skills/write-plainly/eval/false_flags.py > false-flags.md
```

It needs `uv`, `git` and `sloplint` on the `PATH` (sloplint is a Ruby gem). The script declares its own Python dependency (trafilatura, for turning HTML into markdown), which `--upgrade` resolves to the latest release on every run, and slop-guard runs through `uvx` at its latest release too, as `check-prose.sh` runs it, so nothing else needs installing. The first run fetches the web pages and a pinned commit of the `bheijden/slop` repository into `.cache/`, about 60 MB in all. Later runs reuse the cache; delete a file or directory there to fetch it again.

The cache is gitignored and must stay that way. The human texts are other people's copyrighted work, kept locally only to measure the linters. Each run writes `.cache/rights.tsv` with the source, date and known rights status of every public text.

`--private` adds the corpora listed in `.private/eval/corpora-private.toml` at the repo root (a gitignored file) and writes the result to `.private/eval/false-flags-private.md` instead of printing it. Use it for prose that must not be published, such as your own work documents.

The tests in `tests/` run the script end to end on small fixture texts, with stand-in `sloplint` and `uvx` executables:

```sh
uv run --upgrade --no-project --with pytest --with trafilatura python -m pytest claude/skills/write-plainly/eval/tests
```

## Corpora and the table

`corpora.toml` lists the corpora. The human side has the human halves of the `bheijden/slop` matched corpus and seven long-form explanatory web pages that `../sources.md` names as models: two each by Karpathy, Amodei and METR (Model Evaluation and Threat Research), and Google's guide to paragraphs. The agent side is that corpus's model halves. Each of its 24 pairs is one topic written twice: once by a person before 2022, and once by `claude-opus-5` from the same topic, audience and points, without seeing the human text. The pairs cover twelve registers, with three pairs each for academic, forum, government, journalism, literary and techdoc writing and one pair each for six more.

For each rule that fired at least once, the main table gives hits per 1,000 words on each side and their ratio. It also marks whether the human rate is higher and counts the texts on each side with at least one hit. Words are counted as `lint_prose.py` counts them: a word is a run of letters and digits, which may continue across an apostrophe, hyphen, period or comma ("don't", "well-known", "3.5"). Table pipes and list bullets are not words, and "A/B" counts as two. The second table splits the same rates by corpus and register: the `bheijden-slop all` columns are the matched comparison, and the techdoc and academic columns are the registers closest to what this skill is used for. The output ends with the enabled rules that never fired, which these corpora say nothing about.

The script reads slop-guard's hit counts per category (the `--counts` view), so each slop-guard row is a category such as `slop_words` or `structural`, which covers many words or patterns. sloplint runs with its default rules, including the one `check-prose.sh` skips (see Results), so that rule's rate stays visible. slop-guard runs with `../slop-guard.jsonl`, so a rule removed from that file no longer shows up here.

## What it does not show

The numbers are counts of pattern matches. They say how often a rule fires on each kind of text. Whether a reader would agree that a flagged sentence should change is a separate question, which only reading the flagged text answers. A rule can fire more on human prose and still enforce a style you want: the skill bans em dashes by preference, even though careful writers use them. These limits matter when you read the table:

- The corpora are small. The matched corpus has three pairs per register in its main registers, about 3,000 words per side, so one text can move a rate several times over. Hits cluster in a few texts, so read the docs columns beside the rates.
- One model wrote every agent text, prompted one way. Other models, other prompts or real agent drafts from your own work can fire rules at different rates.
- The two sides differ in more than authorship. The seven web pages (about 33,000 words) have no agent counterpart, and the matched corpus is plain text with no headings, bold or lists. Rules about markdown structure can therefore fire only on the human web pages, and their agent rate of zero is not evidence. The corpus table counts the texts with markdown structure on each side. HTML conversion can also add or drop structure, such as a bold lead-in or a caption, so when a markdown rule's rate looks wrong, read the converted page in `.cache/pages/`.
- A third of the matched corpus's human texts were published before 1930, all in non-technical registers: three literary texts and one each of biography, how-to, letters, review and travel. Prose that old differs from the technical documents this skill is for.
- `lint_prose.py` and the modules it imports (`lint_prose_markdown.py`, `lint_prose_document.py` and the word lists in `lint_prose_patterns.py`) change over time, and each table below gives the date of its run.

## Results

The table comes from runs on 2026-11-20. slop-guard ran with the version of `slop-guard.jsonl` from before the changes below, so the rules they removed still have rates. The three-item part of `structural` is the difference between that run and a run with the current file. The human side has 56,689 words and the agent side 23,484.

Each rule falls into one of two groups, and only tell rules can be demoted:

- House-style rules encode this skill's own preferences: no em dashes, no dashes as pauses, few numbers in body prose, paragraph shape and sentence length. The markdown rules from the skill's Format section are house style too: no bold run-in labels or bold lead-ins, bold only for a decision or a label, sentence-case headings and no thin sections. They stay whatever their human rate, and their rates are reported for information. A rule from another linter that contradicts one of them is removed whatever its rates.
- Tell rules exist to catch model habits. A tell rule that fires more often per 1,000 words on the human side than on the agent side, on at least three human texts, gets an advisory "Check:" message or is removed. The three-text minimum exists because two texts against none is within noise for corpora this small, and the skill's owner confirmed it. The owner also ruled four tell rules to be smells that no text should carry. They flag stacked hedges (`stacked-hedge`), comma chains of items that open on the same determiner (sloplint's `same-determiner-chain`), "stands as" and "serves as" (sloplint's `stands-serves-as`), and short evaluative fragments such as "Simple, but powerful." (slop-guard's `pithy_fragment`). These four are house style, so they stay whatever they score on human text, and a hit on any of them is a fix. The fix restructures the sentence; a synonym the pattern misses leaves the smell in place.

slop-guard's `bullet_density` and the bold-header and bullet-run checks in its `structural` rule are tell rules about markdown structure. They cannot fire on the matched corpus, which is plain text, so they are meant to be judged on the passages that the pairwise evaluation in `pairwise/` generated, as "Markdown rules on generated passages" describes. The public passages have no heading, bold or list, so neither rule is judged yet, and both stay on.

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
| `not-x-but-y` | sloplint | tell | 0.00 | 0.21 | 0.00 | 0/31 | 5/24 | kept |
| `isnt-x-its-y` | sloplint | tell | 0.00 | 0.21 | 0.00 | 0/31 | 3/24 | kept |
| `no-x-no-y` | sloplint | tell | 0.00 | 0.13 | 0.00 | 0/31 | 2/24 | kept |
| `stacked-hedge` | lint_prose | house | 0.05 | 0.00 | 0.04 | 2/31 | 0/24 | kept, owner's ruling |
| `same-determiner-chain` | sloplint | house | 0.04 | 0.00 | 0.04 | 2/31 | 0/24 | kept, owner's ruling |
| `stands-serves-as` | sloplint | house | 0.04 | 0.00 | 0.08 | 2/31 | 0/24 | kept, owner's ruling |
| `pithy_fragment` | slop-guard | house | 0.04 | 0.00 | 0.04 | 2/31 | 0/24 | kept, owner's ruling |
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
| `intrasentence_keyword_bold` | slop-guard | house | 0.02 | 0.00 | 0.00 | 1/31 | 0/24 | kept |

Nine more rules fired on a single text, too few to read: sloplint's `not-by-x-but-by-y`, `actually-not-x`, `impact-verb`, `real-x-real-y` and `is-is` and slop-guard's `ai_disclosure` on one human text each, and sloplint's `short-run`, `notice-what` and `thats-how-x` on one agent text each. Most of sloplint's default rules, two in five of slop-guard's categories and `lint_prose.py`'s `heading-density` never fired, so these corpora say nothing about them; the last section of the output lists them.

### Changes

- slop-guard's word list (`SlopWordRule`) is removed from `slop-guard.jsonl`. The human hits are common words in their usual sense, most often "societal", "crucial", "paradigm" and "robust". The two Amodei essays carry over half the human hits, and the rule still leans human on the matched corpus alone.
- slop-guard's stock-phrase rule (`SlopPhraseRule`) is removed. Most human hits are "in addition" and "in other words", written as ordinary transitions or as "in addition to". The rule also matches inside longer words ("gain additional" counts as "in addition", and "AI can also" as "I can also"). Without those matches the human rate is still about five times the agent rate, so this bug does not explain the gap.
- slop-guard's tone rule (`ToneMarkerRule`) is removed. Its human hits are "As mentioned above" in a research post, "As mentioned in the introduction" in an essay and "Certainly," in a memoir, plus "areas mentioned", which is the same substring bug. It is the closest call among the tell-rule changes. It sits exactly at three texts, and the agent texts are essays, which cannot show the chat phrasing the rule mostly looks for ("would you like", "let me know if").
- slop-guard's `structural` rule keeps its bold-header and bullet-run checks, but its three-item list check is off: `triadic_record_cap` and `triadic_penalty` are 0, and `triadic_advice_min` is set higher than any document reaches. Its hits are plain lists of three, such as "film, television, and music".
- slop-guard lists every `pithy_fragment` hit: its `record_cap` is 1000000 instead of the default 3, since a one-pass triage cannot fix a hit it never sees. The cap limits only the listed hits; the counts these tables use include every hit.
- slop-guard's paragraph rhythm rules (`ParagraphBalanceRule` and `ParagraphCVRule`) are removed as house-style conflicts. They ask for a mix of short and long paragraphs, which contradicts the skill's minimum of four sentences per body paragraph, and `paragraph_cv` fired on nearly every agent text.
- `nominalization-of` in `lint_prose.py` now starts its message with "Check:" and calls itself advisory. Its hits are real nominalizations. Some are the case the rule is for ("The creation of this PEP was prompted by"), and some are fine as written ("an implementation of a standard algorithm"), so the rule stays as a prompt to look.
- `check-prose.sh` runs sloplint with `--ignore impact-noun-bare`. Every human hit is research wording, such as "the impact of AI on developer productivity". sloplint's own rationale for the rule calls "the impact of X on Y" ordinary research wording, yet the rule fires on that form.
- Two false positives in `lint_prose.py` are fixed. `inverted-animacy` read "a substantial number said" as an artifact speaking, so it now matches "numbers" ("the numbers tell us") and not "number". `coined-label` read the pronoun in "every plan I have" as a label named "I". These were the only hits of either rule on either side, so neither rule fires on these corpora now and neither has a row in the table.

A run with the current `slop-guard.jsonl` shows the five removed slop-guard categories gone and `structural` firing only on the four web pages with bullet runs or bold headers.

The house-style rules fire more often on careful human prose, as expected. `dash-substitute` (spaced hyphens and en dashes in blog posts, journalism and forum comments, and double hyphens in older printed texts), `short-paragraph-run` and `number-density` all fire several times as often on the human side. `number-density` counts digits, spelled-out numbers from ten up ("twenty-three", "a dozen", "two million") and a smaller number in words that is a multiple, a percentage or a share ("fourfold", "three percent", "one in four"). It also counts multiples written without a number word ("twice as fast", "doubled", "10-fold") and measured amounts and fractions written in words ("three cents", "a tenth of a point", "about a third"). It reads a magnitude after digits ("40 thousand") as part of that number, and passes small counts of things ("two options", "all but four"). Counting digits alone, it would flag one agent text instead of five. The em dash rate is nearly equal on the matched corpus. `complex-sentence` is the most frequent rule on both sides and does not separate them.

One kept tell rule flips between the two comparisons: `contrast_pairs` fires more often on the matched human halves than on the agent texts, and less often over all human text. It stays because the triage compares the whole human side. Each tell-rule change above points the same way on the matched corpus alone, where both sides are plain text on the same topics, though `tone` and `impact-noun-bare` fire on only one matched human text each. The limits in "What it does not show" apply to all of these results.

### Markdown rules on generated passages

The pairwise evaluation generated one passage per task and pipeline, and two of its tasks are public. The 10 graded passages on those two tasks (2,320 words) contain no markdown structure, because the prompt asks for body text with no heading. `bullet_density` and slop-guard's bold-header and bullet-run checks never fire on them, so these rules stay unjudged until a source of agent-written documents with markdown structure is added. The human side for these rules is the seven web pages, since no other human text has markdown structure. The bold and heading rules in `lint_prose.py` are house style and need no judgment.

## Rules from the owner's corrections

The skill's owner collected the writing corrections they had given to models and merged them into rules. The rules below implement the ones a pattern can catch, as new rules in `lint_prose.py` and a wider `coined-label`. The table comes from a run on 2026-11-22 on the same corpora as the table above. The rows for `announcing-sentence`, `stock-emphasis`, `history-in-document`, `rather-than`, `cleft-sentence`, `supporting-statistic`, `inverted-animacy-check`, `power-read`, `universal-negative` and `number-notation` come from a later run that day, after the changes from the owner's comments on model-written documents described below. Each rule was also run on the model text the owner had corrected; that text and those results stay private.

The owner gave these rules, so they are house style and stay even where careful human writers break them. A rule that fires on three or more human texts, or whose verdict depends on the reader, has a message that starts with "Check:". Most of the corrections were about chat and status messages: labels coined during the work, pointers back to an earlier message, acronyms nobody defined. The agent texts here are essays written from a brief, which rarely do these things, so an agent rate of zero means the rule stays quiet on essays. It says nothing about how often the rule catches model habits in messages.

| rule | what it flags | message | human | agent | human texts | agent texts |
|---|---|---|---|---|---|---|
| `coined-label` | labels and IDs coined during the work ("route C", "phase-3", "task #42", `LIB-12`, "C3") | check | 0.35 | 0.00 | 4/31 | 0/24 |
| `back-reference` | pointers to earlier text ("as discussed", "in my previous message", "the fix above", "per the rule", "the two questions about parking are still open") | check | 0.14 | 0.00 | 4/31 | 0/24 |
| `announcing-sentence` | a sentence that only names what follows ("Two changes help wheelchair users:", "Three changes, each with a cost:", "Two honest notes on the new rota.", "We wanted to know whether late opening helps.") | check | 0.02 | 0.00 | 1/31 | 0/24 |
| `stock-emphasis` | "honest", "honestly", "frankly", "to be honest", "table stakes", "is a big win", "and that matters.", "deserves a mention", and the announcing phrases "it is important to note", "it should be noted", "it's worth noting", "it is worth saying that", "needless to say", "at its core", "the reality is", "let me be clear" and "Importantly," | fix | 0.07 | 0.30 | 3/31 | 6/24 |
| `history-in-document` | edit history ("was changed from", "the earlier draft", "which earlier drafts called visits", "our first read", "now fixed", "now counts loans instead of visits", "this revision corrects") | fix | 0.00 | 0.00 | 0/31 | 0/24 |
| `all-caps-emphasis` | ordinary words in capitals ("NOT", "VERY", "IMPORTANT FOR EVERYONE") | fix | 0.09 | 0.00 | 2/31 | 0/24 |
| `american-spelling` | British spellings from a closed list ("colour", "organise", "centre", "licence", "modelling") | fix | 0.56 | 2.04 | 11/31 | 15/24 |
| `rather-than` | "rather than", a ", not" contrast after a number, bracket or inline code, "the loans instead of the visits", "a library as opposed to a café", "a guide and not a rule", a sentence that says what the thing is not ("It isn't a replacement"), and "less about X and more about Y" when a noun is the subject (sloplint flags the "It's less about" form) | check | 0.12 | 1.23 | 6/31 | 14/24 |
| `cannot-rule-out` | "cannot be ruled out", "can't rule out", "we cannot exclude" | fix | 0.00 | 0.00 | 0/31 | 0/24 |
| `power-read` | a result read off the test's power, or a winner the intervals do not separate ("would usually have caught", "cannot detect a change smaller than 5", "below what the test can detect", "likely the best") | check | 0.00 | 0.00 | 0/31 | 0/24 |
| `universal-negative` | a claim that nothing exists or ever happened ("No branch has ever opened on a Sunday", "none varied its hours", "branches to date have not") | check | 0.02 | 0.00 | 1/31 | 0/24 |
| `cleft-sentence` | "What keeps the queue short is the second desk.", "It is the narrow door that causes the delay.", "Adding a second desk is what keeps the queue short." | check | 0.23 | 1.28 | 9/31 | 16/24 |
| `triad-density` | the third and later sentence in a section with an "A, B and C" series | check | 1.62 | 2.60 | 24/31 | 17/24 |
| `tldr-shape` | a TL;DR, Summary or Abstract section of more than eight sentences or four numbers | fix | 0.02 | 0.00 | 1/31 | 0/24 |
| `supporting-statistic` | a sentence outside the back matter quoting a test statistic, degrees of freedom, a p-value, an interval, a plus-minus spread or two decimal rates set against each other ("a t of 3.10 on 14 df", "4.0% [2.5%, 5.5%]", "within ±1.1%", "0.92 against 0.97") | check | 0.09 | 0.00 | 2/31 | 0/24 |
| `undefined-acronym` | the first use of an acronym that comes before its definition | check | 1.50 | 0.55 | 20/31 | 9/24 |
| `inverted-animacy-check` | a thing that earns, holds, buys, wins, crowds or rescues ("The window display earns most of the new members.", "the features that won their trials"), and money or revenue that runs or flows | check | 0.00 | 0.04 | 0/31 | 1/24 |
| `number-notation` | a share written as a count ("1.8 times in 100", "4 in 10", "two of every 100", "3 per hundred") and a ranking metric at a cutoff written in words ("NDCG at 10", "recall in the top 5") | fix | 0.02 | 0.09 | 1/31 | 2/24 |

The human hits were read. `coined-label` fires on product, chip and robot names (R1, V3, H800, PR2), on "L2 regularization" and on two real "described in #3" pointers. `back-reference` fires on cross-references inside long essays ("as noted above"), which the advisory message leaves the writer free to keep. `undefined-acronym` fires mostly on well-known abbreviations outside its skip list (SGD, RNN, IRS, BBC), which is why it is advisory. The `all-caps-emphasis`, `tldr-shape` and `announcing-sentence` hits are real instances: capitals for emphasis in a nineteenth-century biography, a 50-sentence Summary section, and "A few tips and tricks for this step:" before a list. Every `american-spelling` hit is a British spelling, and the rule fires on more model texts than matched human texts: the model wrote "behaviour" and "licence" even in technical documents whose human halves use none. Its message says fix although it fires on more than three human texts, because every hit is a British spelling, which the owner's rule changes in any text. `history-in-document` and `cannot-rule-out` never fired: these corpora have no revised drafts and no statistical readouts. Two `supporting-statistic` hits are in one post, a pair of log probabilities and a pair of screen coordinates, written as bracketed pairs. The other three are confidence intervals written into the body of METR's uplift update as "between" one endpoint "and" the other.

Seven of these rules now match more forms, and three were added (`power-read`, `universal-negative` and `number-notation`), to catch the defects the owner marked in comments on model-written documents. Each change was also measured on text the rules were not written from: the model passages the owner commented on, and the held-out public pages that "Rules for model tells from public catalogs" describes. The changed rules flag every sentence the owner corrected, one of them through a different phrase in the same sentence. A change stayed only if its rule still fires on the held-out pages less often than the median house-style rule does. The table gives each rule's held-out hits before and after the changes, from runs on 2026-11-22. `rather-than` is the one rule above the median, and the changes added no held-out hit to it.

| rule | held-out hits before | held-out hits after | texts hit after (of 14) | rate per 1,000 words after |
|---|---|---|---|---|
| `announcing-sentence` | 6 | 6 | 5 | 0.11 |
| `stock-emphasis` | 3 | 3 | 2 | 0.06 |
| `history-in-document` | 0 | 0 | 0 | 0.00 |
| `rather-than` | 26 | 26 | 8 | 0.48 |
| `cleft-sentence` | 2 | 3 | 3 | 0.06 |
| `supporting-statistic` | 1 | 1 | 1 | 0.02 |
| `inverted-animacy-check` | 1 | 1 | 1 | 0.02 |
| `power-read` | | 0 | 0 | 0.00 |
| `universal-negative` | | 0 | 0 | 0.00 |
| `number-notation` | | 1 | 1 | 0.02 |
| median house-style rule | | | | 0.13 |

The changes added six hits on human text, two of them on the held-out pages:

| rule | text | flagged words |
|---|---|---|
| `cleft-sentence` | the Rust book (held out) | "which is what memory would look like" |
| `number-notation` | Stripe's engineering blog (held out) | "a simple one in 10 lines of code", where "one" is a pronoun and not part of a share |
| `cleft-sentence` | four web pages and a letter | "This is what we are familiar with and expect" |
| `rather-than` | METR's uplift update | "randomize at the developer level instead of the task level", a design contrast its readers expect |
| `number-notation` | a forum post | "1 in 1000" |
| `universal-negative` | a forum post | "not that no one has had self-serve models before", which denies the absolute claim |

How the rules decide:

- `coined-label` reads label words followed by a number or a capital letter ("decision 7", "Track C's", "phase-3"), tracker IDs (`LIB-8.3`), word-and-hex IDs (`req-7c21be`), hash numbers and short letter-and-digit codes. Inside backticks it reads only tracker IDs, hex IDs and hash numbers, because a short code there is usually a variable name such as `W1`. An ID passes when it sits in parentheses right after a plain description ("the roof repair (LIB-12)"), and so do its later uses. Standard prefixes (UTF, SHA, ISO and a few more), common public codes (S3, Q3, P0, A100) and "#1" as a rank also pass.
- `undefined-acronym` looks for an all-caps word of two to six letters before any "(ACR)" or "ACR (spelled out)" in the document. A parenthesis after the acronym defines it only when its words spell the acronym, by their initials (with or without small words such as "of" and "the") or by their capitals. So "NASA (National Aeronautics and Space Administration)" defines NASA, and "NOT (under any circumstances)" defines nothing. It skips about 40 universal ones (API, URL, JSON, GPU and others), Roman numerals, ordinary words in capitals, code and link text.
- `all-caps-emphasis` flags a run of capitals that contains one of about 180 common words that are not also acronyms; an acronym the document defines, in the same way `undefined-acronym` reads definitions, passes ("The WHO (World Health Organization)").
- `triad-density` allows two sentences with a three-item series per H1 or H2 section, as the owner asked, and counts paragraphs, captions and footnotes. It reads the whole comma series and counts it only when it has exactly three items, so a list of four or more does not count. It skips an opening phrase of up to four words that starts with a word such as "in", "after", "when" or "however" and ends at the first comma. So "In winter, the branch opens late and closes early" holds a pair, while "In winter, the branch lends sledges, skates and scarves" counts. A list that starts right after such a word is read as the opening phrase and missed ("In Paris, Rome and Berlin, the museums open late"). slop-guard's three-item check stays off, because it flags single plain lists.
- `american-spelling` reads a closed list of British spellings: -ise and -isation forms of 37 verbs ("organise", "optimisation"), -our words, "centre" and "metre", "licence" and "defence", "modelling" and "labelled", "analyse", "programme", "judgement" and "ageing". It never matches a bare -ise ending, so "advertise", "exercise" and "precise" pass, and so do "analyses" and "catalogue", which are American spellings too.
- `supporting-statistic` reads every paragraph and list item outside the back matter, the summary included, since a summary carries no statistical detail either. Two decimal rates count only when a contrast word joins them: against, versus, vs., while, compared with or compared to. Threshold settings ("an alarm at humidity 0.05 and 0.2"), a headline change ("rose from 0.81 to 0.84") and a line of arithmetic pass. A range counts as an interval only after a confidence level or qualifier ("95% CI", "a 95% Wilson interval", "a credible interval"), so "CI takes 10 to 15 minutes" passes. A pair of years ("(2023, 2024)") and one number with a thousands separator ("($14,200)") are never read as an interval's endpoints. A bracket of whole numbers reads as a citation ("[3, 7]") unless an interval label comes before it ("the 95% confidence interval is [12, 18]"). Worded forms count too, such as "fourteen degrees of freedom", "95 percent CI" and an interval label's endpoints joined by "and" ("a 95% CI between 1.0 and 3.2"). So do "plus or minus" for ±, and "below", "under" or "less than" after a p-value.
- `rather-than` leaves the word-comma-not form ("open, not closed") to slop-guard's `contrast_pairs`, which already flags it. Its "instead of", "as opposed to" and "and not" forms need an article on both sides ("the loans instead of the visits"), so "Instead of driving, take the bus" passes. Its sentence form needs "It", "This" or "That" after a period or semicolon, then a negation such as "isn't a".
- `cleft-sentence` also reads "is what" and "was what" anywhere in a sentence that is not a question, with "are", "were", "exactly" or "only" in the same places. It skips "what to" and "what if", so "The question is what to do next" passes.
- `announcing-sentence` also reads a sentence that holds only a count and a word such as "notes", "caveats" or "things" ("A few caveats."). A short phrase may follow if it starts with "on", "about", "for", "before" or "to keep in mind" ("Two honest notes on the new rota."). Its colon form may cross a comma ("Three changes, each with a cost:").
- `inverted-animacy-check` reads a thing as the subject at the start of a clause, or anywhere before "that" or "which" ("the features that won their trials"). It reads money, revenue and dollars that run or flow, but "the money ran out" and "revenue runs low" pass.
- `universal-negative` reads "no ... has ever", "no ... has had", "no ... exists", "none" before a past verb such as "varied" or "tested", "has never been tried" and "to date have not", so "We could not find a branch that opens on Sundays" and "We found no branch that..." pass.
- `number-notation` reads a count over a base of "10", "100" or "1,000", in digits or words, after "in" ("4 in 10"), "of every" or "out of every", and before "per hundred". A unit of time after the base makes it a duration, which passes. A count of things ("three of the ten volunteers") passes, and so does a score. Its ranking metrics are normalized discounted cumulative gain (NDCG), hit rate (HR), mean reciprocal rank (MRR), mean average precision (MAP), recall and precision, each before "at", "at rank" or "in the top" and a whole-number cutoff. A percentage or a decimal after "at" is an operating point, which passes ("precision at 90% recall").
- `power-read` reads "would usually have caught", "cannot detect" followed closely by "smaller than" and a number, "below what the test can detect" and "likely the best". It says check because a statement about power is sometimes the point, as when a test could rule out large effects.
- The phrase and sentence rules skip double-quoted spans, which hold someone else's words. `coined-label` and `undefined-acronym` read quoted text, because a quoted button or ticket name is still an unexplained ID.

No rule was dropped. Three proposed forms were left out because they flagged good prose. `history-in-document` does not read "an early version of the", which a held-out page uses for a book section first published as an article, and which also covers "an earlier version of the census". It reads "earlier drafts" and "earlier revisions" but not "earlier write-ups" or "prior readouts", which in the owner's model text named earlier published studies. `number-notation` reads "of" and "out of" before a base only after "every", so a score passes.

`supporting-statistic` replaced two simpler caps on numbers, which flag more careful human prose than `number-density` does when numbers are counted the same way, in a run on 2026-11-22. A cap of two per sentence flags nothing that `number-density`'s cap of two per paragraph does not already flag.

| cap on body prose | human hits per 1,000 words | human texts hit |
|---|---|---|
| one number per sentence | 1.61 | 17/31 |
| one number per paragraph | 1.46 | 19/31 |
| `number-density`, two per paragraph | 0.93 | 16/31 |

## Rules for model tells from public catalogs

The rules below catch model habits that sloplint and slop-guard, as `check-prose.sh` runs them, do not catch. Their word and phrase lists, in `lint_prose_patterns.py`, come from Wikipedia's "Signs of AI writing" and "Words to watch" and the phrase list of hardikpandya/stop-slop (see `../sources.md`). The rules marked house style enforce rules the skill already states. The skill says to cut intensifiers and padding, write in active voice and literally, prefer the everyday word, open with the information instead of a signpost, and use no emojis or arrows in prose. `finance-word` comes from the owner's corrections. `stock-emphasis` also flags the announcing phrases the skill tells writers to cut, and `rather-than` also flags "less about X and more about Y"; both rules' rows are in the table above. The plain-language lists come from the Federal Plain Language Guidelines and digital.gov, and the stock images and idioms from "Words to watch" and stop-slop. The table comes from a run on 2026-11-22 on the same corpora as the tables above.

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

Each list started from the catalogs, and an entry stayed only if it fired rarely on the human texts here. Four phrases were dropped from the plain-language rules because careful writers use them in their plain sense. They are "in terms of" ("performance in terms of task length"), "with respect to" (a gradient with respect to a parameter), "on the basis of" and "in the context of". So were the noun "utilization", "blind spot", "playbook", "unpack", "recipe for" and "ecosystem". Phrases sloplint already flags are left to it: "underscores", "tapestry", "testament", "vibrant", "Here's what nobody tells you", "read that again", "Here's the kicker:" and "The takeaway:".

The tell rules were also checked on text their lists were not written from: model text the owner had corrected, and public engineering and research pages outside these corpora, called the held-out pages below. A tell rule stayed only if it caught problems in that model text without flagging the held-out pages more often than the house-style rules do, and three of the twelve did. These checks ran on 2026-11-22.

| text | size |
|---|---|
| model text the owner had corrected | about 340,000 words |
| held-out pages: 14 public engineering and research pages | 54,199 words |

| rule | hits in the corrected model text | outcome |
|---|---|---|
| `chat-phrasing` | 9, all real | kept |
| `section-label` | 4, all real | kept |
| `borrowed-jargon` | 6, all "orthogonal" meaning "unrelated" | kept |
| `ai-vocabulary` | 12, all noise | removed |
| `vague-quantifier` | none real, and hits on 5 of the 14 held-out human pages | removed |
| `promotional-word`, `era-framing`, `stock-concession`, `dead-transition`, `whether-range`, `insight-teaser`, `engagement-bait` | none real | removed |

The human hits were read. `stock-emphasis` fires on three human texts. Every one of those hits is an announcing phrase that the skill cuts in any text, such as "It's worth noting that" and "It should be noted in this context that", so its message says fix, as with `american-spelling`. `intensifier` fires eight times as often on the human side, and most of its hits are "very". It stays because the skill asks writers to cut intensifiers whoever writes them, and it says "check" because one or two strong adverbs per section are often earned. Most `wordy-phrase` hits are "in order to", which the skill names as padding, and the rest are "when it comes to". Each reads the same with the short form, but the rule is advisory because "in order" can mean a sequence ("written in order to disk"). The `signposting` hits are recaps and section signposts in long essays ("In summary,", "In conclusion,", "So in this section, I'll"), which is why it is advisory. `formal-word` fires on "ameliorate" and "Prior to", and `metaphor` on "pulling a few key levers" in an essay and "the backbone of a liberal education" in an agent text. `passive-by-agent` fires at about the same rate on both sides; "by" followed by a means ("by replacing two tiles"), a sort key ("sorted by date") or a feeling ("surprised by") is not an actor and passes.

Four of the new rules (`chat-phrasing`, `section-label`, `finance-word` and `symbol-in-prose`) never fired on these corpora, so the corpora say nothing about their false-flag rate. The agent texts are essays written from a brief, and those rarely carry chat phrasing or section labels, so an agent rate of zero says nothing about how often the rules catch model habits in documents. Because the lists were pruned on these same corpora, the human rates above are lower than they would be on new text.

Three checks were tried and left out. A rule for a phrase repeated three or more times would contradict the skill's rule to keep one term per concept. It also fires mostly on careful prose: sloplint's off-by-default `phrase-echo` fires more than five times as often per word on the human texts as on the agent texts, and on two-thirds of the human texts. A rule against a size in words with no number ("improved considerably") would contradict the skill's Evidence and numbers section, which keeps the numbers in tables and asks the prose for the size in plain words. A count of bold spans per word adds nothing to `bold-run-in` and slop-guard's bold checks, which flag each bold lead-in and inline keyword. On the human pages it would flag Karpathy's recipe post, whose bold lead-ins `bold-run-in` already flags.

How the new rules decide:

- The tell rules read paragraphs, list items, captions, footnotes and headings, and skip double-quoted spans. Every phrase rule reads a paragraph with its line breaks joined, so a phrase wrapped across two lines still matches. `section-label` reads a heading's whole text, or the start of a paragraph or list item, so "the bottom line of the form" passes.
- In `stock-emphasis`, "it is important to note" and "worth noting" need "that", "how", "why" or a punctuation mark after them, so "it is critical to note each failed request" passes, and "at its core" counts only before a comma. The verbs of saying after "worth" ("worth saying", "worth adding", "worth flagging") can also name actions, so they need a clause after them that opens on "that", "how", "why", "what" or "whether". So "a leak worth flagging to the landlord" passes.
- `formal-word` reads "utilize" only as a verb and "endeavor" only before "to", so "resource utilization" and "a long endeavor" pass. `finance-word` passes "a foregone conclusion", reads "repays" only before "its cost" or a similar object, and "carries" only before a percentage, so "the borrower repays the loan" and "the van carries 30 boxes" pass.
- `metaphor` reads each image only in its figurative frame. It reads "bar" after "raise", "lower", "clear", "set" or "meet", or as "a high bar", and "floor" and "ceiling" after "put a" or "set a", or as "a hard floor". It reads "lens" in "through the lens of", "ledger" in "a ledger of", and "lever" as "key levers" or "pull ... levers". So "the café has a bar and a ledger" and "the jaw works as a lever" pass.
- `signposting` reads a recap opener only at the start of a sentence before a comma, so "in short weeks" passes.
- `symbol-in-prose` reads emoji and arrow characters and " -> " between words. Code, tables, double-quoted text and `$...$` math are masked, and the "↩" that marks a footnote's return link passes, as do ordinary symbols such as "♯" and "✓". It is advisory because a menu path such as "File → Save" is ordinary notation.
- `intensifier` allows two per H1 or H2 section, as `triad-density` allows two lists of three, and passes "the very first" and "this very room".
- `passive-by-agent` reads a form of "be", up to two adverbs, a past participle and "by", followed by a word that is not "far", "default", "hand", a number or a lowercase gerund. So "designed by Ming" counts and "fixed by replacing" passes.

## Shape rules from the owner's comments on model-written documents

The owner's comments on model-written documents asked for changes that no sentence pattern can see. A document should have fewer and fuller sections, the length agreed for it, and numbers in tables however they are spelled. A cleanup or review pass should leave the main text shorter, and a pull request description should open with a short summary. The rules below implement these. `staccato-run` and the wider `thin-section`, `heading-density` and `number-density` run on every document. `over-budget`, `revision-growth`, `appendix-growth` and `pr-shape` run only when `lint_prose.py` gets `--budget N`, `--against OLD` or `--pr`, or a file name such as `pr-body.md` for `pr-shape`, so they never fire on the corpora above.

The rates come from a run on 2026-11-22 on the corpora above. The held-out column counts hits on the 14 public pages that "Rules for model tells from public catalogs" describes, which the rules were not written from; the changed rules' counts there before the change are in parentheses. The rules were also run on the model passages the owner commented on and caught the passages they were written for, except `over-budget`, whose passages were not recovered. That text and those results stay private.

| rule | what it flags | message | human | agent | human texts | agent texts | held-out hits (texts of 14) |
|---|---|---|---|---|---|---|---|
| `thin-section` | a section outside the back matter with less than its level needs: an h1 or h2 with one block, or a lower heading whose paragraphs hold fewer than four sentences in all | fix | 0.05 | 0.00 | 1/31 | 0/24 | 10, 6 (was 6, 4) |
| `heading-density` | more headings, at every level below the title and outside the back matter, than the prose supports | fix | 0.00 | 0.00 | 0/31 | 0/24 | 6, 6 (was 1, 1) |
| `number-density` | the rule above, now also counting measured amounts and fractions in words | fix | 1.04 | 0.47 | 17/31 | 7/24 | 42, 10 (was 40, 9) |
| `staccato-run` | three or more short sentences in a paragraph that open on one word or each on a determiner ("Members borrow drills. Members return them. Members pay nothing.") | check | 0.02 | 0.00 | 1/31 | 0/24 | 1, 1 |

The human hits were read. `staccato-run` fires on Karpathy's list of bugs in his training recipe ("The function only expected 3 arguments. This import failed. That key does not exist.") and on the Rust book's "If we forget, we'll waste memory. If we do it too early, we'll have an invalid variable. If we do it twice, that's a bug too." Both are runs of the shape the rule targets, written for rhythm, so the rule is advisory. It fires on the held-out pages far less often than the median house-style rule, and sloplint's `short-run`, which reads only very short sentences, misses both. The `thin-section` hits at lower headings are listed below, and back-matter sections such as the footnotes of the Amodei essays pass. Counting every heading level outside the back matter, `heading-density` fires on six held-out pages, each one to five headings over its budget. The new `number-density` hits are durations and fractions in words ("about two years", "roughly half", "three quarters"). They raise the agent rate by more than the human rate, since the model texts write amounts in words more often.

| `thin-section` hit | text | section |
|---|---|---|
| "Scale", "Uptime" and "Accuracy" | Stripe's post on online migrations (held out) | an h3 of three sentences each |
| "Ownership Rules" | the Rust book (held out) | an h3 of two sentences before a list of the rules |
| "5. Tune", "6. Squeeze out the juice" and "Conclusion" | Karpathy's recipe for training neural networks | an h4 of a sentence or two before a list, and a one-paragraph conclusion |

The held-out pages and the corpora above have no pull request descriptions, revised drafts or word budgets, so the rules for those shapes were checked on other documents, in runs on 2026-11-22:

| rule | checked on | hits |
|---|---|---|
| `pr-shape` | 40 recent pull request descriptions from five public Python and Rust projects | 27, most of them a short description with a bulleted change list or a code sample and no rule, which the owner's shape puts below a rule |
| `revision-growth` | 25 consecutive revisions of four public READMEs and a book chapter | 9, each a real growth of 3 to 116 words; these revisions add features to the text, while the flag is for cleanup and review passes |
| `appendix-growth` | the same 25 revisions | 0, because none of the versions has back matter or footnotes |
| `over-budget` | its tests only: it runs only with `--budget N`, and none of these documents states a word budget | not measured |

How the rules decide:

- `thin-section` reads every heading below a lone H1 title, and a section runs to the next heading of its level or higher, so it holds its subsections. An h1 or h2 needs two blocks, where a list counts once. A lower heading needs four sentences across its paragraphs, and a list adds none. At any level a list of links passes and a summary section is exempt. A heading followed directly by a deeper heading only groups its subsections and is skipped. So is a back-matter heading: Appendix, References, Bibliography, Notes or Footnotes, and with `--pr` everything below the rule.
- `heading-density` counts the headings at every level below a lone H1 title, leaving out back-matter headings, against a budget of six plus one for every 400 words of prose.
- `number-density` counts a number word from two to nine before a unit of measure ("three cents", "five minutes"), and "one cent" or "one point" but not "at one point". It counts a fraction before "of", a comparative, a preposition or punctuation ("two-thirds of sales", "about a quarter more"), so "a third recipe" passes. It counts "half a", "half of", "half the", "more than half" and "two and a half". It counts "under", "over", "nearly", "roughly" or "almost" before a number word, and "by" with a number word at the end of a clause ("rose by three."). "Half a dozen", "judged by two bakers" and "two of the five ovens" pass.
- `staccato-run` reads the sentences of one paragraph, and a sentence of 12 or fewer words is short. Quoted words count toward a sentence's length, and a sentence inside quotation marks is not read. List items, captions and separate paragraphs never form a run.
- `over-budget` counts the main text: the words of paragraphs and list items outside the back matter, leaving out headings, tables, figures, captions, code, quotations and footnotes. It fires above 110% of the budget.
- `revision-growth` compares that count with the old version's, and `appendix-growth` compares the words of the back matter and footnotes.
- `pr-shape` reads the summary, the part of the description before the first horizontal rule, or the whole description when there is no rule. It fires on more than six sentences or 150 words, a list, a table, a code block other than a mermaid diagram, a bold lead-in, or a heading after one leading title. With `--pr`, the part below the rule is the appendix for the other rules too.
- `check-prose.sh` converts a notebook to markdown with jupytext before linting, keeping the markdown cells and the code as fenced blocks and dropping outputs and metadata, and reports the findings under the notebook's name. It ends any run with findings on one line asking for a structural fix, and it prints slop-guard's findings and counts without the 0 to 100 score.

The owner also asked for captions of a sentence or two, and the rule written for it, `long-caption`, was dropped. Markdown does not mark a caption, so the rule had to read the first block after every image as a caption, however long. On the 42 images in 23 public READMEs, tutorials and blog posts, it flagged six blocks, and only one of them was a caption: the three sentences under the model diagram in Whisper's README. The other five were introduction paragraphs after a banner or an illustration, and reading them as captions also exempted them from `number-density` and the other rules for body prose. Treating an image above the document's first body paragraph as a banner changed none of the six, because each of those images comes after at least one paragraph. So a caption is again a block that opens "Figure 2:" or "Table 1.", or a block of at most two sentences right after an image, and `prose-reviewer` checks captions and the text that explains a figure.
