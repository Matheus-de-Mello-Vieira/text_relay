---
name: python-code-quality
description: Implement, change, refactor, review, debug, test, and maintain Python code. Use for Python-focused code work; not documentation-only tasks, unrelated Git administration, non-Python implementation, or work governed by a more specific skill.
---

## Runtime Workflow
- Determine whether the task is implementation, refactor, debugging-related code change, review, test change, or maintenance work. Identify requested behavior, public contracts, boundary inputs, and validation expectations before editing.
- Inspect repository instructions, configuration, task runners, CI, nearby code, tests, and callers before applying defaults.
- Load only the references and examples needed for the touched surface. Use a review-only path when the user asked for findings without edits.
- Use accessible repository evidence only. If missing access blocks a safe decision, ask for clarification or access and report the resulting confidence limit.
- Plan the smallest coherent change that satisfies the request. When repository evidence marks paths as generated or vendored, avoid manual edits, prefer the source template or generator when available, and report skipped paths when relevant.
- Preserve behavior, names, contracts, side effects, error semantics, resource safety, and dependency boundaries unless the user requested a behavior change or correctness and safety require one.
- Update comments, docstrings, annotations, and tests when the changed behavior or contract makes them stale.
- Validate with the narrowest meaningful checks first, then widen to the repository standard target when shared behavior, public contracts, or risk warrant it.
- Review the diff for accidental churn and keep unrelated cleanup out of scope.

## Precedence Order
1. correctness and safety
2. explicit user requirements
3. repository configuration and enforced tooling
4. established local repository conventions
5. PEP 8 and applicable official Python guidance
6. resolved Clean Code guidance
7. general preferences

Use higher levels before lower ones. Do not let style, examples, or preferences override correctness, safety, user requirements, or repository policy.

## Repository Inspection And Overrides
- Inspect repository instructions, `pyproject.toml`, task runners, CI, type-check configuration, and nearby modules before choosing style, naming, structure, or validation commands.
- Prefer repository wrappers and enforced commands. If repository evidence does not select a different compatible command, fall back to `ruff format`, `ruff check`, `codespell`, `pyright`, and `make test`.
- Treat fallback commands as defaults, not as authority over repository policy.
- Preserve established local conventions when higher-precedence levels do not decide the issue.
- Defer to a directly governing specialized skill when the task is primarily about a narrower Python workflow.

## Validation And Reporting
- Run applicable formatter, lint, spelling, type, and focused-test checks for the changed surface.
- Add or update focused tests for behavior changes, bug fixes, boundary drift, failure handling, or substantial refactors that need characterization.
- Run the repository standard test target when the change affects shared behavior, public contracts, cross-module wiring, or the user explicitly asks for broad validation.
- If a repository-selected command is unavailable, report it as skipped or failed based on whether execution started, and do not substitute another command without repository evidence or user approval.
- Never disable checks for convenience or claim a pass for a command that did not finish successfully.
- Report what changed, what was reviewed, what ran, what failed, what was skipped, and what remains uncertain. For review-only work, lead with findings and state that no edits were made.

## Reference Routing
| When | Read |
| --- | --- |
| Formatting, naming, imports, public attributes, or constants matter | [naming-formatting](references/naming-formatting.md) |
| Function shape, comments, docstrings, annotations, or control flow matter | [functions-comments](references/functions-comments.md) |
| Object roles, cohesion, coupling, protocols, or public surface matter | [object-design](references/object-design.md) |
| Exceptions, `None` contracts, adapters, or resource safety matter | [errors-boundaries](references/errors-boundaries.md) |
| Test scope, regression protection, readability, or boundary coverage matter | [tests](references/tests.md) |
| Dependency boundaries, construction, abstractions, or architecture timing matter | [systems-architecture](references/systems-architecture.md) |
| Shared state, lifecycle, coordination, or concurrency testing matter | [concurrency](references/concurrency.md) |
| Refactoring scope, string handling, duplication, or dead code matter | [general-programming](references/general-programming.md) |

## Example Routing
| Need an example for | Read |
| --- | --- |
| Repository style, naming, constants, and public API compatibility | [style-and-naming](examples/style-and-naming.md) |
| Behavior-preserving cleanup of functions and comments | [functions-and-comments](examples/functions-and-comments.md) |
| Choosing between data carriers, objects, and strategies | [object-design](examples/object-design.md) |
| Hardening boundaries, exceptions, and external input validation | [errors-and-boundaries](examples/errors-and-boundaries.md) |
| Readable regression tests and boundary coverage | [tests](examples/tests.md) |
| Incremental architecture and dependency boundaries | [systems-architecture](examples/systems-architecture.md) |
| Concurrency hazards, lifecycle isolation, and stress-style testing | [concurrency](examples/concurrency.md) |
| Precise cleanup, duplication, and dead-code decisions | [general-programming](examples/general-programming.md) |
