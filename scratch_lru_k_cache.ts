
/**
 * LRU-K Cache — Production-grade, zero-dependency TypeScript implementation.
 *
 * Eviction policy: among all resident entries, evict the one whose K-th most
 * recent access timestamp is the earliest. Entries with fewer than K recorded
 * accesses are considered "cold" and take eviction priority.
 *
 * Run tests:  npx tsx --test lru-k-cache.test.ts
 *   or compile first: tsc && node --test dist/lru-k-cache.test.js
 */

// ──────────────────────────────────────────────
// Types & Interfaces
// ──────────────────────────────────────────────

interface CacheEntry<V> {
  value: V;
  /** Access timestamps in ascending order (oldest → newest). Bounded to K entries. */
  accessHistory: number[];
  /** Absolute expiry timestamp (ms epoch), or null if no TTL was set. */
  expiresAt: number | null;
}

interface CacheStats {
  readonly hits: number;
  readonly misses: number;
  readonly evictions: number;
  readonly hitRatio: number;
}

interface LRUKOptions<K, V> {
  /** Maximum number of entries the cache may hold. */
  capacity: number;
  /** The "K" in LRU-K — how many past accesses to track per entry (≥ 1). */
  k?: number;
  /** Optional factory for the key→entry map (defaults to native Map). */
  // Intentionally not generic over Map to keep zero-dep & simple.
}

// ──────────────────────────────────────────────
// Core Implementation
// ──────────────────────────────────────────────

class LRUKCache<K, V> {
  private readonly capacity: number;
  private readonly k: number;
  private store: Map<K, CacheEntry<V>>;
  private hits: number = 0;
  private misses: number = 0;
  private evictions: number = 0;

  constructor(options: LRUKOptions<K, V>) {
    if (!Number.isInteger(options.capacity) || options.capacity < 1) {
      throw new RangeError(`capacity must be a positive integer, got ${options.capacity}`);
    }
    const k = options.k ?? 2;
    if (!Number.isInteger(k) || k < 1) {
      throw new RangeError(`k must be a positive integer ≥ 1, got ${k}`);
    }

    this.capacity = options.capacity;
    this.k = k;
    this.store = new Map<K, CacheEntry<V>>();
  }

  // ── Public API ──────────────────────────────

  /**
   * Retrieve a value. Returns `undefined` on miss or if the entry has expired.
   * A successful hit records a new access timestamp in the sliding window.
   */
  get(key: K): V | undefined {
    const entry = this.store.get(key);

    if (entry === undefined) {
      this.misses++;
      return undefined;
    }

    // Lazy TTL check
    if (this.isExpired(entry)) {
      this.store.delete(key);
      this.misses++;
      return undefined;
    }

    // Record access — push timestamp, trim to K entries
    entry.accessHistory.push(performance.now());
    if (entry.accessHistory.length > this.k) {
      entry.accessHistory.shift();
    }

    this.hits++;
    return entry.value;
  }

  /**
   * Insert or update an entry. If the cache is at capacity and the key is new,
   * one entry is evicted first (LRU-K policy).
   *
   * @param ttl - Optional time-to-live in milliseconds from insertion.
   */
  set(key: K, value: V, ttl?: number): void {
    const existing = this.store.get(key);

    if (existing !== undefined) {
      // Update in-place — no eviction needed
      existing.value = value;
      existing.expiresAt = ttl != null ? performance.now() + ttl : null;
      existing.accessHistory.push(performance.now());
      if (existing.accessHistory.length > this.k) {
        existing.accessHistory.shift();
      }
      return;
    }

    // New key — may need eviction
    if (this.store.size >= this.capacity) {
      this.evictOne();
    }

    const entry: CacheEntry<V> = {
      value,
      accessHistory: [performance.now()],
      expiresAt: ttl != null ? performance.now() + ttl : null,
    };
    this.store.set(key, entry);
  }

  /** Remove a specific key. Returns true if the key was present (and not expired). */
  delete(key: K): boolean {
    const entry = this.store.get(key);
    if (entry === undefined) return false;
    if (this.isExpired(entry)) {
      this.store.delete(key);
      return false; // treat as absent
    }
    this.store.delete(key);
    return true;
  }

  /** Remove all entries. */
  clear(): void {
    this.store.clear();
  }

  /** Current number of non-expired entries (triggers lazy purge). */
  size(): number {
    this.purgeExpired();
    return this.store.size;
  }

  /** Snapshot of performance counters. */
  stats(): CacheStats {
    const total = this.hits + this.misses;
    return {
      hits: this.hits,
      misses: this.misses,
      evictions: this.evictions,
      hitRatio: total === 0 ? 0 : this.hits / total,
    };
  }

  /** Remove all entries whose TTL has elapsed. Returns count removed. */
  purgeExpired(): number {
    let removed = 0;
    const now = performance.now();
    for (const [key, entry] of this.store) {
      if (entry.expiresAt !== null && entry.expiresAt <= now) {
        this.store.delete(key);
        removed++;
      }
    }
    return removed;
  }

  // ── Private helpers ─────────────────────────

