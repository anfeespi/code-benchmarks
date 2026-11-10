// Reads one case file, calls the candidate once per recorded call, prints the results as JSON.
// SIGNATURE_INCLUDE declares the candidate's prototype and CALL_ENTRY; both are generated.
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

struct J {
    enum Kind { Null, Bool, Int, Float, Str, Arr, Obj } kind = Null;
    bool b = false;
    long long i = 0;
    double d = 0;
    std::string s;
    std::vector<J> a;
    std::vector<std::pair<std::string, J>> o;
    const J* get(const std::string& key) const {
        for (auto& kv : o) if (kv.first == key) return &kv.second;
        return nullptr;
    }
};

struct Parser {
    const std::string& t;
    size_t p = 0;
    explicit Parser(const std::string& text) : t(text) {}
    void ws() { while (p < t.size() && (t[p] == ' ' || t[p] == '\n' || t[p] == '\t' || t[p] == '\r')) p++; }
    static void utf8(std::string& out, unsigned cp) {
        if (cp < 0x80) out += char(cp);
        else if (cp < 0x800) { out += char(0xC0 | (cp >> 6)); out += char(0x80 | (cp & 0x3F)); }
        else if (cp < 0x10000) { out += char(0xE0 | (cp >> 12)); out += char(0x80 | ((cp >> 6) & 0x3F)); out += char(0x80 | (cp & 0x3F)); }
        else { out += char(0xF0 | (cp >> 18)); out += char(0x80 | ((cp >> 12) & 0x3F)); out += char(0x80 | ((cp >> 6) & 0x3F)); out += char(0x80 | (cp & 0x3F)); }
    }
    unsigned hex4() { unsigned v = std::stoul(t.substr(p, 4), nullptr, 16); p += 4; return v; }
    std::string str() {
        std::string out;
        p++;
        while (t[p] != '"') {
            if (t[p] != '\\') { out += t[p++]; continue; }
            char c = t[p + 1];
            p += 2;
            switch (c) {
                case 'n': out += '\n'; break;
                case 't': out += '\t'; break;
                case 'r': out += '\r'; break;
                case 'b': out += '\b'; break;
                case 'f': out += '\f'; break;
                case 'u': {
                    unsigned cp = hex4();
                    if (cp >= 0xD800 && cp < 0xDC00 && t[p] == '\\' && t[p + 1] == 'u') {
                        p += 2;
                        cp = 0x10000 + ((cp - 0xD800) << 10) + (hex4() - 0xDC00);
                    }
                    utf8(out, cp);
                    break;
                }
                default: out += c;
            }
        }
        p++;
        return out;
    }
    J value() {
        ws();
        J j;
        char c = t[p];
        if (c == '{') {
            j.kind = J::Obj;
            p++; ws();
            if (t[p] == '}') { p++; return j; }
            while (true) {
                ws();
                std::string k = str();
                ws(); p++;
                j.o.emplace_back(std::move(k), value());
                ws();
                if (t[p++] == '}') break;
            }
        } else if (c == '[') {
            j.kind = J::Arr;
            p++; ws();
            if (t[p] == ']') { p++; return j; }
            while (true) {
                j.a.push_back(value());
                ws();
                if (t[p++] == ']') break;
            }
        } else if (c == '"') {
            j.kind = J::Str;
            j.s = str();
        } else if (c == 't') { j.kind = J::Bool; j.b = true; p += 4; }
        else if (c == 'f') { j.kind = J::Bool; j.b = false; p += 5; }
        else if (c == 'n') { p += 4; }
        else {
            size_t q = p;
            bool fl = false;
            while (q < t.size() && (std::isdigit((unsigned char)t[q]) || t[q] == '-' || t[q] == '+' || t[q] == '.' || t[q] == 'e' || t[q] == 'E')) {
                if (t[q] == '.' || t[q] == 'e' || t[q] == 'E') fl = true;
                q++;
            }
            std::string num = t.substr(p, q - p);
            p = q;
            if (fl) { j.kind = J::Float; j.d = std::stod(num); }
            else { j.kind = J::Int; j.i = std::stoll(num); j.d = (double)j.i; }
        }
        return j;
    }
};

inline void quote(std::string& out, const std::string& s) {
    out += '"';
    for (unsigned char c : s) {
        if (c == '"') out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\n') out += "\\n";
        else if (c == '\t') out += "\\t";
        else if (c == '\r') out += "\\r";
        else if (c < 0x20) { char buf[8]; std::snprintf(buf, sizeof buf, "\\u%04x", c); out += buf; }
        else out += char(c);
    }
    out += '"';
}

