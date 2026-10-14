export const meta = {
  name: 'review',
  description: 'Parallel Claude and Codex reviewers per domain, then merge, group and triage the findings',
  phases: [
    { title: 'Review', detail: 'one read-only reviewer per domain and engine' },
    { title: 'Group', detail: 'merge duplicates and batch related findings' },
    { title: 'Triage', detail: 'verify, prioritize and propose fixes per batch' },
  ],
}

const { repoRoot, reviewDir, skillDir, claudeDomains, codexDomains } = args
for (const key of ['repoRoot', 'reviewDir', 'skillDir']) {
  if (typeof args[key] !== 'string') throw new Error(`args.${key} must be a string`)
}
if (!Array.isArray(claudeDomains) || !Array.isArray(codexDomains)) {
  throw new Error('args.claudeDomains and args.codexDomains must be arrays')
}

const SEVERITY = { type: 'string', enum: ['blocker', 'major', 'minor'] }
const FINDING_PROPERTIES = {
  claim: { type: 'string' },
  locations: { type: 'array', items: { type: 'string', description: 'path:line' } },
  severity: SEVERITY,
  confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
  evidence: { type: 'string' },
  fix: { type: 'string' },
}
const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    reviewer_status: { type: 'string', enum: ['ok', 'failed'] },
    checked_summary: { type: 'string' },
    findings: {
      type: 'array',
      items: { type: 'object', properties: FINDING_PROPERTIES, required: Object.keys(FINDING_PROPERTIES) },
    },
  },
  required: ['reviewer_status', 'checked_summary', 'findings'],
}
const MERGED_FINDING_PROPERTIES = { ...FINDING_PROPERTIES, raised_by: { type: 'array', items: { type: 'string' } } }
const GROUP_SCHEMA = {
  type: 'object',
  properties: {
    batches: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          theme: { type: 'string' },
          findings: {
            type: 'array',
            items: {
              type: 'object',
              properties: MERGED_FINDING_PROPERTIES,
              required: Object.keys(MERGED_FINDING_PROPERTIES),
            },
          },
        },
        required: ['theme', 'findings'],
      },
    },
  },
  required: ['batches'],
}
const TRIAGED_FINDING_PROPERTIES = {
  id: { type: 'string' },
  claim: { type: 'string' },
  locations: { type: 'array', items: { type: 'string' } },
  verdict: { type: 'string', enum: ['confirmed', 'plausible', 'rejected'] },
  verdict_reason: { type: 'string' },
  priority: { type: 'string', enum: ['fix', 'worth fixing', 'deprioritized', 'rejected'] },
  priority_reason: { type: 'string' },
  severity: SEVERITY,
  fix: { type: 'string' },
}
const TRIAGE_SCHEMA = {
  type: 'object',
  properties: {
    triaged: {
      type: 'array',
      items: {
        type: 'object',
        properties: TRIAGED_FINDING_PROPERTIES,
        required: Object.keys(TRIAGED_FINDING_PROPERTIES),
      },
    },
  },
  required: ['triaged'],
}

const bundleLine = `Review bundle: ${reviewDir}. Repo: ${repoRoot}.`

phase('Review')
const reviewers = [
  ...claudeDomains.map(domain => ({ domain, engine: 'claude' })),
  ...codexDomains.map(domain => ({ domain, engine: 'codex' })),
]
const reviews = await parallel(reviewers.map(({ domain, engine }) => () => {
  const label = `${engine}:${domain}`
  const run = engine === 'claude'
    ? agent(
        `You are the ${domain} reviewer. Read ${skillDir}/common.md, then ${skillDir}/${domain}.md, then follow them. ${bundleLine}`,
        { label, phase: 'Review', schema: REVIEW_SCHEMA, agentType: 'review-reader', model: 'opus', effort: 'high' },
      )
    : agent(
        `Domain: ${domain}. Repo root: ${repoRoot}. Review dir: ${reviewDir}.`,
        { label, phase: 'Review', schema: REVIEW_SCHEMA, agentType: 'codex-reviewer', model: 'haiku', effort: 'low' },
      )
  return run.then(review => review && { ...review, reviewer: label })
}))

