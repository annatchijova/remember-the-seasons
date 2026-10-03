// mneme-verify — clean-room implementation of mneme-cf-bundle/v1
// verification, written against spec/cf-bundle-v1.md and the
// conformance corpus. It does not consume the claimed result; it
// recomputes the counterfactual cascade from sealed evidence.
//
// Usage:
//   mneme-verify <bundle|envelope> [trusted-keys.json] [--format json]
package main

import (
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"
	"os"
	"sort"
	"strconv"
	"strings"
)

// ------------------------------------------------------------------
// strict JSON: parse with duplicate-key rejection (RFC 8785 rule
// applied to every layer), preserving number lexemes
// ------------------------------------------------------------------

type jparse struct {
	s string
	i int
}

func (p *jparse) ws() {
	for p.i < len(p.s) && (p.s[p.i] == ' ' || p.s[p.i] == '\t' ||
		p.s[p.i] == '\n' || p.s[p.i] == '\r') {
		p.i++
	}
}

func (p *jparse) value() (interface{}, error) {
	p.ws()
	if p.i >= len(p.s) {
		return nil, fmt.Errorf("unexpected end")
	}
	switch c := p.s[p.i]; {
	case c == '{':
		p.i++
		m := map[string]interface{}{}
		p.ws()
		if p.i < len(p.s) && p.s[p.i] == '}' {
			p.i++
			return m, nil
		}
		for {
			p.ws()
			k, err := p.str()
			if err != nil {
				return nil, err
			}
			if _, dup := m[k]; dup {
				return nil, fmt.Errorf("duplicate JSON key: %q", k)
			}
			p.ws()
			if p.i >= len(p.s) || p.s[p.i] != ':' {
				return nil, fmt.Errorf("expected ':'")
			}
			p.i++
			v, err := p.value()
			if err != nil {
				return nil, err
			}
			m[k] = v
			p.ws()
			if p.i >= len(p.s) {
				return nil, fmt.Errorf("unclosed object")
			}
			if p.s[p.i] == '}' {
				p.i++
				return m, nil
			}
			if p.s[p.i] != ',' {
				return nil, fmt.Errorf("expected ',' or '}'")
			}
			p.i++
		}
	case c == '[':
		p.i++
		var a []interface{}
		p.ws()
		if p.i < len(p.s) && p.s[p.i] == ']' {
			p.i++
			return a, nil
		}
		for {
			v, err := p.value()
			if err != nil {
				return nil, err
			}
			a = append(a, v)
			p.ws()
			if p.i >= len(p.s) {
				return nil, fmt.Errorf("unclosed array")
			}
			if p.s[p.i] == ']' {
				p.i++
				return a, nil
			}
			if p.s[p.i] != ',' {
				return nil, fmt.Errorf("expected ',' or ']'")
			}
			p.i++
		}
	case c == '"':
		return p.str()
	case c == 't' && strings.HasPrefix(p.s[p.i:], "true"):
		p.i += 4
		return true, nil
	case c == 'f' && strings.HasPrefix(p.s[p.i:], "false"):
		p.i += 5
		return false, nil
	case c == 'n' && strings.HasPrefix(p.s[p.i:], "null"):
		p.i += 4
		return nil, nil
	default:
		start := p.i
		for p.i < len(p.s) && strings.IndexByte(
			"-+0123456789.eE", p.s[p.i]) >= 0 {
			p.i++
		}
		if start == p.i {
			return nil, fmt.Errorf("bad value at %d", p.i)
		}
		return json.Number(p.s[start:p.i]), nil
	}
}

