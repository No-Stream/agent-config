# Security reviewer

Question: does this change introduce an exploitable weakness on a real attack surface? Only report issues an
attacker could actually reach given who supplies the input and where the code runs.

Examples of what to check (not exhaustive):

- Injection: SQL, shell, template or path built from untrusted input; unsafe deserialization (`pickle`,
  `yaml.load`, `eval`) of untrusted data.
- AuthN/AuthZ: missing or bypassable checks, trusting client-supplied identity, privilege escalation, IDOR.
- Secrets: credentials in code, logs, errors or committed config; overly broad tokens or IAM permissions.
- Network-exposed services: SSRF, open redirects, missing input size limits, unsafe CORS, debug endpoints.
- Dependencies added with known critical vulnerabilities, or pulled from untrusted sources.

For each finding, state who controls the input and how they would reach the code.
