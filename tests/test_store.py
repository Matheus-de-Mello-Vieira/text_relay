from threading import Thread
from time import monotonic

from text_relay.store import ResultStore


def test_results_are_newest_first() -> None:
    store = ResultStore(maximum_size=3)
    oldest = store.add("oldest")
    newest = store.add("newest")

    assert store.recent() == [newest, oldest]


def test_history_is_bounded() -> None:
    store = ResultStore(maximum_size=2)
    store.add("first")
    second = store.add("second")
    third = store.add("third")

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

    added = store.add("new")
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert received == [[added]]


def test_wait_for_change_returns_after_timeout_when_history_is_unchanged() -> None:
    store = ResultStore(maximum_size=2)
    existing = store.add("existing")

    started = monotonic()
    results = store.wait_for_change(existing.id, timeout_seconds=0.02)

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
