# Common Claude API Mistakes: Icechunk & Zarr-Python

Compiled from 42 Claude Code sessions (11,417 turns) spanning March-April 2026.
3,319 error-containing turns extracted, analyzed by 9 parallel subagents.

---

## Meta-pattern: Premature Over-Specification

The single most pervasive anti-pattern across all sessions. When Claude encounters
an error or needs to debug, it immediately drops to internal/private APIs instead
of using the simple public defaults. This cascades into further errors because the
internal paths are unstable, async-only, and require knowledge of types like
`Buffer`, `BufferPrototype`, and `StorePath` that users should never touch.

### What it looks like

| Over-specified (WRONG)                                              | Simple alternative (CORRECT)                     |
|---------------------------------------------------------------------|--------------------------------------------------|
| `from zarr.core.buffer.cpu import Buffer; Buffer.from_bytes(b'...')`| `zarr.group(store)` or `zarr.create_array(store)` |
| `from zarr.core.buffer import default_buffer_prototype`             | Don't call `store.get()` directly                |
| `from zarr.core.buffer import PROTOTYPE`                            | Use zarr array/group API                         |
| `zarr.core.buffer.numpy_buffer.NumpyBuffer.create_zero_length()`   | `arr[:]` to read data                            |
| `from zarr.core.sync import sync`                                   | Use the sync zarr API directly                   |
| `from zarr.storage._common import StorePath`                        | `zarr.open_group(store)`                         |
| `AsyncGroup(GroupMetadata(), store_path=StorePath(...))`            | `zarr.open_group(store)`                         |
| `zarr.api.asynchronous.open_group(store)`                           | `zarr.open_group(store)`                         |
| `from icechunk._icechunk_python import PyIcechunkStore`             | `import icechunk`                                |
| `from icechunk.repository import Repository`                        | `import icechunk`                                |
| `asyncio.run(store.list_prefix(""))`                                | `zarr.open_group(store).members()`               |
| `asyncio.run(store.delete("data/c/0"))`                            | `arr[idx] = fill_value` or just don't write it   |
| `store.set(key, value)` / `store.get(key, prototype=...)`          | Use zarr group/array API                         |

**Frequency:** 145 hits across 10+ sessions. The `zarr.core.buffer` imports
alone appear in 7 sessions. `asyncio.run()` wrappers for store calls appear
pervasively in debugging scripts.

**Root cause:** When Claude needs to inspect or debug store contents (what keys
exist, what bytes are stored), it reaches into the low-level async store API.
This forces it to know about `BufferPrototype`, `StorePath`, `asyncio.run()`
wrappers, and internal submodule paths. The zarr array/group API almost always
provides what's needed without any of that.

**Rule:** Stay at the zarr group/array level. If you think you need to import
from `zarr.core.*`, `zarr.abc.*`, `zarr.storage._*`, or `icechunk._*`, you're
almost certainly doing it wrong.

---

## Icechunk API Mistakes

### IC-1. IC1 vs IC2 lifecycle confusion

**Frequency:** 3+ occurrences in 1 session, but the fundamental mistake
**Severity:** High -- the entire object model changed between versions

```python
# WRONG (IC1 / old API -- does not exist in IC2)
store = icechunk.IcechunkStore.create(storage=config, mode="w")
store = icechunk.IcechunkStore.open_or_create(storage=config, mode="w")
config = icechunk.StorageConfig.filesystem("/tmp/test")
store.commit("message")  # commit was on the store in IC1

# CORRECT (IC2 / current API)
storage = icechunk.local_filesystem_storage("/tmp/test")
repo = icechunk.Repository.create(storage)
session = repo.writable_session("main")
store = session.store
# ... use store with zarr ...
session.commit("message")  # commit is on the session, not the store
```

The IC2 lifecycle is: **Storage -> Repository -> Session -> Store**.
The store is always obtained from `session.store`, never constructed directly.
Commits happen on the session, not the store.

---

### IC-2. Using `writable_session()` for moves (needs `rearrange_session()`)

**Frequency:** 4+ occurrences across 4 sessions
**Severity:** High -- two mistakes compounded

```python
# WRONG (two errors: wrong session type AND wrong method name)
session = repo.writable_session("main")
session.move_node("/a", "/b")    # AttributeError: no attribute 'move_node'

# WRONG (right method name, wrong session type)
session = repo.writable_session("main")
session.move("/a", "/b")         # IcechunkError: need a rearrange session

# CORRECT
session = repo.rearrange_session("main")
session.move("/a", "/b")
session.commit("moved a to b")
```