func (p *jparse) str() (string, error) {
	if p.i >= len(p.s) || p.s[p.i] != '"' {
		return "", fmt.Errorf("expected string at %d", p.i)
	}
	p.i++
	var b strings.Builder
	for p.i < len(p.s) {
		c := p.s[p.i]
		if c == '"' {
			p.i++
			return b.String(), nil
		}
		if c == '\\' {
			p.i++
			if p.i >= len(p.s) {
				return "", fmt.Errorf("bad escape")
			}
			switch e := p.s[p.i]; e {
			case 'n':
				b.WriteByte('\n')
			case 't':
				b.WriteByte('\t')
			case 'r':
				b.WriteByte('\r')
			case 'b':
				b.WriteByte('\b')
			case 'f':
				b.WriteByte('\f')
			case 'u':
				if p.i+4 >= len(p.s) {
					return "", fmt.Errorf("bad \\u escape")
				}
				n, err := strconv.ParseUint(
					p.s[p.i+1:p.i+5], 16, 32)
				if err != nil {
					return "", err
				}
				p.i += 4
				r := rune(n)
				// surrogate pair
				if n >= 0xD800 && n <= 0xDBFF &&
					p.i+6 < len(p.s) &&
					p.s[p.i+1] == '\\' && p.s[p.i+2] == 'u' {
					lo, err := strconv.ParseUint(
						p.s[p.i+3:p.i+7], 16, 32)
					if err == nil && lo >= 0xDC00 && lo <= 0xDFFF {
						r = 0x10000 + (rune(n)-0xD800)*0x400 +
							(rune(lo) - 0xDC00)
						p.i += 6
					}
				}
				b.WriteRune(r)
			case '"', '\\', '/':
				b.WriteByte(e)
			default:
				return "", fmt.Errorf("bad escape \\%c", e)
			}
			p.i++
			continue
		}
		b.WriteByte(c)
		p.i++
	}
	return "", fmt.Errorf("unclosed string")
}

func strictJSON(s []byte) (interface{}, error) {
	p := &jparse{s: string(s)}
	v, err := p.value()
	if err != nil {
		return nil, err
	}
	p.ws()
	if p.i != len(p.s) {
		return nil, fmt.Errorf("trailing data at %d", p.i)
	}
	return v, nil
}

// ------------------------------------------------------------------
// canonical JSON (mneme-cjson/1.0.0): sorted keys, compact separators,
// literal UTF-8, Python-compatible escaping, no floats
// ------------------------------------------------------------------

func escJSON(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString("\\\"")
		case '\\':
			b.WriteString("\\\\")
		case '\n':
			b.WriteString("\\n")
		case '\r':
			b.WriteString("\\r")
		case '\t':
			b.WriteString("\\t")
		case '\b':
			b.WriteString("\\b")
		case '\f':
			b.WriteString("\\f")
		default:
			if r < 0x20 {
				fmt.Fprintf(&b, "\\u%04x", r)
			} else {
				b.WriteRune(r) // literal UTF-8, like ensure_ascii=False
			}
		}
	}
	b.WriteByte('"')
	return b.String()
}

func canonJSON(v interface{}) (string, error) {
	var b strings.Builder
	err := canonW(&b, v)
	return b.String(), err
}

func canonW(b *strings.Builder, v interface{}) error {
	switch x := v.(type) {
	case nil:
		b.WriteString("null")
	case bool:
		if x {
			b.WriteString("true")
		} else {
			b.WriteString("false")
		}
	case string:
		b.WriteString(escJSON(x))
	case json.Number:
		s := x.String()
		if strings.ContainsAny(s, ".eE") {
			return fmt.Errorf("non-integer JSON number: %s", s)
		}
		b.WriteString(s)
	case []interface{}:
		b.WriteByte('[')
		for i, e := range x {
			if i > 0 {
				b.WriteByte(',')
			}
			if err := canonW(b, e); err != nil {
				return err
			}
		}
		b.WriteByte(']')
	case map[string]interface{}:
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Strings(keys) // UTF-8 byte order == codepoint order
		b.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				b.WriteByte(',')
			}
			b.WriteString(escJSON(k))
			b.WriteByte(':')
			if err := canonW(b, x[k]); err != nil {
				return err
			}
		}
		b.WriteByte('}')
	default:
		return fmt.Errorf("uncanonicalizable %T", v)
	}
	return nil
}

func sha256hex(b []byte) string {
	h := sha256.Sum256(b)
	return hex.EncodeToString(h[:])
}

// ------------------------------------------------------------------
// custody chain (custody_protocol 1.1.0)
// ------------------------------------------------------------------

func genesis(mid string) string {
	return sha256hex(
		append([]byte("MNEME_CUSTODY_GENESIS:"), mid...))
}

func entryHash(mid string, e map[string]interface{},
	prev string) (string, error) {
	payload, err := strictJSON(
		[]byte(e["payload_json"].(string)))
	if err != nil {
		return "", err
	}
	env := map[string]interface{}{
		"memory_id":  mid,
		"seq":        e["seq"],
		"event_type": e["event_type"],
		"actor_id":   e["actor_id"],
		"reason":     e["reason"],
		"created_at": e["created_at"],
		"payload":    payload,
	}
	c, err := canonJSON(env)
	if err != nil {
		return "", err
	}
	return sha256hex(append([]byte(prev), c...)), nil
}

