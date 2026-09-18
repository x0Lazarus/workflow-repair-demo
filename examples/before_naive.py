"""Deliberately broken BEFORE example. Synthetic input only; writes nothing.

Author: x0Lazarus. This illustrates a common parsing mistake, not client history.
"""

from pathlib import Path


if __name__ == "__main__":
    source = Path(__file__).with_name("orders.csv")
    first_record = source.read_text(encoding="utf-8").splitlines()[1]
    pieces = first_record.split(",")
    print("BEFORE: naive comma-splitting of the synthetic first order")
    print(f"Expected fields: 5; actual fields: {len(pieces)}")
    print(f"Incorrect customer field: {pieces[1]!r}")
    print("The quoted customer comma shifts every following field.")
    print("No output file was written. Run normalize_orders.py for the repair.")
