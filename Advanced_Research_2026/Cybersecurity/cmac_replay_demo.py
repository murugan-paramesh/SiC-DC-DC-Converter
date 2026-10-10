#!/usr/bin/env python3
"""
Demonstration of the authenticated CAN command format proposed in README.md: AES-128-CMAC (RFC 4493) over the frame
with a monotonic replay counter. Pure Python (standard library only), self-checked against the published test vectors:
  AES-128 (FIPS-197 C.1): key 000102..0f, plaintext 00112233..ff -> 69c4e0d86a7b0430d8cdb78070b4c55a
  AES-CMAC (RFC 4493 section 4): key 2b7e1516..4f3c, messages of 0 / 16 / 40 / 64 bytes
If a self-check fails the script says so and exits non-zero: no vector is "corrected" to pass.

Frame (CAN FD, 16-byte payload, ID 0x200 command):
   byte 0      command id (0x01 EN, 0x02 MODE_CV, 0x03 MODE_CP, 0x04 CLR_FAULT, 0x05 DERATE)
   bytes 1-3   argument, int24 big-endian, fixed point (V x 10, W x 1)
   bytes 4-7   replay counter, uint32 big-endian, monotonic per key
   bytes 8-15  MAC = AES-128-CMAC(K, ID(2 bytes BE) || bytes 0..7) truncated to 64 bits (RFC 4493 allows truncation; 64 bits
               on a 10 Hz command channel gives a forgery probability of 2^-64 per attempt, rate-limited by the bus)
Receiver rule: accept iff MAC matches (constant-time compare) AND counter > last_accepted AND counter - last_accepted <= WINDOW;
last_accepted is persisted (flash/EEPROM emulation) every PERSIST_EVERY accepts and advanced by PERSIST_EVERY at boot so a
reboot can never re-accept a counter value. Classic CAN 2.0B (8-byte payload) variant: two frames (data + MAC) or a 32-bit
MAC with a 16-bit counter - weaker, documented in README.
Outputs: results/cmac_test_vectors.json (self-check + demo vectors), results/demo_log.md, results/provenance.json
"""
import os, sys, json, time, hashlib, platform, hmac

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True); T0 = time.time()


# ----------------------------------------------------------------------------- AES-128 (FIPS-197), pure Python
def _gf_mul(a, b):
    p = 0
    for _ in range(8):
        if b & 1: p ^= a
        hi = a & 0x80; a = (a << 1) & 0xFF
        if hi: a ^= 0x1B
        b >>= 1
    return p


def _build_sbox():
    inv = [0] * 256
    for i in range(1, 256):
        if inv[i]: continue
        for j in range(1, 256):
            if _gf_mul(i, j) == 1: inv[i] = j; inv[j] = i; break
    sbox = []
    for i in range(256):
        b = inv[i]; s = 0
        for k in range(8):
            bit = ((b >> k) & 1) ^ ((b >> ((k + 4) % 8)) & 1) ^ ((b >> ((k + 5) % 8)) & 1) ^ ((b >> ((k + 6) % 8)) & 1) ^ ((b >> ((k + 7) % 8)) & 1) ^ ((0x63 >> k) & 1)
            s |= bit << k
        sbox.append(s)
    return sbox


SBOX = _build_sbox()
RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]