// ------------------------------------------------------------------
// replay (replay_protocol 1.1.0, cf-cascade excision variant)
// ------------------------------------------------------------------

var (
	alpha     = big.NewRat(1, 4)
	promotion = big.NewRat(3, 4)
	one       = big.NewRat(1, 1)
)

func seqOf(e map[string]interface{}) int {
	n, _ := strconv.Atoi(e["seq"].(json.Number).String())
	return n
}

func payloadOf(e map[string]interface{}) map[string]interface{} {
	v, err := strictJSON([]byte(e["payload_json"].(string)))
	if err != nil {
		return map[string]interface{}{}
	}
	m, _ := v.(map[string]interface{})
	return m
}

func replay(chain []map[string]interface{}, dead map[int]bool,
	asOf string, useAsOf bool) (string, string, *big.Rat) {
	status, fstate := "CLEAN", "NEUTRAL"
	conf := big.NewRat(1, 2)
	for _, e := range chain {
		if dead[seqOf(e)] {
			continue
		}
		if useAsOf && e["created_at"].(string) >= asOf {
			continue
		}
		switch et := e["event_type"].(string); et {
		case "QUARANTINED":
			status = "QUARANTINED"
		case "SUPERSEDED_BY":
			status = "SUPERSEDED"
		case "TAINT_FLAGGED":
			if status == "CLEAN" {
				status = "TAINT_FLAGGED"
			}
		case "REHABILITATED":
			status = "CLEAN"
		case "REINFORCED":
			conf = new(big.Rat).Add(conf,
				new(big.Rat).Mul(alpha,
					new(big.Rat).Sub(one, conf)))
		case "STATE_CHANGED":
			p := payloadOf(e)
			to, _ := p["to"].(string)
			if p["from"] == "NEUTRAL" && to == "REINFORCED" {
				if conf.Cmp(promotion) >= 0 {
					fstate = "REINFORCED"
				}
			} else if to != "" {
				fstate = to
			}
		}
	}
	return status, fstate, conf
}

// ------------------------------------------------------------------
// ranking_protocol 1.0.0 — exact rational arithmetic
// ------------------------------------------------------------------

var (
	boostReinforced = big.NewRat(3, 2)
	boostNeutral    = big.NewRat(1, 1)
	decayBase       = big.NewRat(43, 50)
	resonantStep    = big.NewRat(1, 2)
)

type memory struct {
	id     string
	vec    []*big.Rat
	status string
	fstate string
}

func ratFromStr(s string) *big.Rat {
	r, ok := new(big.Rat).SetString(s)
	if !ok {
		return big.NewRat(0, 1)
	}
	return r
}

func dot(a, b []*big.Rat) *big.Rat {
	s := big.NewRat(0, 1)
	for i := range a {
		s.Add(s, new(big.Rat).Mul(a[i], b[i]))
	}
	return s
}

type link struct {
	from, to, ltype string
}

func ratCmpKey(d, nv *big.Rat) (int, *big.Rat) {
	if d.Sign() <= 0 {
		return 0, big.NewRat(0, 1)
	}
	return 1, new(big.Rat).Quo(
		new(big.Rat).Mul(d, d), nv)
}

