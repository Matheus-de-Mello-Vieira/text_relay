# When To Consult

Use this reference when a change touches data carriers, domain objects, public
surface, collaborator boundaries, or required call order. If the requested shape
would add avoidable coupling, unclear responsibility, or exposed internals,
surface that risk and reshape the design before treating it as routine cleanup.

Inspect the local extension pattern before adding a protocol, ABC, registry,
wrapper, or new public entrypoint. Preserve established repository vocabulary
and public/internal conventions unless correctness, safety, or explicit user
requirements force a change.

# Object And Data Boundaries

Classify each construct first:

- A boundary data carrier or persistence record may expose fields directly and
  may mirror provider or storage shape.
- A behavior-bearing object should hide representation behind domain operations.
- A policy object, callable, or protocol is appropriate when behavior varies but
  the rest of the code should call one stable interface.

Keep that classification coherent. Boundary rows, DTOs, and framework-required
records can stay simple and transport-focused. Do not let them accumulate
business rules just because they are convenient to reach. Translate them into
application objects later, or keep business rules in a separate behavior-bearing
object when an Active Record-like form must remain as the persistence shape.

Choose polymorphism by the real change axis. If new behavior-bearing variants are
the part likely to grow, localize selection once and let callers use a stable
interface. If the data shape is stable and new operations are more likely, keep
plain data plus procedural functions. One-off conditionals do not need
abstraction just to satisfy a pattern.

# Public Surface And Protocols

Expose only what clients actually need: operations, data, constants, and helper
entrypoints that are part of the intended API. Keep caches, temporary helpers,
translation details, and provider-specific quirks internal by convention. Do
not widen an API only to satisfy a test until simpler seams fail; broader access
for tests is a last resort, though a genuinely public value can stay public when
it is truly part of the contract.

Shape boundary APIs around application needs instead of forwarding a provider's
entire surface. A small adapter, gateway, protocol, or function layer is often
enough. Reuse an existing boundary pattern in the repository before adding a new
wrapper style.

Use Python's object protocols directly:

- Use `is` and `is not` for singleton checks such as `None`.
- Test boolean state directly instead of comparing to `True` or `False`.
- Use `isinstance` for runtime type checks.
- If a class supports ordering, provide a coherent rich-comparison set or use
  `functools.total_ordering` from a smaller core implementation.

Do not rely on truthiness when the code must distinguish `None` from an
intentionally empty mapping, sequence, or set.

# Responsibilities And Coupling

Keep behavior-bearing classes and modules cohesive around one clear reason to
change. Review signals include methods that touch disjoint state clusters,
feature envy toward another object, unrelated dependencies added for convenience,
and tests that need too many doubles just to reach one behavior.

Respond in small behavior-preserving steps. Extract or move behavior when the
responsibility is misplaced, but do not split a logically complete type without
real change pressure. Feature envy can be the lesser evil when moving the code
would create unrelated coupling. Performance can justify a less obvious
placement if names make that responsibility explicit.

Avoid reaching through chains of behavior-bearing collaborators to do work. Ask
the immediate collaborator for the needed operation instead. Direct traversal of
intentional data structures is still fine; a nested dict, parsed row, or DTO is
not subject to the same rule as hidden object internals.

Reduce artificial coupling with the lightest Python abstraction that isolates
the dependency clearly. An injected callable, small protocol, or relocated
helper may be enough; do not default to inheritance or a new layer unless the
repository already uses it or the change axis justifies it.

# Temporal Coupling And Example Route

When operations must happen in order, make that order visible in the API. Pass
the output of one step into the next, require dependencies at construction, or
use an object or context manager that enforces valid state transitions. Do not
hide required sequencing in comments, broad mutable state, or "call this first"
conventions. Extra ceremony is justified only when it exposes real temporal
complexity.

Identify the actual ordering invariant before changing the API, then make
invalid states hard to represent. For a worked object-versus-data example that
also shows strategy extraction, boundary shaping, and explicit setup, see
[Object Design Example](../examples/object-design.md).
