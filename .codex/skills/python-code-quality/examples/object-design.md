# Scenario

Keep records as records and put behavior where invariants live.

## Task

Add a portfolio allocation feature that combines holdings, current prices, and
valuation rules without changing existing `AmountPortfolio` behavior.

## Repository Evidence

Domain behavior lives under `investiment_analyzer/*/domain`; persistence mapping
lives under `data_source`. `PortfolioDataMapper` translates
`PortfolioSchema.asset_amount` into `AmountPortfolio`, while
`AmountPortfolio.contribute()` and its unittest cases live in the portfolio
domain. Transaction objects already expose active/inactive state explicitly.

## Decision Checkpoints

- Classify each type first: parsed rows are boundary data, allocation rules are
  behavior, and price lookup is a collaborator contract.
- Keep persistence keys, JSON field names, and provider payload shapes out of the
  domain API unless they are domain language.
- Add polymorphism only for the real variation axis: the rest-allocation rule is
  varying, not the stored portfolio row.
- Make setup visible by constructing the allocator with prices and a rule.
- Use Python object protocols: test optional prices with `is None`, not truthiness
  that would discard an intentionally empty mapping.
- Preserve the existing `AmountPortfolio.contribute()` result shape and focused
  unittest coverage while extracting responsibility.

## Poor Approach

```python
@dataclass
class PortfolioRow:
    key: str
    asset_amount: dict[str, int]
    asset_repository: AssetRepository
    price_gateway: PriceGateway

    def contribute(
        self,
        contribution: Money,
        ideal_proportions: dict[Asset, float],
        balance_protector: Money,
    ) -> _ContributionPortfolioResult[int]:
        prices = {
            self.asset_repository.find(code): self.price_gateway.current(code)
            for code in self.asset_amount
        }
        portfolio = AmountPortfolio(self.asset_amount)
        return portfolio.contribute(
            contribution,
            ideal_proportions,
            balance_protector,
            asset_prices=prices,
        )
```

This turns a persistence row into a domain object, exposes mapper field names to
the calculation, and couples a simple record to repositories and gateways. The
opposite mistake is leaving the row plain while callers chain through mapper
schemas, enterprise internals, and gateway clients to assemble allocation inputs.

## Why It Fails

The first design over-objectifies raw data and makes domain tests need database
and gateway doubles. The second keeps data simple but scatters invariant-bearing
behavior. Both hide allocation responsibility and make invalid call order likely.

## Preferred Approach

Leave mapper rows as simple boundary data. Convert them to `AmountPortfolio`,
then move the varying rest-allocation behavior behind a small domain strategy.
Use a protocol because tests and callers need that collaborator shape; do not add
inheritance to every portfolio-related type.

## Resulting Change

```diff
+class RestDistributionStrategy(Protocol):
+    def distribute(
+        self, rest: Money, prices: np.ndarray
+    ) -> tuple[np.ndarray, Money]:
+        raise NotImplementedError
+
+@dataclass(frozen=True)
+class PortfolioContributionAllocator:
+    current: AmountPortfolio[int]
+    asset_prices: Mapping[Asset, Money]
+    rest_strategy: RestDistributionStrategy
+
+    def allocate(
+        self,
+        contribution: Money,
+        ideal_proportions: Mapping[Asset, float],
+        balance_protector: Money,
+    ) -> _ContributionPortfolioResult[int]:
+        future_total = (
+            self.current.calculate_total(dict(self.asset_prices))
+            + contribution
+            - balance_protector
+        )
+        floor_amounts, rest = self._floor_targets(future_total, ideal_proportions)
+        extra_amounts, remaining = self.rest_strategy.distribute(
+            rest, self._ordered_prices(ideal_proportions)
+        )
+        return self._build_result(
+            floor_amounts + extra_amounts,
+            remaining + balance_protector,
+        )
```

`AmountPortfolio.contribute()` delegates to this allocator to preserve the public
method while replacing string rule selection with a strategy. Call sites ask the
portfolio API to allocate; they do not navigate through mapper schemas or
provider clients.

## Verification

- Add focused `portfolio/domain/portfolio_test.py` cases for greedy and
  diversity allocation, invalid proportions, and preserved rest money.
- Run `poetry run python -m unittest discover -v -s "./investiment_analyzer/portfolio/domain" -p "*test.py"`.
- Run `make lint` because the strategy protocol and public domain surface are typed.
- Run `make test` if the public portfolio API or shared strategy protocol changes.

## Completion Report

Changed surfaces: portfolio domain allocation code and colocated unittest
coverage only. Behavior is preserved for existing contribution callers; the
change narrows mapper coupling and makes required prices explicit at allocator
construction. Report skipped full-suite validation honestly.

## Exception or Counterexample

A vendor CSV row or `PortfolioSchema` should remain a simple data carrier when it
only transports parsed fields. Adding methods to such a row is not an improvement
unless domain invariants or behavior actually belong there.
