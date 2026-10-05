## Scenario

Task: keep `SpecificationSatisfactoryFilter` concurrent without relying on the
deleted `base.utilities.concurrency` helper.

The useful overlap is per-entity specification evaluation. The class should keep
the public `filter` contract unchanged, preserve output ordering, and continue
to ignore exceptions raised while checking one entity so the rest of the input
can still be processed.

## Repository Evidence

The current implementation lives in
`investiment_analyzer/base/domain/specifications/specification_satisfactory_filter.py`.
It now uses `ThreadPoolExecutor` directly in the two strategy classes:

- `_WithoutTQDM` maps `_return_entity_if_satisfied` over the incoming entities.
- `_WithTQDM` wraps the executor result iterator with `tqdm` for progress
  reporting.

The focused regression coverage is in
`specification_satisfactory_filter_test.py`, and the file passes Pyright with
the constructor worker count typed as `n: int = 5`.

## Poor Approach

```python
def make_unsatisfactory_none(self, entities: Iterable[E]) -> list[E | None]:
    output: list[E | None] = []

    for entity in entities:
        thread = Thread(
            target=lambda: output.append(self._return_entity_if_satisfied(entity))
        )
        thread.start()

    return output
```

## Why It Fails

The example above returns before workers finish, mutates shared state without a
clear coordination boundary, and gives no place to propagate worker failures or
guarantee completion. It also makes output order scheduler-dependent, which
would be a behavioral change from the current filter.

## Preferred Approach

Keep the concurrent surface small and local to the strategy that needs it. Use a
bounded `ThreadPoolExecutor`, let the executor own worker lifecycle, and keep
the filtering contract in one place.

```python
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm


class _WithoutTQDM(_SpecificationSatisfactoryFilterStrategy[E]):
    def __init__(self, specification: AbstractSpecification[E], n: int) -> None:
        super().__init__(specification)
        self._n = n

    def make_unsatisfactory_none(self, entities: Iterable[E]) -> list[E | None]:
        with ThreadPoolExecutor(max_workers=self._n) as executor:
            return list(executor.map(self._return_entity_if_satisfied, entities))


class _WithTQDM(_SpecificationSatisfactoryFilterStrategy[E]):
    def make_unsatisfactory_none(self, entities: Iterable[E]) -> list[E | None]:
        with ThreadPoolExecutor(max_workers=self._n) as executor:
            satisfactory_entities = executor.map(
                self._return_entity_if_satisfied, entities
            )
            return list(
                tqdm(
                    satisfactory_entities,
                    desc=self._desc,
                    leave=self._leave,
                    total=self._total,
                    file=self._output,
                )
            )
```

This keeps the coordination model explicit:

- `max_workers=self._n` is the visible tuning point.
- `executor.map(...)` preserves input order in the produced iterator.
- `with ThreadPoolExecutor(...)` guarantees worker shutdown before returning.
- Per-entity exceptions are handled inside `_return_entity_if_satisfied`, so the
  concurrent wrapper stays simple and does not need result locking.

## Decision Checkpoints

1. Confirm the work can overlap safely. Here each entity check is independent
   from the filter's perspective.
2. Identify shared state before adding threads. This implementation avoids
   shared mutable output structures by letting `executor.map` produce the
   results.
3. Keep exception policy near the business rule. `_return_entity_if_satisfied`
   still decides that one bad entity should be ignored.
4. Keep progress reporting outside the worker body. Wrapping the mapped iterator
   with `tqdm` avoids extra locks for manual progress updates.
5. Type concurrency knobs explicitly. `n: int = 5` is required for this file to
   stay Pyright-clean.

## Resulting Change

The repository no longer needs a generic concurrency helper for this path. The
filter owns its own worker lifecycle, and the behavior remains the same for
callers: satisfied entities are yielded in input order, unsatisfied entities are
discarded, and per-entity specification errors are suppressed.

## Verification

Focused commands that reflect the current implementation:

```bash
poetry run pyright \
  investiment_analyzer/base/domain/specifications/specification_satisfactory_filter.py
poetry run python -m unittest -v \
  investiment_analyzer.base.domain.specifications.specification_satisfactory_filter_test
```

Run broader repository checks only when the concurrent surface change affects
shared contracts outside this module.

## Completion Report

Changed surfaces: the specification filter module and its colocated tests only.
Report the targeted unittest module and the Pyright run separately. If broader
lint or test targets are skipped, call that out explicitly instead of implying a
repository-wide pass.

## Exception Or Counterexample

Do not copy this pattern blindly into code that shares caches, files, database
sessions, or mutable accumulators across workers. In those cases, the executor
is only the outer tool; you still need a design for the shared invariant, such
as a lock, ownership transfer, or a single-threaded adapter around the critical
section.