func independentRecall(mems []memory, links []link,
	q []*big.Rat, topK, hops int) []string {
	servable := map[string]bool{}
	for _, m := range mems {
		if m.status == "CLEAN" {
			servable[m.id] = true
		}
	}
	type cand struct {
		id       string
		nv, d    *big.Rat
		fstate   string
	}
	var cands []cand
	for _, m := range mems {
		if !servable[m.id] || m.fstate == "FORGOTTEN" {
			continue
		}
		nv := dot(m.vec, m.vec)
		if nv.Sign() == 0 {
			continue
		}
		cands = append(cands, cand{m.id, nv,
			dot(q, m.vec), m.fstate})
	}
	if len(cands) == 0 {
		return nil
	}
	best := -1
	var bestK int
	var bestV *big.Rat
	for i, c := range cands {
		cl, v := ratCmpKey(c.d, c.nv)
		if best < 0 || cl > bestK ||
			(cl == bestK && (v.Cmp(bestV) > 0 ||
				(v.Cmp(bestV) == 0 && c.id < cands[best].id))) {
			best, bestK, bestV = i, cl, v
		}
	}
	seed := cands[best].id

	linkMap := map[string][]link{}
	for _, l := range links {
		if servable[l.from] && servable[l.to] {
			linkMap[l.from] = append(linkMap[l.from], l)
		}
	}
	hopOf := map[string]int{}
	inhibited := map[string]bool{}
	boost := map[string]*big.Rat{}
	frontier := map[string]bool{seed: true}
	maxHop := hops
	if maxHop > 10 {
		maxHop = 10
	}
	for depth := 0; depth <= maxHop; depth++ {
		next := map[string]bool{}
		var fs []string
		for m := range frontier {
			fs = append(fs, m)
		}
		sort.Strings(fs)
		for _, m := range fs {
			if inhibited[m] {
				continue
			}
			if _, seen := hopOf[m]; seen {
				continue
			}
			hopOf[m] = depth
			for _, l := range linkMap[m] {
				switch l.ltype {
				case "INHIBITORY":
					inhibited[l.to] = true
				case "RESONANT":
					next[l.to] = true
					if boost[l.to] == nil {
						boost[l.to] = big.NewRat(0, 1)
					}
					boost[l.to].Add(boost[l.to], resonantStep)
				default:
					next[l.to] = true
				}
			}
		}
		frontier = map[string]bool{}
		for m := range next {
			_, visited := hopOf[m]
			if !visited && !inhibited[m] {
				frontier[m] = true
			}
		}
	}

	type scored struct {
		rank *big.Rat
		id   string
	}
	var sc []scored
	for _, c := range cands {
		if inhibited[c.id] && c.id != seed &&
			c.fstate != "REINFORCED" {
			continue
		}
		hop, ok := hopOf[c.id]
		decay := big.NewRat(1, 1)
		if ok && hop >= 0 {
			for i := 0; i < hop; i++ {
				decay.Mul(decay, decayBase)
			}
		}
		sb := boostNeutral
		if c.fstate == "REINFORCED" {
			sb = boostReinforced
		}
		m := new(big.Rat).Mul(sb, decay)
		if boost[c.id] != nil {
			m.Add(m, boost[c.id])
		}
		t := new(big.Rat).Mul(c.d, m)
		rank := big.NewRat(0, 1)
		if t.Sign() > 0 {
			rank = new(big.Rat).Quo(
				new(big.Rat).Mul(t, t), c.nv)
		}
		sc = append(sc, scored{rank, c.id})
	}
	sort.Slice(sc, func(i, j int) bool {
		c := sc[i].rank.Cmp(sc[j].rank)
		if c != 0 {
			return c > 0
		}
		return sc[i].id < sc[j].id
	})
	var out []string
	for i := 0; i < len(sc) && i < topK; i++ {
		out = append(out, sc[i].id)
	}
	return out
}

// ------------------------------------------------------------------
// DSSE + Ed25519 (RFC 8032)
// ------------------------------------------------------------------

const payloadType = "application/vnd.mneme.cf-bundle+json;version=1"

func b64any(s string) ([]byte, error) {
	if b, err := base64.StdEncoding.DecodeString(s); err == nil {
		return b, nil
	}
	return base64.URLEncoding.DecodeString(s)
}

func checkSignature(env map[string]interface{},
	trusted map[string]string) (bool, string) {
	pt, _ := env["payloadType"].(string)
	if pt != payloadType {
		return false, ""
	}
	payload, err := b64any(env["payload"].(string))
	if err != nil {
		return false, ""
	}
	pae := append([]byte("DSSEv1 "),
		[]byte(strconv.Itoa(len(pt)))...)
	pae = append(pae, ' ')
	pae = append(pae, pt...)
	pae = append(pae, ' ')
	pae = append(pae, []byte(strconv.Itoa(len(payload)))...)
	pae = append(pae, ' ')
	pae = append(pae, payload...)
	sigs, _ := env["signatures"].([]interface{})
	for _, s := range sigs {
		sm, _ := s.(map[string]interface{})
		sigB, err := b64any(sm["sig"].(string))
		if err != nil || len(sigB) != 64 {
			continue
		}
		for label, vkeyHex := range trusted {
			vk, err := hex.DecodeString(vkeyHex)
			if err != nil || len(vk) != 32 {
				continue
			}
			if ed25519.Verify(ed25519.PublicKey(vk), pae, sigB) {
				return true, label
			}
		}
	}
	return false, ""
}

