# Zarr API Mistakes Catalog

**Date range:** 2026-03-31 to 2026-04-14 (last 2 weeks)
**Sessions scanned:** 53 / 85 (filtered by zarr-related keywords)
**Error turns found:** 630 (26 user corrections, 497 errors, 140 self-corrections)
**Previous full scan:** 68/114 sessions, 982 error turns (2026-04-14)

---

## 1. Icechunk v1 API used in v2 code

**Frequency:** 3+ occurrences | **Signal:** error

Claude uses the removed icechunk v1 store-creation API instead of the v2 Repository pattern.

```python
# WRONG (v1 API)
store = icechunk.IcechunkStore.create(
    storage=icechunk.StorageConfig.filesystem("/tmp/test"),
    mode="w",
)
# also wrong:
store = icechunk.IcechunkStore.open_or_create(
    storage=icechunk.StorageConfig.memory(), mode="w"
)
```

```python
# CORRECT (v2 API)
storage = icechunk.local_filesystem_storage("/tmp/test")
repo = icechunk.Repository.create(storage)
session = repo.writable_session("main")
store = session.store
```

**Error:** `AttributeError: type object 'IcechunkStore' has no attribute 'create'`

---

## 2. `store.list_prefix()` is an async generator, not an awaitable

**Frequency:** 5+ occurrences | **Signal:** error, self_correction

Claude repeatedly tries to `await` or `sync()` the result of `list_prefix()`, or passes it directly to `sorted()`. This applies to both `IcechunkStore` and `MemoryStore`.

```python
# WRONG
all_keys = sync(store.list_prefix(""))           # can't await a generator
keys = sorted(store.list_prefix(""))             # async_generator is not iterable
keys = store.list_prefix_sync("")                # method doesn't exist
```

```python
# CORRECT (async context)
keys = sorted([k async for k in store.list_prefix("")])

# CORRECT (sync context — use zarr to traverse instead)
root = zarr.open_group(store, mode="r")
for name, obj in root.members():
    print(name, obj)
```

**Error:** `TypeError: object builtins.PyAsyncGenerator can't be used in 'await' expression` / `TypeError: 'async_generator' object is not iterable`

---

## 3. Missing `consolidated=False` when opening icechunk stores with xarray

**Frequency:** 3+ occurrences | **Signal:** error

```python
# WRONG
ds = xr.open_zarr(session.store)
```

```python
# CORRECT
ds = xr.open_zarr(session.store, consolidated=False)
```

**Error:** `RuntimeWarning: Failed to open Zarr store with consolidated metadata, but successfully read with non-consolidated metadata. This is typically much slower for opening a dataset.`

---

## 4. `create_array` with both `shape` and `data` arguments

**Frequency:** 3+ occurrences | **Signal:** error

```python
# WRONG — shape and data are mutually exclusive
root.create_array("x", shape=(3,), dtype="i4", data=np.array([1, 2, 3]))
```

```python
# CORRECT — use data alone (shape/dtype inferred)
root.create_array("x", data=np.array([1, 2, 3]))

# OR use shape alone, then write
arr = root.create_array("x", shape=(3,), dtype="i4")
arr[:] = [1, 2, 3]
```

**Error:** `The data parameter was used, but the shape parameter was also used. Either use the data parameter, or the shape parameter, but not both.`

---

## 5. `zarr.open_group(mode='r')` on empty store without catching `GroupNotFoundError`

**Frequency:** 3+ occurrences | **Signal:** user_correction, error

```python
# WRONG — crashes on first iteration of a fresh repo
root = zarr.open_group(store=session.store, mode="r")
```

```python
# CORRECT
from zarr.errors import GroupNotFoundError
try:
    root = zarr.open_group(store=session.store, mode="r")
except GroupNotFoundError:
    return None  # no data committed yet
```

---

## 6. Async store methods called without `await`

**Frequency:** 2+ occurrences | **Signal:** error

When writing directly to the zarr store API (bypassing zarr Array objects), Claude forgets that `store.set()` and `store.delete()` are coroutines.

```python
# WRONG
store.set("arr/zarr.json", buffer)
```

```python
# CORRECT
await store.set("arr/zarr.json", buffer)
```

**Error:** `RuntimeWarning: coroutine 'IcechunkStore.set' was never awaited`

---

## 7. Importing from wrong or internal zarr modules

**Frequency:** 5+ occurrences | **Signal:** error, self_correction

Claude reaches for internal module paths that change between zarr versions.

