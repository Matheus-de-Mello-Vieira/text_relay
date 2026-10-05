# Validate external data even when nearby code is permissive

## Scenario

Task: harden `FedFundsHistoricalSerieGateway.collect_data()` after the FRED CSV response changed from `observation_date,FEDFUNDS` to a different shape. Keep callers receiving a decimal `Series[float]`; the behavior change is only that malformed vendor data now fails clearly before cache mutation.

## Repository Evidence

Economic gateways live under `investiment_analyzer/economy/data_source/third_party_service_gateways/`. Tests are colocated with `*_test.py` and run through Poetry-backed unittest discovery. The repository parsing guidance requires explicit shape validation and clear failures for vendor data, so safety overrides the nearby permissive habit of returning `None` or empty data.

## Poor Approach

```python
def collect_data(self) -> Series[float] | None:
    try:
        response = requests.get(FRED_CSV_URL, params=params, timeout=30)
        df = pd.read_csv(StringIO(response.text))
        self._cache.save(FED_FUNDS_SERIE_CODE, df)
        return cast(Series[float], df.get("FEDFUNDS", pd.Series()) / 100)
    except Exception:
        return None
```

## Why It Fails

This hides malformed external data behind normal absence, leaks cache mutation
onto the failure path, and makes callers guess whether `None` means "no rate"
or "vendor contract drifted." The broad catch also erases the low-level context
needed to diagnose the boundary failure.

## Preferred Approach

Expose one stable boundary error only if callers are meant to catch it, keep the parser helpers internal, validate required columns before conversion, and mutate state only after parsing succeeds. Preserve `None` only for a documented normal absence contract; malformed vendor payloads are not normal absence.

## Decision Checkpoints

- Vendor shape drift is an external boundary failure, not a missing economic indicator.
- Callers do not need separate exceptions for missing columns and invalid numeric values, so one gateway error with context is enough.
- `requests` and `pandas` details stay inside the gateway instead of leaking through the domain-facing mapper.
- The `try` body protects only the vendor call and parse step; cache writes remain on the success path.
- Passing `None` into `StringIO` or `pd.to_numeric` is blocked with validation instead of relying on downstream crashes.

## Resulting Change

```diff
+class FredGatewayError(Exception):
+    pass
+
 def collect_data(self) -> Series[float]:
-    df = pd.read_csv(StringIO(requests.get(FRED_CSV_URL).text))
-    return cast(Series[float], df["FEDFUNDS"] / 100)
+    response = self._fetch_csv()
+    try:
+        df = self._read_fred_csv(response.text)
+        series = self._to_decimal_series(df)
+    except (KeyError, TypeError, ValueError) as err:
+        raise FredGatewayError(
+            "FRED FEDFUNDS response did not match the expected CSV contract"
+        ) from err
+    self._cache.save(FED_FUNDS_SERIE_CODE, series)
+    return series
+
+def _read_fred_csv(self, csv_content: str) -> pd.DataFrame:
+    if not csv_content:
+        raise ValueError("FRED FEDFUNDS CSV response is empty")
+    df = pd.read_csv(StringIO(csv_content))
+    df.columns = df.columns.str.lower()
+    missing_columns = REQUIRED_COLUMNS - set(df.columns)
+    if missing_columns:
+        raise ValueError(f"missing required columns: {sorted(missing_columns)}")
+    return df
```

The focused tests use tiny accepted and drifted CSV payloads: one verifies the decimal series, one verifies missing columns raise `FredGatewayError`, and one verifies the cache is not updated when parsing fails.

## Verification

- `poetry run python -m unittest discover -v -s "./investiment_analyzer/economy/data_source/third_party_service_gateways" -p "fed_funds_serie_gateway_test.py"`
- `poetry run python -m unittest discover -v -s "./investiment_analyzer" -p "*test.py"` when mapper/cache contracts changed.
- `make lint` for repository Ruff, Pyright, and codespell coverage of the gateway code and new error text.

## Completion Report

Report the gateway file and colocated test file as changed. State that malformed vendor data now raises a gateway-owned exception before cache mutation, while normal no-result contracts elsewhere may still return `None` if documented. Do not report the commands above as passed until they have actually run.

## Exception or Counterexample

Counterexample: an internal helper may call `pd.read_csv` directly because it is inside the boundary. That does not justify returning `None` from `collect_data()` for a malformed external response.
