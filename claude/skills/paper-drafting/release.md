# Submission and release checklist

Load only when the draft is going to a venue or out in public.

## Conference submission

- Confirm the deadline and its time zone. Submit the abstract and the paper at least 24 hours early; resubmit later
  versions as they improve.
- Write in the venue's LaTeX template. For fiddly LaTeX, do not spend more than a few minutes stuck.
- Over the page limit: move the least important subsections to the appendix, merge figures into multi-panel figures,
  then edit at the word level. Word-level editing usually saves 0.5-1.5 pages.
- Venue checklists (for example the NeurIPS checklist) are long and missing one is a desk reject. Start them early.
- Anonymity: no names, no GitHub or Hugging Face links that reveal a username, no identifying acknowledgements.
  Anonymous code hosting (for example anonymous.4open.science) for code links.
- Keywords and topic area: choose by which reviewers you want, not only by best fit.
- Authorship order is the owner's call; flag anyone who contributed and may have been missed.

## Public release

- List the polish and new results that did not make the deadline, estimate cost and value of each, drop the ones not
  worth it, do the rest.
- Restore content cut for the page limit; the arXiv version need not match the conference version.
- Acknowledgements (generous) and an author-contributions statement; a corresponding-author email.
- Code: runs on a fresh machine, has a licence (MIT or Apache 2.0 for reuse), a README, ideally a notebook showing the
  main results.
- Data: release the eval transcripts or samples behind the main results where the repo's privacy and
  benchmark-integrity rules allow, so readers can check the examples themselves.
- arXiv takes about one working day to appear; first-time submitters to cs.LG need an endorsement, so arrange it early.
- Short-form summary (tweet thread, post teaser): the first item does almost all the work. It must make sense to an
  ML reader who does not know a paper is involved, state the key insight in plain words, carry the most eye-catching
  figure, and contain no link.