```python
# WRONG
from zarr.core.common import ByteRequest
from zarr.storage._common import make_store_path
from zarr.storage import StorePath
from zarr.core.buffer.cpu import Buffer
from zarr.core.common import BytesLike  # does not exist
```

```python
# CORRECT
from zarr.abc.store import ByteRequest, RangeByteRequest, OffsetByteRequest, SuffixByteRequest
from zarr.core.buffer import Buffer, default_buffer_prototype
# StorePath and make_store_path are internal — use zarr.open_group(store) instead
```

---

## 8. `zarr.open_array(mode='a')` silently ignores shape/dtype arguments

**Frequency:** 1 occurrence | **Signal:** error, self_correction

```python
# WRONG — mode='a' opens the existing array as-is, ignoring shape
arr = zarr.open_array(store, path="data", mode="a", shape=(new_shape,))
```

```python
# CORRECT — mode='w' to overwrite with new shape
arr = zarr.open_array(store, path="data", mode="w", shape=(new_shape,), dtype="f4")
```

---

## 9. `MemoryStore.list_prefix()` uses raw string matching, not directory semantics

**Frequency:** 2 occurrences | **Signal:** error, self_correction

```python
# SURPRISING BEHAVIOR
# MemoryStore: list_prefix("0") returns "0/zarr.json" AND "0_c/zarr.json"
# LocalStore/IcechunkStore: list_prefix("0") returns only "0/..." (directory semantics)
```

```python
# CORRECT — filter results when using MemoryStore as a test reference
expected = [k async for k in model_store.list_prefix(path)]
if path:
    expected = [k for k in expected if k.startswith(path + "/")]
```

---

## 10. Version-gating zarr features by version string breaks on dev builds

**Frequency:** 1 occurrence | **Signal:** error, user_correction

```python
# WRONG — dev builds report pre-release versions (e.g. 3.1.7.dev38 < 3.2)
from packaging.version import Version
if Version(zarr.__version__) >= Version("3.2"):
    zarr.config.set({"array.rectilinear_chunks": True})
```

```python
# CORRECT — gate on feature presence
try:
    zarr.config.set({"array.rectilinear_chunks": True})
except Exception:
    pass  # feature not available in this build
# OR: check hasattr on the relevant metadata class
```

---

## 11. `arr.chunks` type changed in zarr v3

**Frequency:** 1 occurrence | **Signal:** user_correction

```python
# WRONG — assumes v2 behavior where arr.chunks is a tuple of ints
for coord, chunk_size in zip(coords, arr.chunks):
    ...
```

```python
# CORRECT — use metadata API
chunk_grid = arr.metadata.chunk_grid
# chunk_grid may be RegularChunkGrid or RectilinearChunkGridMetadata
```

---

## 12. `IcechunkStore` is not directly iterable

**Frequency:** 1 occurrence | **Signal:** error

```python
# WRONG
print(list(store))
```

```python
# CORRECT — traverse via zarr
root = zarr.open_group(store, mode="r")
for name, obj in root.members():
    print(name, obj)
```

---

## 13. `zarr.group()` vs `zarr.open_group()` confusion

**Frequency:** 1 occurrence | **Signal:** self_correction

Claude uses `zarr.group(store=store, overwrite=True)` interchangeably with `zarr.open_group()`. In zarr v3, `zarr.group()` is a v2-era convenience with subtly different semantics.

```python
# WRONG — v2-era convenience function
root = zarr.group(store=store, overwrite=True)
```

```python
# CORRECT — explicit mode-based API
root = zarr.open_group(store=store, mode="w")   # overwrite
root = zarr.open_group(store=store, mode="a")   # append
```

---

## Meta-patterns

### Root cause: zarr v2 muscle memory
Patterns 4, 8, 11, 13 stem from Claude applying zarr v2 conventions to v3. In v2, `create_array` accepted both `shape` and `data`; `arr.chunks` was a plain tuple; `mode='a'` behaved differently.

### Root cause: sync/async confusion
Patterns 2, 6 stem from zarr v3's async-first store API. Claude forgets that store methods are coroutines and `list_prefix` returns an async generator, not a list.

### Root cause: icechunk API churn (v1 to v2)
Patterns 1, 3, 5 reflect the icechunk v1-to-v2 migration. The store creation API changed completely, consolidated metadata doesn't apply, and empty repos need special handling.

### Root cause: reaching for internal APIs
Pattern 7 is the highest-frequency anti-pattern. When Claude hits an error, it dives into zarr internals (`zarr.core.buffer.cpu`, `zarr.storage._common`) instead of staying at the public API surface (`zarr.open_group`, `zarr.abc.store`).
