# Security Boundaries

Read this file before storing anything with the self-improving skill.

## Never Store

| Category | Examples | Why |
| --- | --- | --- |
| Credentials | Passwords, API keys, tokens, SSH keys | Security breach risk |
| Financial | Card numbers, bank accounts, crypto seeds | Fraud risk |
| Medical | Diagnoses, medications, conditions | Privacy risk |
| Biometric | Voice patterns, behavioral fingerprints | Identity theft |
| Third parties | Personal information about other people | No consent obtained |
| Location patterns | Home/work addresses, routines | Physical safety |
| Access patterns | What systems the user can access | Privilege escalation |

## Store With Caution

| Category | Rules |
| --- | --- |
| Work context | Keep project-scoped, decay after the project ends |
| Emotional states | Store only if explicitly requested |
| Relationships | Roles only, no personal details |
| Schedules | General patterns only, not specific times |

## Consent Rules

- Explicit corrections can be logged as corrections.
- Explicit "remember/always/never" preferences can be logged as memory if safe.
- Inferred preferences require confirmation after repeated evidence.
- Cross-session personal patterns require explicit opt-in.

## Red Flags

Stop and do not store if the proposed memory:

- Contains secrets or credentials.
- Is only useful "just in case".
- Infers sensitive information.
- Mentions third-party personal information.
- Would affect behavior in hidden ways the user cannot inspect.

## Forget Requests

If the user asks to forget something:

1. Confirm the matching entry.
2. Remove or mark it as forgotten.
3. Show the updated file or a concise confirmation.
4. Do not keep ghost behavior based on the removed item.