// ------------------------------------------------------------------
// the verifier
// ------------------------------------------------------------------

var knownSemantics = map[string]bool{
	"mneme-cf-bundle/v1": true,
	"cf-cascade/v1":      true,
}

func main() {
	// hidden canonicalization driver for cross-language differential
	// testing: --canon reads a strict-JSON value on stdin and prints
	// its mneme-cjson/1.0.0 canonical bytes.
	if len(os.Args) > 1 && os.Args[1] == "--canon" {
		in, _ := os.ReadFile("/dev/stdin")
		v, err := strictJSON(in)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		c, err := canonJSON(v)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Print(c)
		return
	}
	args := []string{}
	for _, a := range os.Args[1:] {
		if !strings.HasPrefix(a, "--") {
			args = append(args, a)
		}
	}
	if len(args) < 1 {
		fmt.Fprintln(os.Stderr, "usage: mneme-verify bundle [keys]")
		os.Exit(2)
	}
	data, err := os.ReadFile(args[0])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	raw, err := strictJSON(data)
	if err != nil {
		fmt.Fprintln(os.Stderr, "parse:", err)
		os.Exit(1)
	}
	env, _ := raw.(map[string]interface{})

	trusted := map[string]string{}
	if len(args) > 1 {
		kd, _ := os.ReadFile(args[1])
		json.Unmarshal(kd, &trusted)
	}

	checks := map[string]bool{}
	order := []string{}
	check := func(name string, ok bool) {
		checks[name] = ok
		order = append(order, name)
	}

	authenticated, signer := false, ""
	var b map[string]interface{}
	if _, has := env["payloadType"]; has {
		authenticated, signer = checkSignature(env, trusted)
		pb, _ := b64any(env["payload"].(string))
		pv, err := strictJSON(pb)
		if err != nil {
			fmt.Fprintln(os.Stderr, "payload parse:", err)
			os.Exit(1)
		}
		b = pv.(map[string]interface{})
		if len(trusted) > 0 {
			check("CF-1", authenticated)
		}
	} else {
		b = env
	}

	seal, _ := b["bundle_sha256"].(string)
	body := map[string]interface{}{}
	for k, v := range b {
		if k != "bundle_sha256" {
			body[k] = v
		}
	}
	cj, _ := canonJSON(body)
	check("CF0", sha256hex([]byte(cj)) == seal)

	sem, _ := b["semantics"].(map[string]interface{})
	bp, _ := sem["bundle_protocol"].(string)
	rp, _ := sem["causal_rewind_protocol"].(string)
	check("CF0.5", knownSemantics[bp] && knownSemantics[rp])

	ev, evOk := b["evidence"].(map[string]interface{})
	iv, ivOk := b["intervention"].(map[string]interface{})
	if !evOk || !ivOk {
		// signed-or-raw object without the bundle schema — not a
		// cf bundle; reject, never panic on hostile input
		v := map[string]interface{}{
			"verdict": "REJECTED",
			"checks":  map[string]string{"parse": "FAIL"},
		}
		out, _ := json.MarshalIndent(v, "", " ")
		fmt.Println(string(out))
		os.Exit(1)
	}
	chainsRaw := ev["chains"].(map[string]interface{})
	midI := iv["memory_id"].(string)
	seqI, _ := strconv.Atoi(iv["seq"].(json.Number).String())

	chains := map[string][]map[string]interface{}{}
	linked := true
	for mid, chv := range chainsRaw {
		var ch []map[string]interface{}
		for _, ev2 := range chv.([]interface{}) {
			ch = append(ch, ev2.(map[string]interface{}))
		}
		sort.Slice(ch, func(i, j int) bool {
			return seqOf(ch[i]) < seqOf(ch[j])
		})
		chains[mid] = ch
		if len(ch) > 0 {
			for i, e := range ch {
				if seqOf(e) != i {
					linked = false
				}
			}
		}
		prev := genesis(mid)
		for _, e := range ch {
			if e["prev_hash"].(string) != prev {
				linked = false
			}
			h, err := entryHash(mid, e, prev)
			if err != nil || h != e["entry_hash"].(string) {
				linked = false
			}
			cj2, err2 := canonJSON(payloadOf(e))
			if err2 != nil ||
				cj2 != e["payload_json"].(string) {
				linked = false
			}
			prev = e["entry_hash"].(string)
		}
	}
	check("CF1", linked)

	receipts := ev["receipts"].(map[string]interface{})
	decisions := []map[string]interface{}{}
	for _, dv := range ev["decisions"].([]interface{}) {
		decisions = append(decisions, dv.(map[string]interface{}))
	}
	embOK := true
	for _, d := range decisions {
		qv, _ := d["query_embedding"].([]interface{})
		parts := []interface{}{}
		for _, x := range qv {
			parts = append(parts, x)
		}
		ej, _ := canonJSON(map[string]interface{}{"v": parts})
		qs := sha256hex([]byte(ej))
		rsha := d["receipt_sha256"].(string)
		rec, _ := receipts[rsha].(map[string]interface{})
		if qs != d["query_embedding_sha256"].(string) ||
			rec == nil || rec["query_sha256"].(string) != qs {
			embOK = false
		}
	}
	check("CF1.5", embOK)

	// world as data
	mems := []memory{}
	for _, mv := range ev["memories"].([]interface{}) {
		m := mv.(map[string]interface{})
		var emb map[string]interface{}
		switch e := m["embedding_json"].(type) {
		case string:
			v, _ := strictJSON([]byte(e))
			emb, _ = v.(map[string]interface{})
		case map[string]interface{}:
			emb = e
		}
		vec := []*big.Rat{}
		for _, x := range emb["v"].([]interface{}) {
			vec = append(vec, ratFromStr(x.(string)))
		}
		mems = append(mems, memory{
			id:     m["memory_id"].(string),
			vec:    vec,
			status: m["custody_status"].(string),
			fstate: m["field_state"].(string)})
	}
	links := []link{}
	for _, lv := range ev["cell_links"].([]interface{}) {
		l := lv.(map[string]interface{})
		links = append(links, link{l["from_id"].(string),
			l["to_id"].(string), l["link_type"].(string)})
	}
	var tI string
	for _, e := range chains[midI] {
		if seqOf(e) == seqI {
			tI = e["created_at"].(string)
		}
	}
	topK, _ := strconv.Atoi(
		receipts[sortedKeys(receipts)[0]].(map[string]interface{})["top_k"].(json.Number).String())
	hops, _ := strconv.Atoi(
		receipts[sortedKeys(receipts)[0]].(map[string]interface{})["hops"].(json.Number).String())

	servedAt := func(qv []interface{}, dead map[string]map[int]bool,
		asOf string, useAsOf bool) []string {
		world := []memory{}
		for _, m := range mems {
			ch := chains[m.id]
			var ds map[int]bool
			if dead != nil {
				ds = dead[m.id]
			}
			st, fs, _ := replay(ch, ds, asOf, useAsOf)
			world = append(world, memory{m.id, m.vec, st, fs})
		}
		q := []*big.Rat{}
		for _, x := range qv {
			q = append(q, ratFromStr(x.(string)))
		}
		return independentRecall(world, links, q, topK, hops)
	}

	consistent := true
	for _, d := range decisions {
		if d["created_at"].(string) <= tI {
			continue
		}
		rec := receipts[d["receipt_sha256"].(string)]
		if rec == nil {
			consistent = false
			continue
		}
		served := servedAt(
			d["query_embedding"].([]interface{}), nil,
			d["created_at"].(string), true)
		exp := []string{}
		for _, x := range rec.(map[string]interface{})["served"].([]interface{}) {
			exp = append(exp, x.(string))
		}
		if !eqStr(served, exp) {
			consistent = false
		}
	}
	check("CF2", consistent)

	ownConseq := func(did string) map[string]map[int]bool {
		out := map[string]map[int]bool{}
		for mid, ch := range chains {
			for j, e := range ch {
				et := e["event_type"].(string)
				p := payloadOf(e)
				if et == "DECISION_USED_MEMORY" &&
					p["decision_id"] == did {
					if out[mid] == nil {
						out[mid] = map[int]bool{}
					}
					out[mid][seqOf(e)] = true
					if j+1 < len(ch) &&
						ch[j+1]["event_type"].(string) == "REINFORCED" &&
						payloadOf(ch[j+1])["caused_by_decision_id"] == nil {
						out[mid][seqOf(ch[j+1])] = true
					}
				} else if et == "REINFORCED" &&
					p["caused_by_decision_id"] == did {
					if out[mid] == nil {
						out[mid] = map[int]bool{}
					}
					out[mid][seqOf(e)] = true
				}
			}
		}
		return out
	}

	sort.Slice(decisions, func(i, j int) bool {
		a, bb := decisions[i], decisions[j]
		if a["created_at"] != bb["created_at"] {
			return a["created_at"].(string) <
				bb["created_at"].(string)
		}
		return a["decision_id"].(string) <
			bb["decision_id"].(string)
	})

	dead := map[string]map[int]bool{midI: {seqI: true}}
	divergent := []string{}
	ungrounded := []interface{}{}
	invalidated := [][]interface{}{}
	propagation := []interface{}{}
	for _, d := range decisions {
		if d["created_at"].(string) <= tI {
			continue
		}
		deadEval := map[string]map[int]bool{}
		for m, ds := range dead {
			deadEval[m] = map[int]bool{}
			for s := range ds {
				deadEval[m][s] = true
			}
		}
		for m, ds := range ownConseq(d["decision_id"].(string)) {
			if deadEval[m] == nil {
				deadEval[m] = map[int]bool{}
			}
			for s := range ds {
				deadEval[m][s] = true
			}
		}
		servedSet := map[string]bool{}
		for _, s := range servedAt(
			d["query_embedding"].([]interface{}), deadEval,
			d["created_at"].(string), true) {
			servedSet[s] = true
		}
		used := []string{}
		for _, x := range d["used"].([]interface{}) {
			used = append(used, x.(string))
		}
		fallen := []string{}
		for _, m := range used {
			if !servedSet[m] {
				fallen = append(fallen, m)
			}
		}
		sort.Strings(fallen)
		if len(fallen) == 0 {
			continue
		}
		divergent = append(divergent,
			d["receipt_sha256"].(string))
		kill := [][]interface{}{}
		sortedUsed := append([]string{}, used...)
		sort.Strings(sortedUsed)
		for _, mid := range sortedUsed {
			ch := chains[mid]
			for j, e := range ch {
				et := e["event_type"].(string)
				p := payloadOf(e)
				if et == "DECISION_USED_MEMORY" &&
					p["decision_id"] == d["decision_id"] {
					if dead[mid] == nil {
						dead[mid] = map[int]bool{}
					}
					dead[mid][seqOf(e)] = true
					kill = append(kill, []interface{}{
						mid, json.Number(strconv.Itoa(seqOf(e))),
						"DECISION_USED_MEMORY"})
					if j+1 < len(ch) &&
						ch[j+1]["event_type"].(string) == "REINFORCED" &&
						payloadOf(ch[j+1])["caused_by_decision_id"] == nil {
						dead[mid][seqOf(ch[j+1])] = true
						kill = append(kill, []interface{}{
							mid,
							json.Number(strconv.Itoa(seqOf(ch[j+1]))),
							"REINFORCED"})
					}
				} else if et == "REINFORCED" &&
					p["caused_by_decision_id"] == d["decision_id"] {
					if dead[mid] == nil {
						dead[mid] = map[int]bool{}
					}
					dead[mid][seqOf(e)] = true
					kill = append(kill, []interface{}{
						mid, json.Number(strconv.Itoa(seqOf(e))),
						"REINFORCED"})
				}
			}
		}
		usedArr := []interface{}{}
		for _, u := range used {
			usedArr = append(usedArr, u)
		}
		fallenArr := []interface{}{}
		for _, f := range fallen {
			fallenArr = append(fallenArr, f)
		}
		ungrounded = append(ungrounded, map[string]interface{}{
			"decision_id": d["decision_id"],
			"used":        usedArr,
			"fallen":      fallenArr})
		invalidated = append(invalidated, kill...)
		invArr := []interface{}{}
		for _, k := range kill {
			invArr = append(invArr, []interface{}{k[0], k[1]})
		}
		propagation = append(propagation, map[string]interface{}{
			"decision_id": d["decision_id"],
			"invalidated": invArr})
	}

	rep := b["report"].(map[string]interface{})
	divOK := eqStr(toStrs(rep["divergent_receipts"]), divergent)
	check("CF3-divergent", divOK)
	check("CF3-ungrounded",
		jsonEq(rep["ungrounded_decisions"], ungrounded))
	repInv := [][]interface{}{}
	for _, x := range rep["invalidated"].([]interface{}) {
		xa := x.([]interface{})
		repInv = append(repInv, []interface{}{
			xa[0], xa[1], xa[2]})
	}
	invNorm := [][]interface{}{}
	for _, k := range invalidated {
		invNorm = append(invNorm, k)
	}
	check("CF3-invalidated", jsonEq(repInv, invNorm))
	check("CF3-propagation",
		jsonEq(rep["propagation"], propagation))

	cfStates := map[string]interface{}{}
	mids := []string{}
	for m := range dead {
		mids = append(mids, m)
	}
	sort.Strings(mids)
	for _, m := range mids {
		st, fs, cf := replay(chains[m], dead[m], "", false)
		cfStates[m] = map[string]interface{}{
			"custody_status": st, "field_state": fs,
			"confidence":     cf.RatString()}
	}
	check("CF3-states",
		jsonEq(rep["counterfactual_states"], cfStates))
	repBody := map[string]interface{}{}
	for k, v := range rep {
		if k != "report_sha256" {
			repBody[k] = v
		}
	}
	rc, _ := canonJSON(repBody)
	check("CF3-digest",
		rep["report_sha256"].(string) == sha256hex([]byte(rc)))

	all := true
	verdict := map[string]interface{}{
		"checks": map[string]string{},
		"recomputed": map[string]int{
			"divergent_receipts":   len(divergent),
			"ungrounded_decisions": len(ungrounded),
			"invalidated_events":   len(invalidated)},
		"intervention": map[string]interface{}{
			"memory_id": midI, "seq": seqI},
		"payload_type": env["payloadType"],
		"protocols":    sem,
	}
	for _, n := range order {
		verdict["checks"].(map[string]string)[n] = statusOf(checks[n])
		if !checks[n] {
			all = false
		}
	}
	if all {
		if authenticated {
			verdict["verdict"] = "VERIFIED_AUTHENTICATED"
			verdict["verified_by"] = []string{signer}
		} else {
			verdict["verdict"] = "VERIFIED_ORIGIN_UNTRUSTED"
		}
	} else {
		verdict["verdict"] = "REJECTED"
	}
	out, _ := json.MarshalIndent(verdict, "", " ")
	fmt.Println(string(out))
	if !all {
		os.Exit(1)
	}
}