`move_node()` does not exist -- the method is `move()`.
Rearrange sessions can ONLY do moves. Writable sessions can ONLY do data writes.
You cannot mix operations across session types.

---

### IC-3. Methods called on wrong object (Session vs Repository)

**Frequency:** 5+ occurrences across 4 sessions
**Severity:** High -- fundamental confusion about object responsibilities

```python
# WRONG -- these methods do not exist on Session
session.rewrite_manifests(...)      # lives on Repository
session.set_metadata({...})         # lives on Repository (v2 only)
session.get_node("/path")           # does not exist at all
session.delete_array("/data")       # does not exist on Python Session
session.delete_group("/data")       # does not exist on Python Session

# CORRECT
repo.rewrite_manifests(...)
repo.set_metadata({...})            # v2 repos only
# For deleting: use zarr API through the store, not session methods
```

---

### IC-4. `session.commit(amend=True)` -- amend is a separate method

**Frequency:** 1 occurrence
**Severity:** Medium

```python
# WRONG
session.commit("message", amend=True)   # TypeError: unexpected keyword argument

# CORRECT
session.amend("message")               # separate method, not a kwarg
```

---

### IC-5. `SnapshotInfo.flushed_at` does not exist

**Frequency:** 1 occurrence
**Severity:** Medium

```python
# WRONG
older_than = snap_info.flushed_at + timedelta(microseconds=1)
# AttributeError: 'builtins.SnapshotInfo' object has no attribute 'flushed_at'

# CORRECT
older_than = snap_info.written_at + timedelta(microseconds=1)
```

Claude invented the attribute name. The actual field is `written_at`.

---

### IC-6. `StorageConfig` vs `Storage` type confusion

**Frequency:** 2 occurrences
**Severity:** Medium

```python
# WRONG -- StorageConfig/ObjectStoreConfig is not a Storage
config = icechunk.StorageConfig.filesystem("/tmp/test")
repo = icechunk.Repository.create(config)
# TypeError: 'PyObjectStoreConfig_LocalFileSystem' cannot be cast as 'Storage'

# CORRECT -- factory functions return Storage objects
storage = icechunk.local_filesystem_storage("/tmp/test")
repo = icechunk.Repository.create(storage)
```

---

### IC-7. Wrong S3 region = hard failure for anonymous access

**Frequency:** 1 occurrence
**Severity:** Medium

Claude assumed wrong S3 region would cause a slow redirect. For anonymous
access, it's a hard failure (`PermanentRedirect` / dispatch failure).

```python
# WRONG mental model: "wrong region = extra round trip, sdk follows 301"
# REALITY with anonymous=True: complete failure, no redirect following

# CORRECT
storage = icechunk.s3_storage(
    bucket="my-bucket",
    region="us-east-1",     # must be correct for anonymous access
    anonymous=True,
)
```

---

### IC-8. `ic.Buffer` does not exist in IC2

**Frequency:** 1 occurrence
**Severity:** Low

```python
# WRONG
ic.Buffer.from_bytes(b'{"zarr_format": 3}')  # AttributeError

# CORRECT -- don't write raw metadata. Use zarr:
root = zarr.group(store=session.store)
```

---

### IC-9. Trying to commit on a readonly session

**Frequency:** 1 occurrence (latent)
**Severity:** Low

A readonly session has `branch_name = None`. Calling `session.commit()` on it
raises `CommitNotAllowed`. After `checkout_tag` or `readonly_session(snapshot_id=...)`,
you must create a new writable session to make changes.

---

### IC-10. `Snapshot.parent_id()` deprecated in v2 -- always returns `None`

**Frequency:** 1 occurrence
**Severity:** Medium for library internals

In spec_version=2, `Snapshot.parent_id()` always returns `None`. Parent tracking
moved to the transaction log. Code checking `snapshot.parent_id().is_none()` to
detect root snapshots will treat ALL v2 snapshots as roots.

---

## Zarr v3 API Mistakes

### Z-1. `store.list_prefix()` is an async generator, not an awaitable

**Frequency:** 4+ occurrences across 3 sessions
**Severity:** High

