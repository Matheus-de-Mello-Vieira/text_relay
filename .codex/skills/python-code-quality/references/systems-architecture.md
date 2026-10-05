## When To Consult

Use this reference when a change affects dependency ownership, composition roots,
framework coupling, architectural abstractions, reuse choices, or the command
used to build and validate the repository.

- Inspect existing domain, `data_source`, entrypoint, and container patterns
  before introducing a new boundary or abstraction.
- Prefer application-owned boundaries when third-party payloads, clients, or
  package types would otherwise leak across modules.
- Keep the guidance proportional. A small change rarely justifies a new layer,
  registry, plugin mechanism, or framework-specific base class.
- Use [the systems architecture example](../examples/systems-architecture.md)
  when the tradeoff is mainly about where to place a boundary or when to defer a
  heavier architecture.
- Use [the object design example](../examples/object-design.md) when the
  architecture question depends on whether a type should stay as boundary data or
  should carry behavior and invariants.

## Dependency Boundaries

- Keep important dependencies explicit. If application code would otherwise know
  vendor field names, HTTP details, ORM objects, or framework lifecycle APIs,
  put those details behind an adapter, gateway, collector, or other
  application-owned collaborator.
- Move responsibility to the module that owns the fact instead of reaching
  through intermediate objects or assuming another module's internal knowledge.
- Add small abstractions only when they clarify domain intent or isolate a real
  change axis. Do not introduce an interface, protocol, or wrapper for every
  implementation detail.
- Choose the abstraction style that matches current Python usage in the
  repository: protocol, ABC, callable collaborator, helper module, or plain
  function. Inheritance is one option, not the default.
- Keep domain logic framework-light unless the selected framework explicitly
  requires coupling at that boundary. Prefer plain domain objects or functions,
  and keep persistence, logging, security, transactions, caching, and transport
  concerns in decorators, middleware, adapters, or boundary modules when that
  preserves domain clarity.
- When a dependency is introduced or upgraded, verify the behavior the code
  actually relies on. Keep those checks focused on the boundary contract instead
  of re-testing the full vendor library.
- A higher-level abstraction may select between concrete implementations when
  the set is fixed, strongly coupled, and deployed together. Do not treat that
  exception as permission to reverse dependency direction across normal
  architectural boundaries.

## Construction And Configuration

- Keep startup, dependency construction, and high-level configuration separate
  from runtime logic that uses those collaborators. In this repository, prefer
  existing composition points such as container modules, app factories,
  entrypoint scripts, or other established wiring code.
- Runtime objects should receive collaborators or values; they should not
  repeatedly instantiate major dependencies, read service locators, or reach
  into a container to resolve what they need.
- Use a factory only when runtime behavior genuinely needs control over creation
  timing or parameters. Service lookup inside an object is only partial
  injection; the object still owns resolution.
- Pass high-level configuration down as arguments or structured settings instead
  of letting lower-level code discover global configuration on its own.
- Treat lazy construction as an optimization, not as the default architecture.
  A single isolated lazy initialization is not automatically a design problem,
  but broader laziness should be justified by measured lifecycle, startup, or
  resource constraints.

## Architecture And Reuse Decisions

- Use the simplest architecture that satisfies today's requirements while still
  separating concerns enough to change course safely. This does not ban up-front
  design; it rejects speculative complexity without current value.
- Postpone reversible architectural decisions until waiting will produce useful
  evidence, but not so long that correctness, safety, or required separation of
  concerns are neglected.
- Adopt a standard, framework feature, or internal convention only when it has
  demonstrable value for reuse, staffing, integration, or encapsulating proven
  good practice. If a lighter design does the job, prefer the lighter design.
- Organize code so new behavior can be added by localized extension or confined
  edits rather than wide disturbance. If no volatility, boundary pressure, test
  need, or change risk exists, do not add another layer just to "future-proof"
  the code.
- Extract small common behavior when duplicate code truly shares one
  responsibility. When repeated code is only superficially similar, leave it
  local.
- Use a shared algorithm template only when the algorithm is genuinely common
  and the varying steps are well defined. In Python, a helper function,
  strategy callable, composition, or inheritance can all be valid; choose the
  smallest option that fits the current codebase.
- Keep repository-dependent decisions conditional. If the surrounding project
  already enforces a module layout, container library, framework app-factory
  pattern, or gateway structure, follow that existing choice unless it conflicts
  with correctness, safety, or explicit user requirements.

## Validation And Example Route

- Inspect the repository's documented build and validation entrypoints before
  suggesting commands. Prefer the single-step project wrapper when one exists;
  in this repository that is usually `make test` for the standard suite, with
  documented `poetry run python -m unittest ...` commands for focused checks.
- When dependency wiring, framework boundaries, or shared abstractions change,
  run the narrowest meaningful tests first, then the standard project test
  entrypoint when feasible.
- Use repository wrappers for formatting, linting, type checking, and spelling
  when they exist rather than reconstructing ad hoc command sequences.
- Report architecture decisions explicitly: what boundary moved, what was kept
  out of domain logic, whether a new abstraction was deferred, and which checks
  passed, failed, or were skipped.
- Route judgment-heavy tradeoffs through
  [the systems architecture example](../examples/systems-architecture.md) first.
  Use [the tests example](../examples/tests.md) when the question becomes how to
  characterize a new boundary or dependency contract with focused regression
  coverage.