template <class T> struct Conv;
template <> struct Conv<long long> {
    static long long from(const J& j) { return j.i; }
    static void to(std::string& o, long long v) { o += std::to_string(v); }
};
template <> struct Conv<int> {
    static int from(const J& j) { return (int)j.i; }
    static void to(std::string& o, int v) { o += std::to_string(v); }
};
template <> struct Conv<double> {
    static double from(const J& j) { return j.d; }
    static void to(std::string& o, double v) {
        char buf[40];
        std::snprintf(buf, sizeof buf, "%.17g", v);
        o += buf;
    }
};
template <> struct Conv<bool> {
    static bool from(const J& j) { return j.b; }
    static void to(std::string& o, bool v) { o += v ? "true" : "false"; }
};
template <> struct Conv<std::string> {
    static std::string from(const J& j) { return j.s; }
    static void to(std::string& o, const std::string& v) { quote(o, v); }
};
template <class T> struct Conv<std::vector<T>> {
    static std::vector<T> from(const J& j) {
        std::vector<T> out;
        out.reserve(j.a.size());
        for (auto& e : j.a) out.push_back(Conv<T>::from(e));
        return out;
    }
    static void to(std::string& o, const std::vector<T>& v) {
        o += '[';
        for (size_t k = 0; k < v.size(); k++) { if (k) o += ','; T e = v[k]; Conv<T>::to(o, e); }
        o += ']';
    }
};
template <class T> struct Conv<std::optional<T>> {
    static std::optional<T> from(const J& j) {
        if (j.kind == J::Null) return std::nullopt;
        return Conv<T>::from(j);
    }
    static void to(std::string& o, const std::optional<T>& v) {
        if (!v) o += "null"; else Conv<T>::to(o, *v);
    }
};
template <class... Ts> struct Conv<std::tuple<Ts...>> {
    template <size_t... I> static std::tuple<Ts...> fromImpl(const J& j, std::index_sequence<I...>) {
        return std::tuple<Ts...>(Conv<Ts>::from(j.a[I])...);
    }
    static std::tuple<Ts...> from(const J& j) { return fromImpl(j, std::index_sequence_for<Ts...>{}); }
    template <size_t... I> static void toImpl(std::string& o, const std::tuple<Ts...>& v, std::index_sequence<I...>) {
        ((o += (I ? "," : ""), Conv<Ts>::to(o, std::get<I>(v))), ...);
    }
    static void to(std::string& o, const std::tuple<Ts...>& v) {
        o += '[';
        toImpl(o, v, std::index_sequence_for<Ts...>{});
        o += ']';
    }
};
template <class A, class B> struct Conv<std::pair<A, B>> {
    static std::pair<A, B> from(const J& j) { return {Conv<A>::from(j.a[0]), Conv<B>::from(j.a[1])}; }
    static void to(std::string& o, const std::pair<A, B>& v) {
        o += '['; Conv<A>::to(o, v.first); o += ','; Conv<B>::to(o, v.second); o += ']';
    }
};
template <class V> struct Conv<std::map<std::string, V>> {
    static std::map<std::string, V> from(const J& j) {
        std::map<std::string, V> out;
        for (auto& kv : j.o) out.emplace(kv.first, Conv<V>::from(kv.second));
        return out;
    }
    static void to(std::string& o, const std::map<std::string, V>& v) {
        o += '{';
        bool first = true;
        for (auto& kv : v) { if (!first) o += ','; first = false; quote(o, kv.first); o += ':'; Conv<V>::to(o, kv.second); }
        o += '}';
    }
};
template <class V> struct Conv<std::map<long long, V>> {
    static std::map<long long, V> from(const J& j) {
        std::map<long long, V> out;
        if (const J* pairs = j.get("__pairs__"))
            for (auto& kv : pairs->a) out.emplace(kv.a[0].i, Conv<V>::from(kv.a[1]));
        return out;
    }
    static void to(std::string& o, const std::map<long long, V>& v) {
        o += "{\"__pairs__\":[";
        bool first = true;
        for (auto& kv : v) { if (!first) o += ','; first = false; o += '['; o += std::to_string(kv.first); o += ','; Conv<V>::to(o, kv.second); o += ']'; }
        o += "]}";
    }
};

#include SIGNATURE_INCLUDE

int main(int argc, char** argv) {
    std::ifstream in(argv[1], std::ios::binary);
    std::stringstream buf;
    buf << in.rdbuf();
    std::string text = buf.str();
    J spec = Parser(text).value();
    std::string out = "{\"results\":[";
    bool first = true;
    for (auto& call : spec.get("calls")->a) {
        if (!first) out += ',';
        first = false;
        const std::vector<J>& args = call.get("args")->a;
        try {
            std::string v;
            CALL_ENTRY(args, v);
            out += "{\"value\":" + v + "}";
        } catch (...) {
            out += "{\"error\":true}";
        }
    }
    out += "]}";
    std::fwrite(out.data(), 1, out.size(), stdout);
    return 0;
}
