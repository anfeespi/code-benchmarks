import { readFileSync } from "node:fs";
import * as sol from "./solution.ts";

type T = string | any[];

function dec(t: T, x: any): any {
  if (x === null || typeof t === "string") return x;
  const k = t[0];
  if (k === "optional") return dec(t[1], x);
  if (k === "list") return x.map((e: any) => dec(t[1], e));
  if (k === "tuple") return x.map((e: any, i: number) => dec(t[i + 1], e));
  if (k === "map") {
    if (t[1] === "str") {
      const out: Record<string, any> = {};
      for (const key of Object.keys(x)) out[key] = dec(t[2], x[key]);
      return out;
    }
    const m = new Map<any, any>();
    for (const [a, b] of x.__pairs__) m.set(dec(t[1], a), dec(t[2], b));
    return m;
  }
  return x;
}

function enc(v: any): any {
  if (v === undefined) return null;
  if (Array.isArray(v)) return v.map(enc);
  if (v instanceof Map) {
    const pairs = [...v.entries()].map(([a, b]) => [enc(a), enc(b)]);
    if (pairs.every(([a]) => typeof a === "string")) return Object.fromEntries(pairs);
    return { __pairs__: pairs };
  }
  if (v !== null && typeof v === "object") {
    const out: Record<string, any> = {};
    for (const key of Object.keys(v)) out[key] = enc(v[key]);
    return out;
  }
  if (typeof v === "bigint") return Number(v);
  return v;
}

const spec = JSON.parse(readFileSync(process.argv[2], "utf8"));
const fn = (sol as any)[spec.entry_name];
const results: any[] = [];
for (const call of spec.calls) {
  const args = call.args.map((a: any, i: number) => dec(spec.signature.args[i], a));
  try {
    results.push({ value: enc(fn(...args)) });
  } catch {
    results.push({ error: true });
  }
}
process.stdout.write(JSON.stringify({ results }));
