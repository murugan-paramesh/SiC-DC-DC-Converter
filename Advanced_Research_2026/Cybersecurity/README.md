# Cybersecurity: IEC 62443 applicability, secure boot / signed update, authenticated CAN commands

**Maturity: L0-L1 (document only, plus a standard-library Python demonstration of the message format).** Nothing here has
been implemented in the firmware, no key management exists, no penetration test was done. Statements about the C2000
silicon are datasheet-level recollections marked **"to verify against the current TRM"**. The project's controller is
the **TMS320F280049C** (LAUNCHXL-F280049C, EL-14, `10_Firmware/hal/c2000`); where the brief mentions the TMS320F2837x
the equivalent features are noted, but all of it must be checked against the device-specific Technical Reference Manual.

Script: `python3 Advanced_Research_2026/Cybersecurity/cmac_replay_demo.py` (< 1 s; exit code 0 only if the AES / CMAC
self-check against FIPS-197 C.1 and RFC 4493 vectors passes and the demo behaves as expected). Outputs:
`results/cmac_test_vectors.json`, `results/demo_log.md`, `results/provenance.json`.

## 1. Where IEC 62443 applies to this converter

The converter is a *component* (IEC 62443-4-2 "embedded device") inside a system that an integrator assesses under
62443-3-2 / 3-3; the development process would fall under 62443-4-1. The applicable deliverable from a component vendor
is a security-capability statement per foundational requirement (FR), not a certification.

Zones and conduits (component view):

| zone / conduit | content | trust | notes |
|---|---|---|---|
| Z-PWR (power stage) | gate drivers, comparators, PROT_DIS, TZ inputs | hardware, no software reachability for thresholds | protection thresholds are resistors (R141 burden, R159 OV divider) |
| Z-CTRL (control, SELV) | C2000 LaunchPad, ADC chain, firmware, parameter block | trusted once booted from authenticated flash | physically inside the IP20 module in a locked cabinet (APP-02) |
| C-CAN (conduit) | TCAN332 non-isolated CAN FD transceiver, 500 kbit/s, IDs 0x100/0x101 status, 0x200 command, 0x7FF heartbeat | **untrusted** (shared cabinet bus) | ISO1042 isolated variant is the documented upgrade |
| C-UART (service port J15) | 3.3 V UART, `$C,...` ASCII commands with CRC-16 | untrusted, physical access required | should be disabled in operation or require the same authentication |
| C-JTAG (LaunchPad XDS110) | debug / flash programming | untrusted after manufacturing | lock before shipment (section 3) |
| C-UPDATE | firmware image delivered over CAN or UART to a bootloader | untrusted | signed images (section 3) |
| C-INTERLOCK (J17) | 24 V precharge feedback / external enable through PC817 | physical signals | not a cyber conduit; cannot be driven from software |

Target security level: **SL-T 1 for the component in a restricted-access cabinet, SL-T 2 for the CAN conduit** if the
cabinet bus is shared with third-party equipment (62443-3-3 FR mapping below). This is an engineering proposal, not an
assessment result.

| FR (62443-4-2) | current state (rev A) | proposal |
|---|---|---|
| FR1 identification & authentication | none: any node can send 0x200 | per-device 128-bit key, CMAC on every command (section 4) |
| FR2 use control | none: `$C,EN`, `$C,MODE`, `$C,CLR` accepted from anyone | authenticated commands; command whitelist per key (operator key cannot change limits) |
| FR3 system integrity | CRC-16 on telemetry only; no code integrity check | secure boot, signed update, parameter-block CRC (also an FMEDA diagnostic) |
| FR4 data confidentiality | n/a (telemetry is not confidential) | none needed; keys in OTP / secure zone |
| FR5 restricted data flow | CAN IDs fixed; no filtering | accept only 0x200/0x7FF from the configured source; drop everything else |
| FR6 timely response to events | fault log ring (8 entries) in RAM | persistent security log (section 5), authentication-failure counter in telemetry |
| FR7 resource availability | heartbeat loss -> FLT_COMM (safe state) | rate limiting of commands, DoS on CAN degrades to safe state by design |

## 2. Threat model (STRIDE) for the CAN interface and the update path