func sortedKeys(m map[string]interface{}) []string {
	ks := []string{}
	for k := range m {
		ks = append(ks, k)
	}
	sort.Strings(ks)
	return ks
}

func toStrs(v interface{}) []string {
	out := []string{}
	if a, ok := v.([]interface{}); ok {
		for _, x := range a {
			out = append(out, x.(string))
		}
	}
	return out
}

func eqStr(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func norm(v interface{}) interface{} {
	switch x := v.(type) {
	case map[string]interface{}:
		out := map[string]interface{}{}
		for k, e := range x {
			out[k] = norm(e)
		}
		return out
	case []interface{}:
		out := make([]interface{}, len(x))
		for i, e := range x {
			out[i] = norm(e)
		}
		return out
	case json.Number:
		return x.String()
	default:
		return x
	}
}

func jsonEq(a, b interface{}) bool {
	aj, _ := canonJSON(toIface(a))
	bj, _ := canonJSON(toIface(b))
	return aj == bj
}

func toIface(v interface{}) interface{} {
	switch x := v.(type) {
	case map[string]interface{}:
		out := map[string]interface{}{}
		for k, e := range x {
			out[k] = toIface(e)
		}
		return out
	case []map[string]interface{}:
		out := make([]interface{}, len(x))
		for i, e := range x {
			out[i] = toIface(e)
		}
		return out
	case [][]interface{}:
		out := make([]interface{}, len(x))
		for i, e := range x {
			out[i] = toIface(e)
		}
		return out
	case []interface{}:
		out := make([]interface{}, len(x))
		for i, e := range x {
			out[i] = toIface(e)
		}
		return out
	case json.Number:
		n, _ := strconv.Atoi(x.String())
		return json.Number(strconv.Itoa(n))
	default:
		return x
	}
}

func statusOf(ok bool) string {
	if ok {
		return "PASS"
	}
	return "FAIL"
}