```python
# WRONG -- all of these fail
sync(store.list_prefix(""))          # TypeError: can't be used in 'await'
asyncio.run(store.list_prefix(""))   # ValueError: coroutine expected
sorted(store.list_prefix(""))        # TypeError: async_generator not iterable

# Claude also invented this, which does not exist:
store.list_prefix_sync("")           # AttributeError

# CORRECT (if you truly need store-level keys)
async def _keys(store):
    return sorted([k async for k in store.list_prefix("")])
keys = asyncio.run(_keys(store))

# BETTER -- stay at zarr level
root = zarr.open_group(store)
print(list(root.members()))
```

---

### Z-2. `IcechunkStore.set()` is async -- calling without `await` silently drops the write

**Frequency:** 2 occurrences across 2 sessions
**Severity:** High -- completely silent failure

```python
# WRONG -- coroutine created but never awaited
session.store.set("zarr.json", meta)
# RuntimeWarning: coroutine 'IcechunkStore.set' was never awaited
# session.commit() then fails: "no changes made"

# CORRECT -- use zarr API, not raw store
root = zarr.group(store=session.store)
arr = root.create_array("data", shape=(10,), dtype="f8")
arr[:] = np.arange(10)
```

---

### Z-3. `IcechunkStore.set()` requires `Buffer`, not `bytes`

**Frequency:** 1-2 occurrences
**Severity:** Medium

```python
# WRONG
store.set("zarr.json", b'{"zarr_format": 3}')
# TypeError: `value` must be a Buffer instance. Got bytes.

# CORRECT (but you probably shouldn't be doing this at all)
from zarr.core.buffer.cpu import Buffer
await store.set("zarr.json", Buffer.from_bytes(b'{"zarr_format": 3}'))

# BETTER -- use zarr API
zarr.group(store=session.store)
```

---

### Z-4. `group.create_array()` does not accept `data=` with explicit `shape`/`dtype`

**Frequency:** 3 occurrences across 3 sessions
**Severity:** Medium

```python
# WRONG (zarr v2 pattern)
group.create_array("arr", shape=(3,), dtype="i4", data=np.array([1, 2, 3]))

# CORRECT
arr = group.create_array("arr", shape=(3,), dtype="i4")
arr[:] = np.array([1, 2, 3])

# OR infer shape/dtype from data:
arr = group.create_array("arr", data=np.array([1, 2, 3], dtype="i4"))
```

Cannot mix explicit `shape`/`dtype` with `data=`.

---

### Z-5. `create_array()` requires `dtype` in zarr v3

**Frequency:** 1-2 occurrences
**Severity:** Low

```python
# WRONG
root.create_array("arr", shape=(1,))              # missing dtype

# CORRECT
root.create_array("arr", shape=(1,), dtype="i4")
```

---

### Z-6. `IcechunkStore` is not iterable

**Frequency:** 1 occurrence
**Severity:** Low

```python
# WRONG
list(store)   # TypeError: 'IcechunkStore' object is not iterable

# CORRECT
root = zarr.open_group(store)
print(root.tree())
```

---

### Z-7. `zarr.Array` has no `.flat` attribute

**Frequency:** 1 occurrence
**Severity:** Low

```python
# WRONG (numpy habit)
node.flat[0]

# CORRECT
node[0]
```

---

## Summary: Top mistakes by impact

| Rank | Pattern | Occurrences | Category |
|------|---------|-------------|----------|
| 1 | Over-specification: dropping to internal APIs | 145 hits | Anti-pattern |
| 2 | Session vs Repository method confusion | 5+ across 4 sessions | Icechunk |
| 3 | `writable_session` for moves (need `rearrange_session`) | 4+ across 4 sessions | Icechunk |
| 4 | `list_prefix()` treated as awaitable | 4+ across 3 sessions | Zarr async |
| 5 | IC1 vs IC2 lifecycle (`IcechunkStore.create` vs `Repository.create`) | 3+ in 1 session | Icechunk |
| 6 | `create_array(data=...)` with explicit shape/dtype | 3 across 3 sessions | Zarr v2->v3 |
| 7 | `store.set()` without await (silent failure) | 2 across 2 sessions | Zarr async |
| 8 | `StorageConfig` vs `Storage` types | 2 occurrences | Icechunk |
| 9 | `commit(amend=True)` instead of `session.amend()` | 1 occurrence | Icechunk |
| 10 | `SnapshotInfo.flushed_at` (should be `written_at`) | 1 occurrence | Icechunk |
