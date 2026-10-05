## When To Consult

Use this reference when implementation portability, repeated string building, condition idioms, cleanup scope, duplication, or dead-code removal need judgment. Apply it only after correctness and safety, explicit user requirements, repository tooling, and established local conventions.

## Portable Defaults And Local Overrides

- If the task or repository needs portability across Python implementations, avoid relying on CPython-specific behavior unless that dependency is explicit and accepted.
- For repeated string accumulation on performance-sensitive or large paths, collect fragments and use `str.join(...)`; do not rewrite single concatenations or non-sensitive code for speculative speed.
- Use `startswith()` and `endswith()` for prefix or suffix intent when they are semantically equivalent to the existing logic.
- Do not make a string literal's meaning depend on trailing whitespace that editors, formatters, or readers may not preserve.
- Keep closely related lines near each other when that strengthens one idea and does not fight enforced formatting, local layout, or Python's required execution order.

## Clarity And Minimality

- Make intent clear to the next reader. Prefer names, ordering, and structure that reduce maintenance cost, but do not churn working code for subjective taste alone.
- Use Python condition idioms precisely: compare with `is None` or `is not None` when `None` is a distinct sentinel, and use sequence truthiness when emptiness is the real question.
- Keep code and APIs no broader than the requirements demand, but do not remove compatibility behavior, public surface, or boundary-specific detail without evidence that it is unnecessary.
- Apply heuristics with practiced judgment. A smell, style cue, or cleanup opportunity is not an automatic edit command.

## Cleanup Duplication And Dead Code

- When you are already changing code, do not leave an obvious nearby mess behind solely because cleanup could happen later; keep the cleanup small, relevant, and behavior-preserving.
- Refactor through small steps that preserve observable behavior, and separate cleanup from feature changes when the task allows.
- When clear duplication can be removed safely and a shared abstraction states the common idea more clearly, remove it. If the code is only similar, normalize it first only when that helps a later safe refactor.
- Functions, data mappings, dispatch tables, and polymorphism are all valid duplication-removal tools; choose the simplest Python fit instead of forcing a pattern.
- Treat unused or unreachable code as a smell, not as automatic deletion. Check runtime wiring, public APIs, dynamic access, scripts, migrations, compatibility shims, and tests before removing it.
- Static analysis is evidence for dead-code removal, not sole authority.

## Validation And Example Route

- Before cleanup, abstraction, or deletion, confirm current behavior from tests, caller evidence, fixtures, or public contracts.
- Report skipped validation and unresolved usage uncertainty explicitly instead of claiming a cleanup is safe.
- See [general-programming examples](../examples/general-programming.md) for a scoped cleanup that preserves XML behavior, distinguishes `None` from other falsey values, uses `startswith()`, and requires broader usage checks before deleting a helper.
