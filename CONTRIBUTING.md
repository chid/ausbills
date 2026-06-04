# Contributing

`ausbills` is built around jurisdiction adapters registered in
[ausbills/registry.py](ausbills/registry.py). The supported public API is:

```py
from ausbills import get_bill, get_bills, list_jurisdictions
```

## Adding Or Updating A Jurisdiction

1. Add or update an adapter in [ausbills/adapters.py](ausbills/adapters.py).
   Adapters implement:

   ```py
   def list_bills(self) -> list[Bill]:
       ...

   def get_bill(self, bill_id: str) -> Bill:
       ...
   ```

2. Return normalized [Bill](ausbills/models.py) objects. Put document URLs in
   `DocumentLink` objects and progress state in `Progress`.

3. Use the fetcher passed to the adapter. Do not call `requests` directly from an
   adapter; `backend="auto"` depends on the shared fetch layer to detect source
   blocks and fall back to Playwright where available.

4. Register the adapter in `ADAPTERS` in [ausbills/registry.py](ausbills/registry.py).

5. Add compact fixtures under `tests/fixtures/<jurisdiction>/`:
   `list.html` or `list.json`, plus `detail.html` for at least one bill.

6. Add or update fixture expectations in [tests/test_adapters.py](tests/test_adapters.py).

## Testing

Default tests must not use the network:

```sh
pytest
```

Live smoke tests are opt-in:

```sh
AUSBILLS_LIVE=1 pytest -m live
```

If a source requires browser access and Playwright is not installed, the live
test should skip with `SourceBlockedError` and the browser install guidance.
