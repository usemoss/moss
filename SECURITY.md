# Security Policy

We take security issues in Moss seriously. If you believe you have found a
vulnerability, please report it privately so we can investigate and coordinate
a fix before public disclosure.

## Reporting a Vulnerability

Please do not open public GitHub issues for security reports.

Instead, email `contact@moss.dev` with:

- A clear description of the vulnerability
- The affected package, example, or component
- The version, commit SHA, or branch you tested
- Reproduction steps or a proof of concept
- Any known impact, affected environments, or suggested mitigation

Please avoid:

- Accessing data that does not belong to you
- Modifying or deleting data in another account or environment
- Disrupting service availability or degrading system performance
- Using social engineering, spam, or physical attacks

We ask for coordinated disclosure and will work with you to validate the report,
develop a fix, and determine an appropriate disclosure timeline.

## Supported Versions

We currently provide security fixes for the latest stable major release line.

| Version | Supported |
| --- | --- |
| `1.x` | Yes |
| `< 1.0` | No |

If you are reporting an issue against an older release, we may ask you to
upgrade to the latest supported version before we can investigate further.

## Response Timeline

Our targets for private security reports are:

- Acknowledgement within 3 business days
- Initial triage or a request for more information within 7 business days
- Status updates at least every 14 calendar days while the report is open

Complex fixes can take longer depending on severity, exploitability,
dependencies, and release coordination. When a report is confirmed, we will
share the remediation plan and disclosure approach directly with the reporter.

## Public Disclosure

Please do not disclose the issue publicly until we have had a reasonable chance
to investigate and ship a fix or mitigation. Once remediation is available, we
may publish a security advisory, release notes, or other coordinated
communication describing the impact and resolution.
