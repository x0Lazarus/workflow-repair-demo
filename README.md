# A reliable order-export import

**A small portfolio demonstration by x0Lazarus.** All records are synthetic. This is a working example of a proposed workflow-repair service, not a client engagement, testimonial, revenue claim, or production certification.

A fragile CSV import can split a quoted customer field at its embedded comma and shift every later column. This repair reads CSV correctly, preserves leading-zero order IDs, normalizes dates and currency codes, and produces deterministic JSON with exact integer money values.

| Before example | Repaired workflow |
| --- | --- |
| Splitting `"  Demo, North  "` at every comma produces six fields instead of five | The quoted value becomes the single customer reference `Demo, North` |
| Import fails before producing usable structured orders | Three synthetic orders import successfully; `00017` remains a string |
| A naive extension could silently round an amount such as `19.999` | Unsupported precision rejects the whole import with a line-numbered error |
| Output replacement behavior is unspecified in the before example | Validation finishes first; a same-directory temporary file replaces the output only on success |

The deliberately broken [before example](examples/before_naive.py) only reads the bundled synthetic file and prints the parsing error. It writes nothing. The money and output guarantees are additional requirements of the repair, not claimed observed customer incidents.

## Run it

Requires **Python 3.10 or newer**. No third-party packages, API keys, network access, or paid services are needed. Run from this directory, using a modern interpreter. On Windows with the Python launcher:

```powershell
py -3.12 examples/before_naive.py
py -3.12 normalize_orders.py examples/orders.csv --output build/orders.json
py -3.12 -B -m unittest discover -s tests -v
```

On a system where `python3` is Python 3.10+:

```sh
python3 examples/before_naive.py
python3 normalize_orders.py examples/orders.csv --output build/orders.json
python3 -B -m unittest discover -s tests -v
```

The output contains three orders and separate totals: **USD 3,000 cents** and **EUR 8,900 cents**. No exchange-rate conversion is performed. Success exits with code `0`.

To see failure handling, first run the successful import above, then:

```powershell
py -3.12 normalize_orders.py examples/invalid_orders.csv --output build/orders.json
```

The command exits `1`, identifies the amount error on line 3, and leaves the previously accepted JSON untouched. CLI argument errors exit `2`. Filesystem and encoding errors are also reported without a traceback.

## Agreed input contract

- UTF-8 CSV, optionally with a UTF-8 BOM. The required headers are exactly `order_id`, `customer_ref`, `order_date`, `amount`, and `currency`; order may vary. Unknown, missing, or duplicate headers fail.
- Physically empty data lines are ignored. Every nonempty data row must have exactly five fields. Outer whitespace is stripped.
- IDs remain strings, are unique after stripping, and contain 1-64 ASCII letters, digits, dots, underscores, or hyphens, starting with a letter or digit. IDs are case-sensitive.
- Customer references contain 1-200 printable characters. Quoted commas work; embedded control characters do not.
- Dates must be `YYYY-MM-DD` or explicitly **US `MM/DD/YYYY`**, including zero padding. The importer checks that the calendar date exists and does not guess locale.
- Amounts are positive, at most `999999999.99`, and have zero, one, or two fractional digits. No currency symbols, thousands separators, signs, exponents, leading whole-number zeroes, or silent rounding. Integer arithmetic converts money to minor units.
- Supported currencies are USD, EUR, GBP, CAD, and AUD, all represented with two decimal places. Codes normalize to uppercase. Other currencies, refunds, and zero-value orders are deliberately unsupported.
- Output order matches source order. `schema_version` is `1`; totals are grouped by currency. No timestamp is inserted, so identical input produces identical JSON.

## Evidence and limits

The 16 unittest tests exercise correct parsing, exact money, BOM/reordered headers, duplicate IDs, malformed dates and CSV, missing/extra fields, unsupported values, CLI behavior, deterministic output, and preservation of an existing destination on validation or simulated replacement failure. Tests use synthetic files under `build/`.

See [VALIDATION.md](VALIDATION.md) for the executed checks and sample-output fingerprint.

This is a single-machine batch demonstration for modest exports, with the whole validated dataset held in memory. It reports the first error, does not deduplicate automatically, and has no accounting-system connector, scheduler, reconciliation against an external system, customer data, or production monitoring. Concurrent successful runs to the same destination have last-writer-wins behavior. Atomic replacement prevents a partially written JSON destination under normal local-filesystem operation; it is not a guarantee against power loss or every network-filesystem behavior. The output file can be replaced when `--output` points at an existing file, so retain backups separately.

## License

Author and project owner: **x0Lazarus**. Copyright (c) 2026 x0Lazarus.

The included tests and sample workflows validate the documented behavior. These checks do not establish production qualification. Review the code and its limitations before adapting it for a client.

Released under the [MIT License](LICENSE).

See [OFFER.md](OFFER.md) for the proposed bounded service packages.