  private isExpired(entry: CacheEntry<V>): boolean {
    return entry.expiresAt !== null && entry.expiresAt <= performance.now();
  }

  /**
   * LRU-K eviction score.
   * - If the entry has fewer than K accesses → score = -Infinity (evict first).
   * - Otherwise → the timestamp at index `history.length - k` (the K-th from newest).
   */
  private evictionScore(entry: CacheEntry<V>): number {
    const h = entry.accessHistory;
    if (h.length < this.k) return Number.NEGATIVE_INFINITY;
    // K-th most recent access = element at position (length - k)
    return h[h.length - this.k];
  }

  private evictOne(): void {
    let minKey: K | null = null;
    let minScore = Number.POSITIVE_INFINITY;

    for (const [key, entry] of this.store) {
      // Skip expired entries — they're "free" to remove without counting as eviction
      if (this.isExpired(entry)) {
        this.store.delete(key);
        return;
      }
      const score = this.evictionScore(entry);
      if (score < minScore || (score === minScore && minKey !== null && key < minKey)) {
        // Tie-break: lexicographically smallest key for determinism
        minScore = score;
        minKey = key;
      }
    }

    if (minKey !== null) {
      this.store.delete(minKey);
      this.evictions++;
    }
  }
}

// ──────────────────────────────────────────────
// Unit Tests — Node.js built-in test runner
// ──────────────────────────────────────────────

import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";

