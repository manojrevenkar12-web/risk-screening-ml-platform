"""Near-duplicate detection. Syndicated news arrives many times with small edits; scoring and tagging each copy pays
for the same story twice and floods analysts with repeats."""

from __future__ import annotations

import hashlib


def simhash(text: str, shingle: int = 3) -> int:
    words = text.split()
    grams = [" ".join(words[i:i + shingle]) for i in range(max(1, len(words) - shingle + 1))]
    acc = [0] * 64
    for g in grams:
        h = int.from_bytes(hashlib.blake2b(g.encode(), digest_size=8).digest(), "big")
        for b in range(64):
            acc[b] += 1 if h >> b & 1 else -1
    return sum(1 << b for b in range(64) if acc[b] > 0)


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


class Deduper:
    """Keeps the SimHash of recent stories in `bands` bands, so a lookup compares only documents that agree exactly on
    at least one band (locality-sensitive hashing), then checks the full Hamming distance."""

    def __init__(self, max_hamming: int, shingle: int, bands: int = 16):
        self.max_hamming, self.shingle, self.n = max_hamming, shingle, bands
        self.width = 64 // bands
        self.mask = (1 << self.width) - 1
        self.bands: list[dict[int, list[tuple[int, str]]]] = [{} for _ in range(bands)]

    def seen(self, doc_id: str, text: str) -> str | None:
        """The id of an earlier copy of this story, or None (and remember this one)."""
        h = simhash(text, self.shingle)
        for i in range(self.n):
            for other, oid in self.bands[i].get(h >> (self.width * i) & self.mask, []):
                if hamming(h, other) <= self.max_hamming:
                    return oid
        for i in range(self.n):
            self.bands[i].setdefault(h >> (self.width * i) & self.mask, []).append((h, doc_id))
        return None
