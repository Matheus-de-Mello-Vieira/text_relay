## Scenario
Add a data source through an explicit boundary, not speculative architecture.

Task: add a new market-data provider for stock prices while keeping valuation code independent from vendor clients, cache keys, and payload shapes.

## Repository Evidence
This repository already separates domain and data-source code: valuation strategies live under `investiment_analyzer/variable_income/domain/enterprise_stock/valuation`, provider collectors live under `investiment_analyzer/variable_income/data_source/enterprise_stock/prices`, and `base/domain/patterns/container.py` owns dependency wiring. `AbstractPriceCollector` is already the domain-facing collaborator. Validation should use project entrypoints: `make lint`, focused `poetry run python -m unittest ...`, and `make test` when wiring changes affect shared behavior.

## Poor Approach
Do not put the provider in a valuation strategy:

```python
class EnterpriseValuationByGordon(EnterpriseStockValuationStrategy):
    def _current_price(self, search_code: str) -> Money:
        response = requests.get(f"{BRAPI_URL}/quote/{search_code}", timeout=15)
        frame = pd.DataFrame(response.json()["results"])
        return Money.real(frame.iloc[0]["regularMarketPrice"])
```

Why it fails: the valuation class now owns HTTP, payload, and provider-failure concerns, while `MarketDataPlugin`, `PluginRegistry`, and provider discovery add architecture before a second real provider has different lifecycle rules.

## Preferred Approach
Use the existing boundary. Add provider-specific work in a collector, then wire it where dependencies are constructed:

```diff
 class ConcretePriceCollector(AbstractPriceCollector):
     def __init__(
         self,
         cache_folder: Path = Provide["cache_folder"],
         price_history_store: AbstractPriceHistoryStore | None = None,
         price_history_cache: ParquetTimeSeriesCache | None = None,
-        yfinance_collector: YfinancePriceHistoryCollector | None = None,
+        history_collector: PriceHistoryCollector | None = None,
     ) -> None:
         ...
-        self._yfinance_collector = yfinance_collector or YfinancePriceHistoryCollector()
+        self._history_collector = history_collector or BrapiPriceHistoryCollector()
```

`BrapiPriceHistoryCollector` owns HTTP, retries, JSON validation, and normalization to `OHLCVSchema`. The valuation strategy still receives an `AbstractPriceCollector` or the already-computed values it needs; it does not import `requests`, vendor payload keys, cache folders, or dependency-injector providers.

## Decision Checkpoints
- Construction and configuration stay in the container or gateway setup; use sites receive collaborators.
- Domain logic speaks in stock prices and valuation inputs, not HTTP responses or cache hashes.
- A small `PriceHistoryCollector` protocol is justified only if both existing and new collectors share the same current, tested method shape.
- Shared retry or payload validation is extracted only after duplicate gateway code proves the responsibility is common.
- A short note in the implementation plan records why plugin discovery was deferred: one provider does not yet prove a stable extension axis.

## Resulting Change
The narrow change touches:
- `variable_income/data_source/enterprise_stock/prices/brapi_price_history_collector.py`
- `variable_income/data_source/enterprise_stock/prices/concrete_price_collector.py`
- the container wiring or composition root that selects the collector
- focused gateway and valuation tests

Behavior is preserved for existing callers: `AbstractPriceCollector.get_price_history()` still returns normalized `OHLCVSchema`, and valuation code keeps the same public calculation API.

## Verification
- `poetry run python -m unittest investiment_analyzer.variable_income.domain.enterprise_stock.valuation.enterprise_valuation_test`
- `poetry run python -m unittest investiment_analyzer.variable_income.data_source.enterprise_stock.prices.concrete_price_collector_test`
- `make lint`
- `make test` when container wiring or shared collector contracts changed

If network credentials for the new provider are unavailable locally, gateway tests use synthetic payloads and the live-provider check is reported as skipped, not passed.

## Completion Report
Report the provider files, wiring, and tests changed. State whether domain behavior was preserved, whether the new provider failure path was covered, and which project commands passed, failed, or were skipped.

## Exception or Counterexample
If a second provider later needs runtime discovery, retries with different rate limits, or provider-specific authentication lifecycles, introduce the smallest abstraction that isolates that current, testable variation instead of extending the collector ad hoc.