| threat | asset / entry | effect on THIS design | existing barrier | proposed control |
|---|---|---|---|---|
| Spoofing a command frame (0x200) | CAN | enable, change mode / reference, clear faults | none | CMAC + counter (section 4) |
| Spoofing the heartbeat (0x7FF) | CAN | keeps the converter running after the real supervisor died | none | heartbeat carries the counter + MAC |
| Tampering with a frame in flight | CAN | wrong reference (bounded by the command parser: 250-460 V, +/-7 kW) | range check in `dab_comm_parse_command` | MAC |
| Tampering with the firmware image | update path | arbitrary code in Z-CTRL | none | signed image, verified by an immutable bootloader |
| Repudiation | CAN | no record of who commanded what | fault log only | logged counter + key id per accepted command |
| Information disclosure | telemetry | state, fault, voltages, currents | - | not sensitive; keys never leave the device |
| Denial of service (bus flooding, heartbeat suppression) | CAN | FLT_COMM after 500 ms -> gates off (safe); loss of availability | FLT_COMM | accept; availability is a system-level concern |
| Elevation of privilege via JTAG | debug port | read keys, reflash | none | JTAG lock / password, debug disabled in the field |
| Replay of a recorded valid frame | CAN | re-enable, re-clear | none | monotonic counter, persisted |
| Reference manipulation to drive the plant to its limits | CAN | reference at 460 V / 7 kW: the firmware limiter and the OV comparator bound it | limits in firmware + hardware (section 6) | unchanged; this is why the hardware path must stay software-independent |

What an attacker on the CAN bus **cannot** do in rev A, by construction: change a protection threshold (resistors),
disable PROT_DIS (a wired-OR of comparator outputs into the driver DIS pins), hold the gates on against a hardware trip, or
exceed the inductor current limit for more than the comparator's reaction time. What they **can** do: start the converter
(with precharge satisfied), set any reference in the allowed window, clear firmware faults repeatedly, and keep it running
by forging the heartbeat.

## 3. Secure boot and signed firmware update on the C2000 (datasheet-level, to verify against the current TRM)

Features of the F28004x family as recalled (the F2837x has a DCSM of the same structure; **verify every item**):

* **Dual-zone Code Security Module (DCSM)**: two zones (Zone 1 / Zone 2), each with a 128-bit password (CSMPSWD) in OTP,
  link-pointer mechanism to update the password set, EXEONLY sectors (execute-only code: not readable even from the
  other zone), per-sector and per-RAM-block zone assignment (GRABSECT / GRABRAM). Zone 1 can hold the bootloader and the
  keys, Zone 2 the application.
* **JTAGLOCK**: a OTP bit that disables the debug port permanently unless the zone password is presented (F28004x; on
  F2837x the equivalent is the CSM-protected emulation access - verify). Irreversible: the production flow must program it
  after the final test and keep the passwords in a key store.
* **Boot ROM**: selects the boot mode by GPIO / OTP boot-mode table; the ROM itself does **not** verify signatures on
  F28004x (secure-boot ROM support appears on newer families such as F28P65x - verify). Therefore authenticated boot has to
  be implemented as a **two-stage boot**: an immutable first-stage bootloader (FSBL) in a Zone-1 EXEONLY flash sector,
  write-protected, that verifies the application image before jumping to it.
* **Flash API / ECC**: flash sectors with ECC; the FSBL can also verify a CRC of the parameter block (FMEDA diagnostic).

Proposed chain:

1. FSBL (Zone 1, EXEONLY, locked): computes SHA-256 over the application image + header, verifies an **ECDSA P-256**
   signature with a public key stored in Zone-1 OTP (preferred, allows the signing key to stay off the device), or, if
   asymmetric verification is too heavy for the C28x (ECDSA verify in software ~ 10-50 ms class, acceptable at boot - to
   verify), an **HMAC-SHA-256 with a per-device key** (simpler, but the key then exists on the device and in the factory).
   Anti-rollback: the header carries a version number compared with a monotonic counter in OTP/EEPROM emulation.
2. Update path: the application receives the new image over CAN/UART into a staging flash area (A/B layout: the DAB
   must never boot an unverified image); the FSBL verifies the staged image at the next boot and swaps; a failed
   verification keeps the old image. The update command itself is authenticated (section 4) and is only accepted in
   INIT / FAULT (never while the gates are enabled).
3. Keys: device-unique keys provisioned at end-of-line test over JTAG before JTAGLOCK; a key-rolling command
   (0x05-class, authenticated with the old key) for the CAN key. No key is ever transmitted in clear or logged.

Resource note: the control ISR uses < 5 % of the 10 us period; SHA-256 and AES in software on the C28x at 100 MHz are in
the 10-20 us (AES block) and 100 us (SHA-256 block) classes (recalled figures, to verify) - irrelevant at a 10 Hz command
rate and at boot, but they must run in the background task, never in the ISR.

## 4. Authenticated CAN commands: AES-128-CMAC with replay counters (demonstrated)

Frame (CAN FD, 16-byte payload; the TCAN332 is CAN FD capable, the current 8-byte 2.0B mapping would need two frames):

```
byte 0      command id (0x01 EN, 0x02 MODE_CV, 0x03 MODE_CP, 0x04 CLR_FAULT, 0x05 DERATE / key management)
bytes 1-3   argument, int24 big-endian, fixed point
bytes 4-7   replay counter, uint32 big-endian, monotonic per key
bytes 8-15  AES-128-CMAC(K, CAN_ID || bytes 0-7) truncated to 64 bits
```