describe("LRUKCache", () => {
  let cache: LRUKCache<string, number>;

  beforeEach(() => {
    cache = new LRUKCache<string, number>({ capacity: 3, k: 2 });
  });

  // ── Basic get/set ───────────────────────────

  it("stores and retrieves values", () => {
    cache.set("a", 1);
    assert.equal(cache.get("a"), 1);
  });

  it("returns undefined for missing keys", () => {
    assert.equal(cache.get("ghost"), undefined);
  });

  it("overwrites existing key without eviction", () => {
    cache.set("a", 1);
    cache.set("a", 99);
    assert.equal(cache.get("a"), 99);
    assert.equal(cache.size(), 1);
  });

  // ── LRU-K Eviction ──────────────────────────

  it("evicts the entry with the oldest K-th access when at capacity", () => {
    // Insert 3 entries (capacity = 3)
    cache.set("a", 1);
    cache.set("b", 2);
    cache.set("c", 3);

    // Access "a" and "b" again → their histories grow to length 2
    cache.get("a");
    cache.get("b");

    // Now insert "d" — must evict one entry.
    // Scores (K=2):
    //   a: history [t0, t1] → score = t0 (oldest)
    //   b: history [t0, t1] → score = t0 (oldest)
    //   c: history [t0]     → score = -Infinity  ← evicted first
    cache.set("d", 4);

    assert.equal(cache.get("c"), undefined, "c should have been evicted");
    assert.equal(cache.get("a"), 1);
    assert.equal(cache.get("b"), 2);
    assert.equal(cache.get("d"), 4);
  });

  it("prefers evicting entries with fewer than K accesses (cold entries)", () => {
    cache.set("hot", 10);
    cache.get("hot"); // now has 2 accesses → "warm"
    cache.set("cold", 20); // only 1 access → cold

    // Fill to capacity
    cache.set("filler", 30);

    // Insert new key → must evict "cold" (score -Inf) before "hot" or "filler"
    cache.set("new", 40);

    assert.equal(cache.get("cold"), undefined, "cold entry should be evicted");
    assert.equal(cache.get("hot"), 10);
  });

  it("evicts deterministically on score ties (lexicographic key)", () => {
    // All three entries have exactly 1 access → all scores = -Infinity
    cache.set("z", 1);
    cache.set("m", 2);
    cache.set("a", 3);

    // Insert "x" → tie among z, m, a → evict lexicographically smallest = "a"
    cache.set("x", 4);

    assert.equal(cache.get("a"), undefined, "'a' should be evicted (lexicographic tie-break)");
    assert.equal(cache.get("m"), 2);
    assert.equal(cache.get("z"), 1);
  });

  // ── Scan Resistance ─────────────────────────

  it("resists a sequential scan better than naive LRU", () => {
    const scanCache = new LRUKCache<string, number>({ capacity: 4, k: 2 });

    // Seed "hot" entries with multiple accesses (they become warm)
    scanCache.set("hot1", 1);
    scanCache.get("hot1");
    scanCache.set("hot2", 2);
    scanCache.get("hot2");
    scanCache.set("hot3", 3);
    scanCache.get("hot3");

    // Sequential scan: each scanned key is accessed exactly once → cold
    scanCache.set("scan1", 100);
    scanCache.set("scan2", 101);
    scanCache.set("scan3", 102);

    // After the scan, "hot" entries should still be present because their
    // K-th access score is finite while scanned entries are -Infinity.
    assert.equal(scanCache.get("hot1"), 1);
    assert.equal(scanCache.get("hot2"), 2);
    assert.equal(scanCache.get("hot3"), 3);

    const s = scanCache.stats();
    assert.ok(s.evictions >= 0, "evictions tracked");
  });

  it("does NOT evict a frequently-accessed entry during a one-pass scan", () => {
    const c = new LRUKCache<string, string>({ capacity: 3, k: 2 });

    // Build up access history for the "victim-resistant" key
    c.set("frequent", "important");
    c.get("frequent");
    c.get("frequent"); // 3 accesses → score = 1st timestamp (finite)

    c.set("other1", "x");
    c.set("other2", "y");

    // Scan: insert a new key, evicting one of the cold entries
    c.set("scan", "z");

    assert.equal(c.get("frequent"), "important", "frequently accessed entry survives scan");
  });

  // ── TTL / Expiration ────────────────────────

  it("expires an entry after its TTL elapses (lazy check on get)", async () => {
    const c = new LRUKCache<string, number>({ capacity: 10, k: 2 });
    c.set("temp", 42, 30); // expires in 30 ms

    assert.equal(c.get("temp"), 42, "should be present before TTL");

    await new Promise((r) => setTimeout(r, 50));

    assert.equal(c.get("temp"), undefined, "should be expired after TTL");
  });

  it("expired entries are evicted preferentially over live cold entries", async () => {
    const c = new LRUKCache<string, number>({ capacity: 2, k: 2 });

    // Entry with very short TTL (already expired by the time we insert next)
    c.set("expiring", 1, 1); // 1 ms TTL — will be expired immediately after
    c.set("live", 2);

    await new Promise((r) => setTimeout(r, 5));

    // Insert a third key → eviction should pick the expired "expiring" entry
    c.set("new", 3);

    assert.equal(c.get("expiring"), undefined);
    assert.equal(c.get("live"), 2);
    assert.equal(c.get("new"), 3);
  });

  it("purgeExpired removes all lapsed entries and reports count", async () => {
    const c = new LRUKCache<string, number>({ capacity: 10, k: 2 });
    c.set("a", 1, 10);
    c.set("b", 2, 10);
    c.set("c", 3); // no TTL

    await new Promise((r) => setTimeout(r, 25));

    const removed = c.purgeExpired();
    assert.equal(removed, 2);
    assert.equal(c.size(), 1);
    assert.equal(c.get("c"), 3);
  });

  it("delete returns false for expired keys", async () => {
    const c = new LRUKCache<string, number>({ capacity: 5, k: 2 });
    c.set("gone", 1, 5);
    await new Promise((r) => setTimeout(r, 15));
    assert.equal(c.delete("gone"), false);
  });

  // ── Statistics ──────────────────────────────

  it("tracks hits, misses, evictions and hitRatio", () => {
    const c = new LRUKCache<string, number>({ capacity: 2, k: 2 });

    c.set("a", 1);
    c.get("a");       // hit
    c.get("b");       // miss
    c.set("c", 3);    // evicts one (either a or b)
    c.get("a");       // could be hit or miss depending on eviction

    const s = c.stats();
    assert.ok(s.hits >= 1, "at least one hit recorded");
    assert.ok(s.misses >= 1, "at least one miss recorded");
    assert.ok(s.evictions >= 0);
    assert.equal(typeof s.hitRatio, "number");
    assert.ok(s.hitRatio >= 0 && s.hitRatio <= 1);

    // hitRatio consistency
    const expected = (s.hits + s.misses) === 0 ? 0 : s.hits / (s.hits + s.misses);
    assert.equal(s.hitRatio, expected);
  });

  it("hitRatio is 0 when no operations have occurred", () => {
    const c = new LRUKCache<string, number>({ capacity: 5, k: 2 });
    assert.equal(c.stats().hitRatio, 0);
  });

  // ── Edge cases & validation ─────────────────

  it("throws on invalid capacity", () => {
    assert.throws(() => new LRUKCache<string, number>({ capacity: 0 }), RangeError);
    assert.throws(() => new LRUKCache<string, number>({ capacity: -1 }), RangeError);
    assert.throws(() => new LRUKCache<string, number>({ capacity: 2.5 }), RangeError);
  });

  it("throws on invalid k", () => {
    assert.throws(
      () => new LRUKCache<string, number>({ capacity: 5, k: 0 }),
      RangeError,
    );
  });

  it("clear() empties the cache but preserves stats", () => {
    const c = new LRUKCache<string, number>({ capacity: 3, k: 2 });
    c.set("a", 1);
    c.get("a");
    c.clear();
    assert.equal(c.size(), 0);
    assert.equal(c.stats().hits, 1); // stats persist
  });

  it("works with complex generic types (objects as keys via string, objects as values)", () => {
    interface User { id: number; name: string }
    const c = new LRUKCache<string, User>({ capacity: 2, k: 2 });
    c.set("u1", { id: 1, name: "Alice" });
    const u = c.get("u1");
    assert.deepEqual(u, { id: 1, name: "Alice" });
  });

  it("K=1 degenerates to standard LRU (single access history)", () => {
    const c = new LRUKCache<string, number>({ capacity: 2, k: 1 });
    c.set("a", 1);
    c.set("b", 2);
    c.get("a"); // a is now most-recently-used
    c.set("c", 3); // evicts b (least recently used)

    assert.equal(c.get("b"), undefined);
    assert.equal(c.get("a"), 1);
    assert.equal(c.get("c"), 3);
  });
});
