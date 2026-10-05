## When To Consult

Use this reference when a change touches function decomposition, signatures,
return behavior, comments, docstrings, type annotations, local helper ordering,
or method placement across collaborators.

Inspect nearby callers, tests, public imports, dynamic entry points, and local
module organization before cleanup. Preserve behavior and local vocabulary
unless correctness, safety, enforced tooling, or explicit requirements require
change.

## Function Design

- Prefer named `def` functions for reusable behavior. Expression-level lambdas
  are still fine when they stay inside a larger expression.
- Name functions and extracted concepts for the operation they perform. Do not
  reuse one term for different semantics unless the parameters and return value
  mean the same thing.
- Keep functions focused on one responsibility, but do not extract helpers just
  to satisfy a size rule. Extract when a coherent step, duplicated logic, or
  real named concept becomes clearer on its own.
- Keep argument lists small. Avoid selector or flag arguments that choose
  behavior; prefer separate functions or a named concept for related values.
  Natural ordered pairs, some necessary dyads, justified triads, and
  homogeneous varargs can still be reasonable. A temporary flag can be
  acceptable if it is part of a safe staged refactor.
- Keep return behavior consistent in value-returning functions. Separate queries
  from commands where practical, and make unavoidable side effects or ordering
  dependencies visible in the function's responsibility and name.
- Remove dead functions or other clutter only after confirming they are not
  public API, framework registration, plugin hooks, migration paths, or dynamic
  dispatch targets.
- When annotations are present, use PEP 484 syntax. Keep runtime type checking
  optional, prefer repository type-checker configuration over ad hoc runtime
  enforcement, use the repository-approved ignore or suppression mechanism for
  non-type uses, and add or ship third-party stubs only when the packaging
  policy allows it.

## Comments And Docstrings

- Keep comments and docstrings accurate. Rewrite or delete stale text when code
  changes.
- Prefer clearer names, variables, structure, or extraction over explanatory
  comments. Keep comments only when they add non-obvious intent, rationale,
  warnings, subtle consequences, or constraints imposed by unchangeable code or
  dependencies.
- Write retained comments as clear prose with normal sentence structure,
  preserve identifier case, and default to English unless the expected readers
  clearly share another language. Follow local sentence-spacing conventions.
- Place comments directly with the code they explain. Use normal Python block
  and inline comment spacing, and avoid comments that require readers to hunt
  elsewhere for context.
- Keep legal, follow-up, and position-marker comments concise and purposeful. Use
  source control for history, an issue tracker for bookkeeping, and delete
  commented-out code unless a narrow requirement keeps it.
- Give public modules, functions, classes, and methods PEP 257-style
  docstrings, including normal one-line and multiline closing quote placement.
  Non-public methods do not need public-API boilerplate; use a private
  docstring or brief nearby explanation only when it genuinely helps.

## Control Flow And Collaboration

- Keep control flow straightforward and shallow. Extract unclear boolean logic
  into named predicates, prefer positive conditionals when practical, and
  refactor until the algorithm is easy to follow.
- Multiple returns, `break`, or `continue` are acceptable in very small
  functions when they improve clarity. Larger functions may justify stricter
  single-exit discipline.
- Avoid empty bodies; if one is intentional, make it explicit with `pass`.
  End-of-block comments are a fallback for long nested code, not a substitute
  for simplifying it.
- Keep related functions close together. Prefer caller-before-callee order when
  Python runtime constraints, import behavior, and local organization allow it;
  otherwise group by conceptual affinity or direct dependency.
- Avoid long collaboration chains across behavior-bearing objects. Split a chain
  into named intermediate values when that alone improves clarity, and move
  behavior to the object that is likely to vary by type or algorithm. Direct
  navigation through plain data structures and pure utility operations over
  arguments can still be acceptable.

## Validation And Example Route

- Before changing signatures, returns, helper placement, or comment removal,
  inspect callers, tests, public surfaces, and dynamic references.
- After behavior-preserving cleanup, run the most focused relevant tests first.
  Run the repository test entrypoint when the change affects wider behavior or
  public contracts. If comments, docstrings, or annotations changed, run the
  configured lint, spelling, and type checks when available.
- For a worked example of extracting real concepts, removing narrative
  comments, keeping one necessary warning comment, and avoiding collaborator
  reach-through, see [Functions And Comments Example](../examples/functions-and-comments.md).
