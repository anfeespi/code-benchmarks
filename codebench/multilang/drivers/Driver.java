import java.lang.reflect.Constructor;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.RecordComponent;
import java.lang.reflect.Type;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/** Reads one case file, calls Solution.<entry> once per recorded call, prints the results as JSON. */
public final class Driver {
    private final String t;
    private int p;

    private Driver(String text) { t = text; }

    private void ws() { while (p < t.length() && Character.isWhitespace(t.charAt(p))) p++; }

    private String str() {
        StringBuilder out = new StringBuilder();
        p++;
        while (t.charAt(p) != '"') {
            char c = t.charAt(p++);
            if (c != '\\') { out.append(c); continue; }
            char e = t.charAt(p++);
            switch (e) {
                case 'n': out.append('\n'); break;
                case 't': out.append('\t'); break;
                case 'r': out.append('\r'); break;
                case 'b': out.append('\b'); break;
                case 'f': out.append('\f'); break;
                case 'u': out.append((char) Integer.parseInt(t.substring(p, p + 4), 16)); p += 4; break;
                default: out.append(e);
            }
        }
        p++;
        return out.toString();
    }

    private Object value() {
        ws();
        char c = t.charAt(p);
        if (c == '{') {
            Map<String, Object> m = new LinkedHashMap<>();
            p++; ws();
            if (t.charAt(p) == '}') { p++; return m; }
            while (true) {
                ws();
                String k = str();
                ws(); p++;
                m.put(k, value());
                ws();
                if (t.charAt(p++) == '}') return m;
            }
        }
        if (c == '[') {
            List<Object> a = new ArrayList<>();
            p++; ws();
            if (t.charAt(p) == ']') { p++; return a; }
            while (true) {
                a.add(value());
                ws();
                if (t.charAt(p++) == ']') return a;
            }
        }
        if (c == '"') return str();
        if (c == 't') { p += 4; return Boolean.TRUE; }
        if (c == 'f') { p += 5; return Boolean.FALSE; }
        if (c == 'n') { p += 4; return null; }
        int q = p;
        boolean fl = false;
        while (q < t.length() && "+-.eE0123456789".indexOf(t.charAt(q)) >= 0) {
            char d = t.charAt(q);
            if (d == '.' || d == 'e' || d == 'E') fl = true;
            q++;
        }
        String num = t.substring(p, q);
        p = q;
        return fl ? (Object) Double.valueOf(num) : (Object) Long.valueOf(num);
    }

    @SuppressWarnings("unchecked")
    private static Object dec(Type type, Object x) throws Exception {
        if (x == null) return null;
        if (type instanceof ParameterizedType) {
            ParameterizedType pt = (ParameterizedType) type;
            Class<?> raw = (Class<?>) pt.getRawType();
            Type[] ta = pt.getActualTypeArguments();
            if (List.class.isAssignableFrom(raw)) {
                List<Object> out = new ArrayList<>();
                for (Object e : (List<Object>) x) out.add(dec(ta[0], e));
                return out;
            }
            if (Map.class.isAssignableFrom(raw)) {
                Map<Object, Object> out = new LinkedHashMap<>();
                Map<String, Object> obj = (Map<String, Object>) x;
                if (ta[0] != String.class && obj.containsKey("__pairs__")) {
                    for (Object pair : (List<Object>) obj.get("__pairs__")) {
                        List<Object> kv = (List<Object>) pair;
                        out.put(dec(ta[0], kv.get(0)), dec(ta[1], kv.get(1)));
                    }
                } else {
                    for (Map.Entry<String, Object> e : obj.entrySet()) out.put(e.getKey(), dec(ta[1], e.getValue()));
                }
                return out;
            }
            throw new IllegalStateException("unsupported type " + type);
        }
        Class<?> c = (Class<?>) type;
        if (c == long.class || c == Long.class) return ((Number) x).longValue();
        if (c == int.class || c == Integer.class) return ((Number) x).intValue();
        if (c == double.class || c == Double.class) return ((Number) x).doubleValue();
        if (c == boolean.class || c == Boolean.class || c == String.class) return x;
        if (c.isRecord()) {
            RecordComponent[] rc = c.getRecordComponents();
            List<Object> a = (List<Object>) x;
            Object[] args = new Object[rc.length];
            Class<?>[] types = new Class<?>[rc.length];
            for (int i = 0; i < rc.length; i++) {
                args[i] = dec(rc[i].getGenericType(), a.get(i));
                types[i] = rc[i].getType();
            }
            Constructor<?> k = c.getDeclaredConstructor(types);
            k.setAccessible(true);
            return k.newInstance(args);
        }
        throw new IllegalStateException("unsupported type " + type);
    }

