# Sources for write-plainly

These sources influenced the skill. The skill combines selected principles from them with my own preferences; it does not reproduce a standard or another skill. Study the named writers' explanatory methods without imitating their personalities or treating their arguments as established facts. The links are as collected when the skill was drafted and have not all been rechecked.

## Style guides and standards

- [ASTM, Form and Style for ASTM Standards](https://www.astm.org/v3/assets/blt5eb0a2cb04534832/blt110aa33ef5eaa872/69e24e362ea600fed3edd4fe/bluebook_FormStyle_march2026.pdf): scope, procedures, terminology, and interpretable quantities; especially A5, A18-A22, E, G5, and G19.
- [NASA, Technical Documentation Style Guide](https://standards.nasa.gov/sites/default/files/standards/KSC/F/0/ksc-df-107_rev_f_07082017.pdf): direct language, consistent terms, voice, and noun sequences; especially sections 3.1-3.8.
- [ASD-STE100, Issue 9](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf) and [ISO House Style](https://www.iso.org/ISO-house-style.html): selected principles for unambiguous instructions and modality, without the controlled vocabulary or sentence-length rules.
- Google: [paragraphs](https://developers.google.com/tech-writing/one/paragraphs), [clear sentences](https://developers.google.com/tech-writing/one/clear-sentences), and [anthropomorphism](https://developers.google.com/style/anthropomorphism). [NIST author guidance](https://www.nist.gov/nist-research-library/nist-technical-series-publications-author-instructions): plain language that preserves technical meaning.
- [Wikipedia, Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing): a descriptive catalog of recurring patterns, not a reliable test of authorship or a universal style code.

## Writers whose explanations the skill uses as models

- Karpathy: [A Recipe for Training Neural Networks](https://karpathy.github.io/2019/04/25/recipe/) and [Pong from Pixels](https://karpathy.github.io/2016/05/31/rl/): concrete operations, explanations of why checks work, and one example carried through successive concepts.
- Amodei: [Machines of Loving Grace](https://darioamodei.com/essay/machines-of-loving-grace) and [On DeepSeek and Export Controls](https://darioamodei.com/post/on-deepseek-and-export-controls): explicit assumptions and distinctions that support a quantitative argument.
- METR: [Measuring AI Ability to Complete Long Software Tasks](https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/) and [Changing our Developer Productivity Experiment Design](https://metr.org/blog/2026-02-24-uplift-update/): operational definitions, scoped results, and explanations of how a limitation affects an estimate.

These six pieces, plus Google's paragraph guide, also served as the false-positive check for the linters. On roughly 32,000 words of them, sloplint 0.10.0 raised almost nothing except em dashes, which these authors use and this skill bans by preference. slop-guard 0.5.0 was noisier: its repeated-phrase rule flagged ordinary technical repetition ("the log probability of"), so `slop-guard.jsonl` is the packaged default config with that rule removed. Its word list also fires on words that careful writers use literally ("robust," "societal"), which is why the skill treats single word hits as prompts to check, not errors.

## Research on editing and judging

- Gooding, Lopez-Rivilla, and Grefenstette, [Writing as a testbed for open ended agents](https://arxiv.org/abs/2503.19711) (2025): in their comparison of LLM co-writers, models favored adding and elaborating content, while human editors more often deleted, simplified, and restructured, and raters favored deletions over insertions. This is the basis for the skill's preference for removing over adding.
- Shaib, Chakrabarty, Garcia-Olano, and Wallace, [Measuring AI "Slop" in Text](https://arxiv.org/abs/2509.19163) (2025): binary "slop" judgments were somewhat subjective, while span-level problems tracked dimensions such as coherence and relevance. This is why the reviewer reports specific spans and gives no overall score.
- Chakrabarty et al., [AI-Slop to AI-Polish?](https://arxiv.org/abs/2504.07532) (2025): general LLMs barely beat random on a consolidated writing-quality preference benchmark, while reward models trained on expert edits did better. The skill does not use their model, which was trained mostly on literary writing.

## Tools and other skills

- [sloplint](https://github.com/benjaminjackson/sloplint): regex rules for rhetorical model tells, run by `check-prose.sh`. The questions in its judge catalog (`docs/JUDGE.md`), such as whether a paragraph names anything checkable, how it ends, and whether a sentence tells the reader something new, shaped the `prose-reviewer` rubric.
- [slop-guard](https://github.com/eric-tramel/slop-guard): rule-based scoring for word lists, structure, and rhythm, also run by `check-prose.sh`.
- Agent skills: [Docker Write](https://github.com/docker/docs/blob/main/.agents/skills/write/SKILL.md), [Cloudflare Prose](https://github.com/cloudflare/computer/blob/main/.agents/skills/prose/SKILL.md), and [Writing Clearly and Concisely](https://github.com/obra/the-elements-of-style/blob/main/skills/writing-clearly-and-concisely/SKILL.md).
- Editing skills: [General Writing](https://github.com/msimchowitz/writing-skills/blob/main/for-agents/general-writing/SKILL.md), [Humanizer](https://github.com/blader/humanizer/blob/main/SKILL.md), [No AI Slop](https://github.com/petergyang/no-ai-slop/blob/main/skills/no-ai-slop/SKILL.md), and [ASD-STE100 skill](https://github.com/danyuchn/asd-ste100-skill/blob/master/SKILL.md).
