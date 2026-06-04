# ausbills

Get current bills from Australian parliament and legislation sites.

## Install

```sh
pip install ausbills
```

Some government sites use bot protection. Browser support is optional:

```sh
pip install "ausbills[browser]"
playwright install chromium
```

## Usage

The public API is top-level and jurisdiction based:

```py
from ausbills import Jurisdiction, get_bill, get_bills, list_jurisdictions

print(list_jurisdictions())
print(get_bills(Jurisdiction.ACT))
```

Use `include_details=True` to visit each bill detail page and collect document
links, sponsor, portfolio, and summary fields where available:

```py
for bill in get_bills("WA", include_details=True):
    print(bill.as_dict())
```

Fetch a single bill by id:

```py
bill = get_bill("FEDERAL", "r7000")
print(bill.as_json())
```

By default `backend="auto"` tries requests first, detects WAF/challenge pages,
and falls back to Playwright when the browser extra is installed.

## Tests

Default tests are fixture-only and do not use the network:

```sh
pytest
```

Opt-in live smoke tests call official source sites:

```sh
AUSBILLS_LIVE=1 pytest -m live
```

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md).