    private static void quote(StringBuilder o, String s) {
        o.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"') o.append("\\\"");
            else if (c == '\\') o.append("\\\\");
            else if (c == '\n') o.append("\\n");
            else if (c == '\t') o.append("\\t");
            else if (c == '\r') o.append("\\r");
            else if (c < 0x20) o.append(String.format("\\u%04x", (int) c));
            else o.append(c);
        }
        o.append('"');
    }

    private static void enc(StringBuilder o, Object v) throws Exception {
        if (v == null) { o.append("null"); return; }
        if (v instanceof String) { quote(o, (String) v); return; }
        if (v instanceof Number || v instanceof Boolean) { o.append(v); return; }
        if (v instanceof List) {
            o.append('[');
            boolean first = true;
            for (Object e : (List<?>) v) { if (!first) o.append(','); first = false; enc(o, e); }
            o.append(']');
            return;
        }
        if (v instanceof Map) {
            Map<?, ?> m = (Map<?, ?>) v;
            boolean strings = true;
            for (Object k : m.keySet()) if (!(k instanceof String)) strings = false;
            boolean first = true;
            if (strings) {
                o.append('{');
                for (Map.Entry<?, ?> e : new TreeMap<Object, Object>(m).entrySet()) {
                    if (!first) o.append(','); first = false;
                    quote(o, (String) e.getKey()); o.append(':'); enc(o, e.getValue());
                }
                o.append('}');
            } else {
                o.append("{\"__pairs__\":[");
                for (Map.Entry<?, ?> e : m.entrySet()) {
                    if (!first) o.append(','); first = false;
                    o.append('['); enc(o, e.getKey()); o.append(','); enc(o, e.getValue()); o.append(']');
                }
                o.append("]}");
            }
            return;
        }
        if (v.getClass().isRecord()) {
            o.append('[');
            boolean first = true;
            for (RecordComponent rc : v.getClass().getRecordComponents()) {
                if (!first) o.append(','); first = false;
                Method acc = rc.getAccessor();
                acc.setAccessible(true);
                enc(o, acc.invoke(v));
            }
            o.append(']');
            return;
        }
        throw new IllegalStateException("cannot encode " + v.getClass());
    }

    @SuppressWarnings("unchecked")
    public static void main(String[] argv) throws Exception {
        String text = new String(Files.readAllBytes(Paths.get(argv[0])), StandardCharsets.UTF_8);
        Map<String, Object> spec = (Map<String, Object>) new Driver(text).value();
        String name = (String) spec.get("entry_name");
        Method fn = null;
        for (Method m : Class.forName("Solution").getDeclaredMethods()) if (m.getName().equals(name)) fn = m;
        if (fn == null) throw new IllegalStateException("Solution." + name + " not found");
        fn.setAccessible(true);
        Type[] types = fn.getGenericParameterTypes();
        StringBuilder out = new StringBuilder("{\"results\":[");
        boolean first = true;
        for (Object call : (List<Object>) spec.get("calls")) {
            if (!first) out.append(',');
            first = false;
            List<Object> raw = (List<Object>) ((Map<String, Object>) call).get("args");
            Object[] args = new Object[types.length];
            for (int i = 0; i < types.length; i++) args[i] = dec(types[i], raw.get(i));
            try {
                StringBuilder v = new StringBuilder();
                enc(v, fn.invoke(null, args));
                out.append("{\"value\":").append(v).append('}');
            } catch (InvocationTargetException e) {
                if (e.getCause() instanceof StackOverflowError || e.getCause() instanceof OutOfMemoryError) throw e;
                out.append("{\"error\":true}");
            }
        }
        out.append("]}");
        System.out.write(out.toString().getBytes(StandardCharsets.UTF_8));
        System.out.flush();
    }
}
