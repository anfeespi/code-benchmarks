package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	"sort"
)

var errType = reflect.TypeOf((*error)(nil)).Elem()

func dec(t reflect.Type, x any) reflect.Value {
	out := reflect.New(t).Elem()
	switch t.Kind() {
	case reflect.Int, reflect.Int64:
		n, err := x.(json.Number).Int64()
		if err != nil {
			panic(err)
		}
		out.SetInt(n)
	case reflect.Float64:
		f, err := x.(json.Number).Float64()
		if err != nil {
			panic(err)
		}
		out.SetFloat(f)
	case reflect.Bool:
		out.SetBool(x.(bool))
	case reflect.String:
		out.SetString(x.(string))
	case reflect.Ptr:
		if x != nil {
			p := reflect.New(t.Elem())
			p.Elem().Set(dec(t.Elem(), x))
			out.Set(p)
		}
	case reflect.Slice:
		a := x.([]any)
		s := reflect.MakeSlice(t, len(a), len(a))
		for i, e := range a {
			s.Index(i).Set(dec(t.Elem(), e))
		}
		out.Set(s)
	case reflect.Struct:
		a := x.([]any)
		for i := 0; i < t.NumField(); i++ {
			out.Field(i).Set(dec(t.Field(i).Type, a[i]))
		}
	case reflect.Map:
		m := reflect.MakeMap(t)
		obj := x.(map[string]any)
		if pairs, ok := obj["__pairs__"]; ok && t.Key().Kind() != reflect.String {
			for _, p := range pairs.([]any) {
				kv := p.([]any)
				m.SetMapIndex(dec(t.Key(), kv[0]), dec(t.Elem(), kv[1]))
			}
		} else {
			for k, v := range obj {
				m.SetMapIndex(reflect.ValueOf(k), dec(t.Elem(), v))
			}
		}
		out.Set(m)
	default:
		panic("unsupported type " + t.String())
	}
	return out
}

func enc(v reflect.Value) any {
	switch v.Kind() {
	case reflect.Ptr:
		if v.IsNil() {
			return nil
		}
		return enc(v.Elem())
	case reflect.Slice:
		out := make([]any, v.Len())
		for i := range out {
			out[i] = enc(v.Index(i))
		}
		return out
	case reflect.Struct:
		out := make([]any, v.NumField())
		for i := range out {
			out[i] = enc(v.Field(i))
		}
		return out
	case reflect.Map:
		if v.Type().Key().Kind() == reflect.String {
			out := map[string]any{}
			for _, k := range v.MapKeys() {
				out[k.String()] = enc(v.MapIndex(k))
			}
			return out
		}
		keys := v.MapKeys()
		sort.Slice(keys, func(i, j int) bool { return keys[i].Int() < keys[j].Int() })
		pairs := make([]any, len(keys))
		for i, k := range keys {
			pairs[i] = []any{enc(k), enc(v.MapIndex(k))}
		}
		return map[string]any{"__pairs__": pairs}
	default:
		return v.Interface()
	}
}

func callOnce(fn reflect.Value, rawArgs []any) (res map[string]any) {
	defer func() {
		if r := recover(); r != nil {
			res = map[string]any{"error": true, "panic": fmt.Sprint(r)}
		}
	}()
	ft := fn.Type()
	in := make([]reflect.Value, ft.NumIn())
	for i := range in {
		in[i] = dec(ft.In(i), rawArgs[i])
	}
	outs := fn.Call(in)
	if n := len(outs); n > 0 && ft.Out(n-1).Implements(errType) {
		if !outs[n-1].IsNil() {
			return map[string]any{"error": true}
		}
		outs = outs[:n-1]
	}
	if len(outs) == 1 {
		return map[string]any{"value": enc(outs[0])}
	}
	vals := make([]any, len(outs))
	for i, o := range outs {
		vals[i] = enc(o)
	}
	return map[string]any{"value": vals}
}

func main() {
	raw, err := os.ReadFile(os.Args[1])
	if err != nil {
		panic(err)
	}
	var spec struct {
		Calls []struct {
			Args []any `json:"args"`
		} `json:"calls"`
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	if err := d.Decode(&spec); err != nil {
		panic(err)
	}
	fn := reflect.ValueOf(entryPoint)
	results := make([]any, len(spec.Calls))
	for i, c := range spec.Calls {
		results[i] = callOnce(fn, c.Args)
	}
	out, err := json.Marshal(map[string]any{"results": results})
	if err != nil {
		panic(err)
	}
	os.Stdout.Write(out)
}
