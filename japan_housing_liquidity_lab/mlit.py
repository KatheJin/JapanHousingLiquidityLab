"""Inspect a user-provided local CSV without guessing a fixed MLIT schema."""
import csv
import hashlib
from pathlib import Path


def inspect_csv(path, encoding=None):
    path = Path(path)
    if not path.is_file():
        raise ValueError("CSV file does not exist")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    candidates = [encoding] if encoding else ["utf-8-sig", "cp932"]
    for candidate in candidates:
        try:
            with path.open(encoding=candidate, newline="") as source:
                reader = csv.reader(source, strict=True)
                headers = next(reader, None)
                if not headers or any(not name.strip() for name in headers):
                    raise ValueError("CSV requires nonempty column names")
                if len(set(headers)) != len(headers):
                    raise ValueError("duplicate column names")
                missing = [0] * len(headers)
                count = malformed = 0
                for row in reader:
                    if not row:
                        continue
                    count += 1
                    if len(row) != len(headers):
                        malformed += 1
                        continue
                    for i, value in enumerate(row):
                        missing[i] += not value.strip()
            return {"filename": path.name, "sha256": digest.hexdigest(),
                    "encoding": candidate, "rows": count,
                    "valid_rows": count - malformed, "malformed_rows": malformed,
                    "columns": headers, "missing_in_valid_rows": dict(zip(headers, missing)),
                    "note": "Local schema inspection only; no listing-duration labels inferred."}
        except UnicodeDecodeError:
            if encoding:
                raise ValueError("CSV cannot be decoded using requested encoding") from None
    raise ValueError("CSV is neither UTF-8 nor CP932; specify --encoding")
