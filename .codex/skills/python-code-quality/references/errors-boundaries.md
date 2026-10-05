# When To Consult

Use this reference when a change affects exception contracts, `None` handling,
third-party or framework boundaries, resource cleanup, repeated edge-condition
computations, or the shape of `try`/`except` code.

## Exception Contracts

- Make public and internal exception surfaces explicit. Keep non-public helpers
  underscored, document intentional re-exports, and use `__all__` when the
  module API needs to be explicit. If a package or module intentionally exposes
  nothing, `__all__ = []` is acceptable.
- Preserve established public contracts unless the user or repository
  requirements intentionally change them. If callers are meant to import an
  exception from a package `__init__`, document that re-export instead of
  relying on accidental indirect imports.
- Signal ordinary failures with exceptions derived from `Exception`, not return
  codes, boolean flags, or `BaseException` subclasses. Preserve a non-exception
  failure protocol only when an explicit contract requires it.
- Split exception classes only when handlers need different behavior. If
  several low-level failures are handled the same way, prefer one local
  exception plus useful context. Reuse built-in hierarchies such as
  `FileNotFoundError`, `TimeoutError`, `ValueError`, or other `OSError`
  subclasses when they already express the needed distinction.
- Catch the specific exceptions the protected operation is expected to raise.
  Use `except Exception` only for an intentional program-error catch-all.
  Avoid bare `except` except for narrow, documented traceback/logging or
  cleanup cases.
- When translating or wrapping failures, preserve diagnostic value. Prefer
  `raise LocalBoundaryError("...details...") from err` when the original
  context should remain visible. Use `raise ... from None` only when the new
  exception already carries the relevant details and the hidden chain would add
  noise.

## Boundary Adapters And None Handling

- Keep third-party, framework, and externally controlled APIs behind small
  application-owned boundary points that express local needs. Public
  application APIs should not leak broad vendor clients, raw framework
  objects, or loosely shaped provider payloads unless the local use is so small
  and contained that an adapter would add indirection without reducing risk.
- If a provider contract is unstable or not available yet, define the local
  interface first and adapt to the external API later. Type hints and boundary
  validation can clarify access, but they do not replace owning the boundary.
- Do not pass `None` unless the callee explicitly expects it. When `None` is a
  meaningful sentinel, make that contract explicit in types, names, or docs.
  Otherwise treat accidental `None` as a defect or a clear validation failure.
  Assertions may document the contract, but they are not a complete recovery
  strategy.
- Avoid surprising `None` returns. For normal "no results", return an empty
  collection when that is accurate, or use a deliberate special-case value when
  normal flow can continue. For invalid failures, raise an exception instead of
  converting the failure into normal absence. Preserve `None` only when the API
  contract explicitly makes it meaningful.
- When a third-party API returns `None` ambiguously, wrap it so the rest of the
  application sees a clearer contract.
- Encapsulate repeated boundary arithmetic or edge-condition offsets in a named
  value or helper. If code repeats `index - 1`, `end + 1`, date-window edges,
  or sentinel cutoffs across validation and processing, name that computation
  once instead of scattering it.

## Resource Safety And Try Blocks

- Keep protected regions narrow. Put only the operation that may raise inside
  the `try`, and keep success-only work in `else` or after the handler when
  that improves readability and prevents accidental catching.
- Manage local resources with `with` when suitable. Use `try`/`finally` when a
  context manager is not appropriate or not available.
- Do not hide failures with control flow in `finally`. Avoid `return`,
  `break`, or `continue` there when it would suppress an exception or make
  state consistency harder to reason about.
- Keep state mutations on the safe path when possible. Do not update caches,
  partial aggregates, or externally visible state before validation or parsing
  has succeeded unless the operation has deliberate rollback or transactional
  semantics.
- Prefer extracting substantial `try` bodies or `except` bodies into helpers
  when that cleanly separates normal processing from error processing. Do that
  only if extraction preserves traceback behavior, cleanup semantics,
  transaction boundaries, and local readability.

## Validation And Example Route

- Before changing the code, check: what public exception or `None` contract do
  callers already depend on; which low-level details should stay visible; is an
  external-data mismatch a normal absence or a failure; and would a small
  adapter reduce exposed vendor surface.
- If the repository already has gateway, adapter, or package-export patterns,
  follow them unless correctness or explicit requirements demand a change.
- When behavior depends on learned boundary expectations, add focused tests for
  accepted inputs, malformed inputs, and "state not mutated on failure" cases
  when relevant.
- Use [errors-and-boundaries](../examples/errors-and-boundaries.md) for a
  concrete vendor-drift example that keeps parsing, exception translation, and
  `None` contracts separate.
- Use [tests](../examples/tests.md) when the main decision is how to
  characterize boundary behavior or cover failure paths without weakening the
  production contract.
