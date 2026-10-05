## When To Consult

Use this reference when a Python 3.12 change introduces workers, queues, locks, futures, tasks, shared caches, shared file or network resources, or any assumption that execution cannot overlap with itself. Inspect the actual execution path first; if the code is effectively sequential, keep it simple.

Apply concurrency decisions in this order: correctness and safety, explicit user requirements, repository or runtime configuration, established local conventions, then general Python guidance. This reference does not choose a universal library or framework policy. Confirm the project's runtime model and documented guarantees before relying on particular primitives, thread safety, atomicity, or memory visibility.

## Adoption And Hazard Review

Introduce concurrency only when it meaningfully improves structure, responsiveness, schedule decoupling, or measured throughput. Do not assume extra threads help processor-bound work unless the runtime and deployment actually provide useful parallel capacity. If independent waiting cannot overlap, or the sequential version already meets the need, keep execution single-threaded. Measure where time is spent before changing the model; when unit timing is misleading, prefer production-relevant benchmarks or load tests.

Before editing concurrent code, identify what is shared: mutable objects, files, sockets, caches, database rows, transactions, shutdown flags, and any precision-sensitive calculations or ownership assumptions. Ask whether copying, partitioning, or ownership transfer removes the need for sharing. When shared access remains possible, review every update path, read-modify-write path, and shutdown path instead of checking only the happy path.

Avoid shared mutable state where practical. When sharing is necessary, guard the complete correctness invariant with the smallest documented synchronization region that is still large enough to be correct. A lock around one method call is not enough when correctness spans a check-then-act sequence, a read-update-publish sequence, or several calls on the same shared object. Do not rely on a narrow atomic or nonblocking primitive when the real invariant is wider. Prefer one safe API or adapter that owns the full operation; when you do not own the object, client-side locking around the whole sequence may be the least bad option. A failure-and-cleanup pattern is acceptable only when the failure is explicitly made harmless.

## Lifecycle And Coordination

Keep worker creation, scheduling, limits, retries, and shutdown behavior separate from ordinary application logic. Put tunable settings such as worker count, queue bounds, or backoff configuration where callers and tests can see and vary them. Test as much behavior as possible without concurrent execution, then keep the concurrent wrapper small enough that the remaining interleaving risk is clear. Simple systems may temporarily tolerate direct worker creation, but unbounded creation remains risky, especially for public or high-user paths.

Match the design to a known coordination model before optimizing throughput. A bounded queue usually calls for a producer-consumer shape. Shared resources with many reads and fewer updates need an explicit plan for correctness, starvation, and throughput. Multiple exclusive resources require an explicit acquisition strategy. Prefer a library-provided blocking queue or equivalent coordination primitive when it matches the invariant, but choose between threads, tasks, processes, pools, futures, or sequential code only after checking repository conventions and runtime documentation.

## Deadlock And Stress Testing

When concurrent paths can acquire multiple finite or exclusive resources, review the deadlock conditions rather than treating hangs as random. Break at least one condition deliberately, then account for the cost of that choice. Removing mutual exclusion helps only when the resource can actually be shared. Acquire-all-or-release-and-retry can break lock-and-wait, but it may introduce starvation, livelock, or poor throughput. Safe preemption works only when owners can release state and restart safely. Global acquisition ordering can break circular wait, but it may be infeasible when later resources are discovered only after earlier work begins. Keep concurrency code isolated enough that these strategies can be changed experimentally.

Treat sporadic concurrent failures as real candidates, not noise. Vary worker counts, loads, iteration counts, scheduling pressure, and configuration when testing timing-sensitive code. Investigate every failure. Keep scheduler perturbation, jitter, or instrumentation out of production execution paths; a production no-op hook is acceptable only when the perturbing implementation remains test-only. Repeated stress tests reduce risk but do not prove safety. Use instrumentation to shorten search time when available, use more workers than cores when the goal is to increase switching, and use production-like loads when the project can simulate them safely.

## Validation And Example Route

Validate concurrent changes with the repository-approved focused tests nearest the edited module and, when feasible, the standard test target. Prefer tests that vary completion order, load, or worker count over tests that merely sleep and hope an interleaving occurs. If the design depends on a bounded queue, shutdown rule, or compound cache operation, add tests that prove those invariants directly and report skipped broad checks explicitly instead of implying they passed.

For a worked example that keeps the concurrent surface narrow, protects a compound cache invariant, and scopes stress validation carefully, see [concurrency](../examples/concurrency.md).
