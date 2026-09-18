# Executed validation

Owner: **x0Lazarus**. All inputs were the bundled synthetic fixtures. No external service, customer account, or paid API was used.

Environment: Windows, bundled **CPython 3.12.14**, standard library only.

| Check | Observed result |
| --- | --- |
| `python -B -m unittest discover -s tests -v` | 16 tests passed |
| `python -B examples/before_naive.py` | Demonstrated six fields instead of five and a truncated customer reference; no output file written |
| Valid CSV through the repaired CLI | Exit 0; three orders; original leading-zero IDs preserved |
| Output totals | USD 3,000 minor units; EUR 8,900 minor units |
| Invalid fixture targeting the existing valid JSON | Exit 1; line-3 amount error; existing output bytes unchanged |
| Simulated output-replacement failure | Test verified existing destination retained and temporary file cleaned up |
| Repeat valid import | Test verified byte-for-byte deterministic JSON |

SHA-256 of the generated `build/orders.json`:

```text
3f10ab6578bfc01fa8e83b71c8f50eaf9bc85e931ef915e625ec6ba8e8cde5bb
```

The valid output was fingerprinted before and after an invalid import; the bytes were identical. The hash fingerprints this sample output, not the implementation or a signed release.

These checks establish behavior for the supplied schema and fixtures. They do not establish production suitability, performance on large exports, compatibility with arbitrary CSV producers or network filesystems, resilience to power failure, or customer demand.