def _expand_key(key):
    w = [list(key[4 * i:4 * i + 4]) for i in range(4)]
    for i in range(4, 44):
        t = list(w[i - 1])
        if i % 4 == 0:
            t = t[1:] + t[:1]; t = [SBOX[b] for b in t]; t[0] ^= RCON[i // 4 - 1]
        w.append([w[i - 4][j] ^ t[j] for j in range(4)])
    return [sum(w[4 * r:4 * r + 4], []) for r in range(11)]


def aes128_encrypt_block(key, block):
    rk = _expand_key(key); s = [block[i] ^ rk[0][i] for i in range(16)]
    for rnd in range(1, 11):
        s = [SBOX[b] for b in s]                                            # SubBytes (state column-major: s[r + 4c])
        s = [s[(i + 4 * (i % 4)) % 16] for i in range(16)]                  # ShiftRows
        if rnd != 10:                                                       # MixColumns
            t = []
            for c in range(4):
                a = s[4 * c:4 * c + 4]
                t += [_gf_mul(a[0], 2) ^ _gf_mul(a[1], 3) ^ a[2] ^ a[3], a[0] ^ _gf_mul(a[1], 2) ^ _gf_mul(a[2], 3) ^ a[3],
                      a[0] ^ a[1] ^ _gf_mul(a[2], 2) ^ _gf_mul(a[3], 3), _gf_mul(a[0], 3) ^ a[1] ^ a[2] ^ _gf_mul(a[3], 2)]
            s = t
        s = [s[i] ^ rk[rnd][i] for i in range(16)]
    return bytes(s)


# ----------------------------------------------------------------------------- AES-CMAC (RFC 4493)
def _shift_left_xor(b, xor_last):
    v = int.from_bytes(b, "big"); msb = v >> 127; v = (v << 1) & ((1 << 128) - 1)
    if msb: v ^= xor_last
    return v.to_bytes(16, "big")


def cmac_subkeys(key):
    L = aes128_encrypt_block(key, bytes(16)); K1 = _shift_left_xor(L, 0x87); K2 = _shift_left_xor(K1, 0x87); return K1, K2


def aes_cmac(key, msg):
    K1, K2 = cmac_subkeys(key); n = (len(msg) + 15) // 16
    if n == 0: n = 1; last_complete = False
    else: last_complete = len(msg) % 16 == 0
    if last_complete: last = bytes(a ^ b for a, b in zip(msg[16 * (n - 1):], K1))
    else:
        pad = msg[16 * (n - 1):] + b"\x80" + bytes(15 - len(msg[16 * (n - 1):])); last = bytes(a ^ b for a, b in zip(pad, K2))
    X = bytes(16)
    for i in range(n - 1):
        X = aes128_encrypt_block(key, bytes(a ^ b for a, b in zip(X, msg[16 * i:16 * i + 16])))
    return aes128_encrypt_block(key, bytes(a ^ b for a, b in zip(X, last)))


def self_check():
    out = {}
    ct = aes128_encrypt_block(bytes(range(16)), bytes.fromhex("00112233445566778899aabbccddeeff"))
    out["AES128_FIPS197_C1"] = dict(expected="69c4e0d86a7b0430d8cdb78070b4c55a", got=ct.hex(), ok=ct.hex() == "69c4e0d86a7b0430d8cdb78070b4c55a")
    key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
    m = bytes.fromhex("6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e5130c81c46a35ce411e5fbc1191a0a52eff69f2445df4f9b17ad2b417be66c3710")
    vec = [(0, "bb1d6929e9593728" "7fa37d129b756746"), (16, "070a16b46b4d4144" "f79bdd9dd04a287c"), (40, "dfa66747de9ae630" "30ca32611497c827"), (64, "51f0bebf7e3b9d92" "fc49741779363cfe")]
    for ln, exp in vec:
        got = aes_cmac(key, m[:ln]).hex(); out[f"CMAC_RFC4493_len{ln}"] = dict(expected=exp, got=got, ok=got == exp)
    return out


# ----------------------------------------------------------------------------- command channel
CMD = {0x01: "EN", 0x02: "MODE_CV", 0x03: "MODE_CP", 0x04: "CLR_FAULT", 0x05: "DERATE"}
CAN_ID = 0x200; WINDOW = 256; PERSIST_EVERY = 64


def build_frame(key, cmd, arg, counter):
    payload = bytes([cmd]) + int(arg & 0xFFFFFF).to_bytes(3, "big") + int(counter).to_bytes(4, "big")
    mac = aes_cmac(key, CAN_ID.to_bytes(2, "big") + payload)[:8]
    return payload + mac


class Receiver:
    def __init__(self, key, persisted_counter=0):
        self.key = key; self.last = persisted_counter + PERSIST_EVERY      # boot: jump ahead of anything possibly accepted before the last persist
        self.persisted = self.last; self.accepts = 0; self.log = []
    def receive(self, frame):
        if len(frame) != 16: return self._r("reject: length", frame)
        payload, mac = frame[:8], frame[8:]
        exp = aes_cmac(self.key, CAN_ID.to_bytes(2, "big") + payload)[:8]
        if not hmac.compare_digest(exp, mac): return self._r("reject: MAC", frame)                 # constant-time compare
        ctr = int.from_bytes(payload[4:8], "big")
        if ctr <= self.last: return self._r("reject: replay / stale counter", frame)
        if ctr - self.last > WINDOW: return self._r("reject: counter jump beyond window (resync required)", frame)
        self.last = ctr; self.accepts += 1
        if self.accepts % PERSIST_EVERY == 0: self.persisted = self.last
        cmd = CMD.get(payload[0], "unknown"); arg = int.from_bytes(payload[1:4], "big", signed=True)
        return self._r(f"accept: {cmd} arg={arg} ctr={ctr}", frame)
    def _r(self, msg, frame):
        self.log.append((frame.hex(), msg)); return msg


def demo():
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f"); wrong = bytes.fromhex("ffeeddccbbaa99887766554433221100")
    rx = Receiver(key, persisted_counter=1000); ctr = rx.last + 1
    steps = []
    def step(desc, frame): steps.append(dict(case=desc, frame=frame.hex(), result=rx.receive(frame)))
    f1 = build_frame(key, 0x01, 1, ctr); step("valid EN,1", f1)
    step("replay of the same frame", f1)
    f2 = build_frame(key, 0x02, 4000, ctr + 1); step("valid MODE_CV 400.0 V", f2)
    tampered = bytearray(f2); tampered[2] ^= 0x10; step("same frame with the argument modified (MAC must fail)", bytes(tampered))
    step("frame built with the wrong key", build_frame(wrong, 0x04, 0, ctr + 2))
    step("counter rolled back (ctr - 5)", build_frame(key, 0x03, 3000, ctr - 5))
    step("counter jump beyond the window (+1000)", build_frame(key, 0x03, 3000, ctr + 1000))
    step("lost frames: counter +10 within the window (accepted, gap tolerated)", build_frame(key, 0x03, (-3000) & 0xFFFFFF, ctr + 12))
    step("CLR_FAULT with a valid MAC and counter (accepted - authentication does not make the command safe, the state machine still re-faults if the condition persists)", build_frame(key, 0x04, 0, ctr + 13))
    rx2 = Receiver(key, persisted_counter=rx.persisted)
    steps.append(dict(case="after a reboot with the persisted counter: last valid frame replayed", frame=build_frame(key, 0x04, 0, ctr + 13).hex(), result=rx2.receive(build_frame(key, 0x04, 0, ctr + 13))))
    steps.append(dict(case="after the reboot: fresh counter ahead of the jump-ahead value", frame=build_frame(key, 0x01, 1, rx2.last + 1).hex(), result=rx2.receive(build_frame(key, 0x01, 1, rx2.last + 1))))
    return steps


def main():
    sc = self_check(); ok = all(v["ok"] for v in sc.values())
    steps = demo()
    expect = ["accept", "reject", "accept", "reject", "reject", "reject", "reject", "accept", "accept", "reject", "accept"]
    demo_ok = all(s["result"].startswith(e) for s, e in zip(steps, expect))
    json.dump(dict(self_check=sc, self_check_ok=ok, demo=steps, demo_ok=demo_ok, frame_format=__doc__.split("Frame")[1].split("Outputs")[0].strip()), open(os.path.join(RES, "cmac_test_vectors.json"), "w"), indent=1)
    md = ["# CMAC / replay-counter demonstration (generated by cmac_replay_demo.py)\n", "## Self-check against published vectors", "| vector | expected | got | ok |", "|---|---|---|---|"]
    md += [f"| {k} | {v['expected']} | {v['got']} | {v['ok']} |" for k, v in sc.items()]
    md += ["", f"**Self-check {'PASSED' if ok else 'FAILED'}**", "", "## Command-channel demo (key 000102..0f, CAN ID 0x200, window 256, persist every 64)", "| case | frame (hex) | receiver result |", "|---|---|---|"]
    md += [f"| {s['case']} | `{s['frame']}` | {s['result']} |" for s in steps]
    md += ["", f"Demo expectations {'met' if demo_ok else 'NOT met'}."]
    open(os.path.join(RES, "demo_log.md"), "w").write("\n".join(md) + "\n"); print("\n".join(md))
    head = open(os.path.join(REPO, ".git", "HEAD")).read().strip(); commit = head
    if head.startswith("ref:"):
        rp = os.path.join(REPO, ".git", head[5:]); commit = open(rp).read().strip() if os.path.exists(rp) else head
    json.dump(dict(script="cmac_replay_demo.py", python=platform.python_version(), git_commit=commit, wall_time_s=round(time.time() - T0, 2), deterministic="fixed keys, no random numbers",
                   inputs={"Advanced_Research_2026/Cybersecurity/cmac_replay_demo.py": hashlib.sha256(open(__file__, "rb").read()).hexdigest()[:16]}, self_check_ok=ok, demo_ok=demo_ok),
              open(os.path.join(RES, "provenance.json"), "w"), indent=1)
    sys.exit(0 if (ok and demo_ok) else 1)


if __name__ == "__main__":
    main()
