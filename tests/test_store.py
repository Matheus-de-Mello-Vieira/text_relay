from threading import Thread
from time import monotonic

from text_relay.store import ResultStore


def add(store: ResultStore, text: str):
    return store.add(text, f"checksum-{text}")


def test_results_are_newest_first() -> None:
    store = ResultStore(maximum_size=3)
    oldest = add(store, "oldest")
    newest = add(store, "newest")

    assert store.recent() == [newest, oldest]


def test_history_is_bounded() -> None:
    store = ResultStore(maximum_size=2)
    add(store, "first")
    second = add(store, "second")
    third = add(store, "third")

    assert store.recent() == [third, second]


def test_wait_for_change_returns_when_a_result_is_added() -> None:
    store = ResultStore(maximum_size=2)
    received: list[list] = []

    thread = Thread(
        target=lambda: received.append(store.wait_for_change(None, timeout_seconds=1))
    )
    thread.start()
    thread.join(timeout=0.05)
    assert thread.is_alive()

    added = add(store, "new")
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert received == [[added]]


def test_wait_for_change_returns_after_timeout_when_history_is_unchanged() -> None:
    store = ResultStore(maximum_size=2)
    existing = add(store, "existing")

    started = monotonic()
    results = store.wait_for_change(store.change_id(), timeout_seconds=0.02)

    assert monotonic() - started >= 0.01
    assert results == [existing]


def test_interrupt_waiters_releases_long_poll_immediately() -> None:
    store = ResultStore(maximum_size=2)
    received: list[list] = []
    thread = Thread(
        target=lambda: received.append(store.wait_for_change(None, timeout_seconds=10))
    )

    thread.start()
    thread.join(timeout=0.05)
    assert thread.is_alive()

    store.interrupt_waiters()
    thread.join(timeout=0.1)

    assert not thread.is_alive()
    assert received == [[]]


def test_finds_retained_result_by_image_checksum() -> None:
    store = ResultStore(maximum_size=2)
    expected = store.add("text", "checksum")

    assert store.find_by_image_checksum("checksum") == expected
    assert store.find_by_image_checksum("other") is None


def test_jobs_publish_queued_processing_and_completed_states() -> None:
    store = ResultStore(maximum_size=2)

    job = store.enqueue("checksum")
    assert job is not None
    assert store.jobs() == [job]
    assert store.mark_processing(job.id).status == "processing"  # type: ignore[union-attr]
    completed = store.complete(job.id, "text")

    assert completed is not None
    assert completed.status == "completed"
    assert completed.result is not None
    assert store.recent() == [completed.result]
