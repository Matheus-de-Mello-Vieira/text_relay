# Tests

## When To Consult

Use this reference when you are adding or changing tests, protecting an existing behavior during refactoring, choosing validation scope, diagnosing failures, or deciding whether production code needs a seam to become testable.

Treat production behavior as complete only when objective automated tests cover it, including simple behavior that could break. In this repository, keep the standard full-suite route tied to the documented unittest discovery entrypoint:

```bash
poetry run python -m unittest discover -v -s "./investiment_analyzer" -p "*test.py"
```

Use narrower unittest module or package runs for faster feedback when they do not replace the project-approved complete-suite entrypoint. If the project exposes an IDE action or one shell command for the full suite, use that rather than substituting a familiar tool.

See the Phase 7 [tests example](../examples/tests.md) for a concrete mapper-boundary workflow.

## Test Selection And Scope

When you are practicing TDD, keep the cycle small: write the next failing unit test first, add only enough test code to express that failure, then add only enough implementation to pass it. A noncompiling test still counts as failing in that workflow, so do not wait for a polished test before using it to drive the next step.

Before substantial cleanup of existing behavior, add or identify characterization tests, refactor in small steps, and rerun the relevant tests after each step. If you are simplifying structure, do not collapse code entities in a way that weakens running tests, reintroduces meaningful duplication, or hides design intent.

Do not disable failing tests, warnings, or safety checks merely to make a run pass or make exploration easier. Fix the underlying issue unless explicit project policy allows a temporary override, and report that override plainly.

## Readable Reliable Tests

Keep test code clean. Test-only code may accept small efficiency costs for clarity, but not poor names, tangled helper structure, or brittle coupling. If the test environment has production-like constraints, or the clarity tradeoff is no longer small, prefer the more efficient production-style approach.

Each automated test should be independent, repeatable in its intended environment, and self-validating through an objective pass or fail result. Order-dependent cascading failures usually indicate shared mutable state or hidden fixture coupling; arrange each test's own prerequisites instead.

Structure each test around one clear behavior or concept with readable setup, action, and assertion flow. Minimize assertions, but keep multiple assertions when they communicate one concept more clearly than extra helpers, extra indirection, or duplicated setup. Behavior-oriented naming or Given/When/Then-style structure is useful when it makes that single concept easier to read.

Remove setup noise and duplication when it obscures intent. Introduce only the helper API, factory, fixture, or builder needed to make tests read at the domain level.

## Boundary And Failure Paths

When code handles operations that can fail, force the failure path in tests before growing handler behavior. For third-party or volatile boundaries, add focused learning or characterization tests that exercise the boundary the way production code uses it.

Prefer small synthetic payloads or fixtures when the behavior under test is narrow boundary drift. Use broader fixtures only when end-to-end extraction or integration behavior is the actual subject. Actively cover boundaries, corner cases, exceptional paths, and behavior near recently found bugs.

If focused tests are hard to write because production code is tightly coupled to concrete dependencies, volatile services, or risky existing classes, treat that difficulty as design feedback. Improve the design only as far as needed to make behavior verifiable and dependencies replaceable. A small abstraction with a stub, fake, or fixed lookup is appropriate when it is the least risky way to make the boundary testable.

## Reporting And Example Route

Use coverage output and mixed pass/fail patterns diagnostically, not as invented policy thresholds. They are useful for locating untested branches and likely fault locations; when coverage is unavailable, inspect patterns such as input size, argument values, or ordering among failures.

Report validation honestly: which focused tests ran, whether the full-suite entrypoint ran, which format, lint, type, or safety checks ran, and which checks were skipped or unavailable. Do not claim success from commands that did not complete.

Start with the Phase 7 [tests example](../examples/tests.md) for regression, TDD, boundary, and coverage-routing decisions. When the testing task is mainly about exception contracts or boundary adapters, also review the [errors and boundaries example](../examples/errors-and-boundaries.md).
