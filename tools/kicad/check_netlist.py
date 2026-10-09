"""Compare the KiCad-exported schematic netlist with the design database."""
import re, sys
from . import design as D

def parse(path):
    s = open(path).read()
    nets = {}
    heads = list(re.finditer(r'\(net \(code "\d+"\) \(name "([^"]+)"\)', s))
    for i, m in enumerate(heads):
        name = m.group(1)
        block = s[m.end():heads[i + 1].start()] if i + 1 < len(heads) else s[m.end():]
        nodes = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', block)
        nets[name] = set(nodes)
    comps = re.findall(r'\(comp \(ref "([^"]+)"\)', s)
    return nets, comps

def main(path):
    nets, comps = parse(path)
    dnets = {n: set(p) for n, p in D.nets_of(D.build()).items() if not n.startswith("NC_")}
    ok = True
    for n, pins in dnets.items():
        kn = nets.get(n)
        if kn is None:
            # KiCad may rename a net; find by pins
            match = [k for k, v in nets.items() if v == pins]
            print(f"MISSING net {n} (pins {sorted(pins)}) -> kicad has {match}"); ok = False
        elif kn != pins:
            print(f"DIFF net {n}: design-only {sorted(pins - kn)} kicad-only {sorted(kn - pins)}"); ok = False
    extra = {n for n in set(nets) - set(dnets) if not n.startswith("unconnected-")}
    if extra:
        print("extra nets in kicad:", sorted(extra)); ok = False
    dcomps = set(c.ref for c in D.build())
    if set(comps) != dcomps:
        print("component mismatch:", sorted(set(comps) ^ dcomps)); ok = False
    print("netlist", "MATCHES design" if ok else "MISMATCH", f"({len(nets)} nets, {len(comps)} components)")
    return ok

if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1]) else 1)