Receiver rule: constant-time MAC compare, then `counter > last_accepted` and `counter - last_accepted <= 256` (tolerates
lost frames, forbids far jumps without a resync handshake); `last_accepted` persisted every 64 accepts and advanced by 64 at
boot so that a reboot can never re-accept an old value. The heartbeat 0x7FF uses the same construction so a dead supervisor
cannot be impersonated by a recorded stream. `cmac_replay_demo.py` implements AES-128 and CMAC from scratch (standard library
only), passes the FIPS-197 C.1 and the four RFC 4493 vectors, and shows: valid accept, replay reject, tamper reject, wrong-key
reject, rollback reject, far-jump reject, gap-within-window accept, reboot behaviour (`results/demo_log.md`).

Honest limits: a 64-bit truncated MAC with a shared symmetric key gives no non-repudiation (any key holder can forge);
the key must be per device; the counter persistence costs a flash/EEPROM write every 64 commands (6.4 s at 10 Hz - use a
wear-levelled emulation); the classic-CAN 8-byte variant (16-bit counter + 32-bit MAC) is weaker and should only be used if
CAN FD is not available on the supervisory side.

## 5. Logging

Persistent security log (flash ring, 64 entries): timestamp (period counter + RTC if available), event class
(auth failure, counter rejection, update attempt, key roll, JTAG unlock attempt if detectable), source id, counter value.
Authentication-failure counters are exported in the 0x100 status frame so the supervisor can raise an alarm; the existing
fault log ring (8 entries, RAM) should be moved to the same persistent store.

## 6. Hardware protections must never be bypassable from software or CAN - where the design enforces it

| protection | path | software reachable? | evidence in the design |
|---|---|---|---|
| inductor over-current 32 A | CT -> burden R141 -> LM393 U10 -> PROT_DIS -> driver DIS pins (U1-U4) and EPWM TZ1 | threshold: **no** (6.2 Ohm burden, resistor divider). Latch clear: the EPWM one-shot flag is cleared by `hal_trip_clear()`, but the comparator re-asserts while the condition persists, and PROT_DIS drives the driver DIS pins **directly, without the MCU** | `sensing_protection.kicad_sch`: "LM393 comparators ... wired-OR -> PROT_DIS (driver DIS + DSP TZ)"; BOM U12 note "drivers use PROT_DIS directly in rev A" |
| DC-link over-voltage 920 / 490 V | V1_SE / V2_SE -> LM393 U11 -> PROT_DIS | threshold: **no** (R159 8.2 k divider) | same |
| gate-driver UVLO | inside UCC21520 | **no** | datasheet function |
| dead time 150 ns + 22 ns interlock | EPWM dead band (software) + DT pin resistor (hardware, 2.2 k) | the EPWM dead band **is software**; the 22 ns driver interlock is not | R101 (BOM) - the hardware interlock only prevents simultaneous drive of one leg, it does not enforce 150 ns |
| precharge / enable interlock | J17 -> PC817 -> GPIO | firmware reads it; `precharge_ok` cannot be forced from CAN (not a command) | `dab_meas_t.precharge_ok` from `hal_adc_read` |
| CMPSS cycle-by-cycle limit | internal comparator with a DAC threshold | **yes - the threshold is a register**; this path is a software convenience, the LM393 path is the independent one | `hal_f28004x.h` comment; recommend register lock (EALLOW-protected lock bits, to verify) |
| firmware fault latch | `dab_ctrl_clear_fault()` from `$C,CLR` | **yes - unauthenticated today** | clears only the firmware latch; the hardware latch re-asserts if the condition persists (verified by the SIL harness and the model check in `Reliability_Engineering/`) |

Two weak points for the design owner: (1) `DIS_ALL = PROT_DIS OR DSP_DIS` through the 74HC32 is reserved and the drivers
use PROT_DIS directly - keep it that way: a software-controlled OR input must never be able to *mask* PROT_DIS (an OR cannot,
an AND could; review at the next revision); (2) the firmware-side dead time and the CMPSS threshold are software-configurable
and therefore inside the attack surface of a compromised firmware image - which is why secure boot (section 3) is the
control for them, not a CAN-level measure.

## 7. Not verified

* All C2000 security-feature statements (DCSM zones, EXEONLY, JTAGLOCK, boot-ROM behaviour, flash API) are from memory and
  must be checked against the F28004x TRM / datasheet of the current revision; the F2837x equivalents likewise.
* Crypto execution times on the C28x are class figures; no cycle count was measured.
* No implementation in `10_Firmware` (out of scope of this module); the demo is host Python.
* No formal 62443 assessment, no SL claim, no key-management process definition.