const failedReviewers = reviewers
  .map(({ domain, engine }, index) => ({ label: `${engine}:${domain}`, review: reviews[index] }))
  .filter(({ review }) => !review || review.reviewer_status === 'failed')
  .map(({ label, review }) => (review ? `${label} (${review.checked_summary})` : `${label} (agent died)`))
const completedReviews = reviews.filter(review => review && review.reviewer_status === 'ok')
const rawFindings = completedReviews.flatMap(review =>
  review.findings.map(finding => ({ ...finding, raised_by: [review.reviewer] })))
const checkedSummaries = completedReviews.map(review => `${review.reviewer}: ${review.checked_summary}`)
if (failedReviewers.length) log(`Failed reviewers: ${failedReviewers.join('; ')}`)
log(`${rawFindings.length} raw findings from ${completedReviews.length}/${reviewers.length} reviewers`)

if (!rawFindings.length) {
  return { failedReviewers, checkedSummaries, rawFindingCount: 0, triaged: [], untriaged: [] }
}

phase('Group')
const grouping = await agent(
  `You are merging and grouping code review findings from parallel reviewers. ${bundleLine}

1. Merge findings that share a root cause, even if worded differently. Union their raised_by lists, keep the
   clearest claim and the strongest evidence and fix, and take the higher severity and confidence. Do not merge
   findings that only share a file.
2. Do not drop, judge or rewrite findings beyond merging; triage happens later. Every input finding must end up in
   exactly one output finding.
3. Group the merged findings into batches of roughly 3-10 related findings: same file or subsystem first, same
   root cause second. Aim for 2-5 batches; use more only when there are more than about 50 findings. Give each
   batch a short theme.

Read code only when you need it to decide whether two findings are the same issue.

Findings:
${JSON.stringify(rawFindings, null, 1)}`,
  { label: 'group', phase: 'Group', schema: GROUP_SCHEMA, agentType: 'review-reader', model: 'opus', effort: 'high' },
)
if (!grouping) throw new Error('Grouping agent died; resume this run to retry it')

let nextId = 1
const batches = grouping.batches.map(batch => ({
  theme: batch.theme,
  findings: batch.findings.map(finding => ({ id: `F${nextId++}`, ...finding })),
}))
const mergedFindings = batches.flatMap(batch => batch.findings)
const mergedRaisers = new Set(mergedFindings.flatMap(finding => finding.raised_by))
const lostReviewers = completedReviews
  .filter(review => review.findings.length && !mergedRaisers.has(review.reviewer))
  .map(review => review.reviewer)
if (lostReviewers.length) log(`Warning: grouping dropped every finding from ${lostReviewers.join(', ')}`)
log(`${rawFindings.length} raw findings merged into ${mergedFindings.length}, in ${batches.length} batches`)

phase('Triage')
const triageResults = await parallel(batches.map((batch, index) => () => agent(
  `Read ${skillDir}/triage.md and follow it. ${bundleLine}

Batch theme: ${batch.theme}
Findings:
${JSON.stringify(batch.findings, null, 1)}`,
  { label: `triage:${index + 1}`, phase: 'Triage', schema: TRIAGE_SCHEMA, agentType: 'review-reader', model: 'opus', effort: 'high' },
)))

const findingsById = new Map(mergedFindings.map(finding => [finding.id, finding]))
const triaged = triageResults
  .filter(Boolean)
  .flatMap(result => result.triaged)
  .filter(entry => findingsById.has(entry.id))
  .map(entry => ({ ...entry, raised_by: findingsById.get(entry.id).raised_by }))
const triagedIds = new Set(triaged.map(entry => entry.id))
const untriaged = mergedFindings.filter(finding => !triagedIds.has(finding.id))
if (untriaged.length) log(`Warning: ${untriaged.length} findings were not triaged: ${untriaged.map(f => f.id).join(', ')}`)

const PRIORITY_ORDER = ['fix', 'worth fixing', 'deprioritized', 'rejected']
const SEVERITY_ORDER = ['blocker', 'major', 'minor']
triaged.sort((left, right) =>
  PRIORITY_ORDER.indexOf(left.priority) - PRIORITY_ORDER.indexOf(right.priority)
  || SEVERITY_ORDER.indexOf(left.severity) - SEVERITY_ORDER.indexOf(right.severity))

return { failedReviewers, checkedSummaries, rawFindingCount: rawFindings.length, triaged, untriaged }
