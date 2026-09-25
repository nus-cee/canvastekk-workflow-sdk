# WASM worker pattern for heavy TypeScript nodes (web-ifc, fragments, three)

**DA-3010** · Applies to every TypeScript node that loads WebAssembly (web-ifc)
or accumulates large typed-array geometry (fragments/three).

## Why

Two runtime facts make memory behave differently in Node than in the Python SDK:

1. **V8 returns JS heap pages to the OS after major GCs** — plain objects need no
   `malloc_trim`-style remedy.
2. **WASM linear memory never shrinks.** `WebAssembly.Memory.grow()` is
   one-way: once the Emscripten heap (web-ifc) has grown to fit a big model,
   that memory stays reserved **for the life of the process**. No GC, no trim
   call can return it.

On Lambda, sandboxes are warm and reused across invocations — so one big model
permanently inflates every subsequent invocation's footprint in that sandbox
(the Python-side equivalent is documented in DA-3009; WASM is strictly worse
because nothing can reclaim it).

## Pattern: one Worker per invocation, terminated in `finally`

Run the WASM work inside a `worker_threads.Worker` and terminate it after the
response is built — terminating the thread frees its entire WASM heap.

```ts
import { Worker } from "node:worker_threads";
import path from "node:path";

// worker.js — the WASM-touching work lives here, isolated:
//   const webifc = new WebIFC.IfcAPI();
//   parentPort!.on("message", async ({ inputs, downloadsDir }) => {
//     const result = runHeavyConversion(inputs, downloadsDir);
//     parentPort!.postMessage({ ok: true, result });
//   });

export function runInWorker<T>(payload: unknown, timeoutMs: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const worker = new Worker(path.join(__dirname, "worker.js"));
    const timer = setTimeout(() => {
      worker.terminate(); // frees the worker's WASM heap even on timeout
      reject(new Error("worker timed out"));
    }, timeoutMs);
    worker.on("message", (msg) => {
      clearTimeout(timer);
      worker.terminate();
      if (msg.ok) resolve(msg.result as T);
      else reject(new Error(String(msg.error)));
    });
    worker.on("error", (err) => {
      clearTimeout(timer);
      worker.terminate();
      reject(err);
    });
    worker.postMessage(payload);
  });
}
```

Call it from `execute()` — the SDK's error handling and response shape are
unchanged; only the WASM lifetime is scoped to one invocation.

## Pitfalls

- **Worker startup is not free** (~50–100 ms + module loads). Worth it only for
  WASM/near-cap workloads; do not wrap trivial nodes.
- **Do not share WASM instances across threads** — each Worker compiles its own
  module. Pre-compile the module once in the main thread and pass it via
  `worker.postMessage({ moduleWebAssembly })` if startup cost matters
  (compiled modules are transferable and cheap to instantiate per worker).
- **Large inputs/outputs** should move as transferable `ArrayBuffer`s
  (`postMessage(buf, [buf])`) to avoid structured-clone copies.
- **`worker.terminate()` in every exit path** — success, error, and timeout —
  or the heap leak this pattern exists to fix comes back.
- The Python SDK's `malloc_trim` fix (DA-3009) does **not** apply here: WASM
  memory is not on the glibc heap.

## When NOT to use it

Pure-JS nodes (validation, JSON transforms): V8 already returns their heap;
a Worker adds cost without benefit. Reserve the pattern for nodes that call
web-ifc / Emscripten-bound libraries or accumulate model-scale typed arrays.
