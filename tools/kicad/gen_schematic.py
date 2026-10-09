"""
Hierarchical schematic generator (KiCad 7 format).

Layout strategy: every symbol is placed on a grid inside titled functional
groups; each pin gets a short wire stub ending in a global label (or a power
symbol for the power nets).  This "label-netlist" style keeps the generated
schematic unambiguous and fully ERC/netlist-consistent while still being
readable by functional group.
"""
import os, json, uuid
from .sexpr import f, q, uid, font
from . import symbols as S
from . import design as _default_design

D = _default_design
LIB = D.LIB
STUB = 2.54


def use_design(module):
    """Switch the generator to another design database module (DAB board)."""
    global D, LIB
    D = module
    LIB = module.LIB


def pin_abs(sym, X, Y, number):
    px, py, orient = sym.pin_point(number)
    return X + px, Y - py, orient


def label_sexpr(net, x, y, orient):
    """Global label at the end of a stub. orient = pin orientation (0,90,180,270)."""
    ang = {0: 180, 180: 0, 270: 90, 90: 270}[orient]
    just = {0: "left", 180: "right", 90: "left", 270: "right"}[ang]
    return (f'  (global_label {q(net)} (shape passive) (at {f(x)} {f(y)} {ang}) (fields_autoplaced)\n'
            f'    (effects (font (size 1.27 1.27)) (justify {just}))\n    (uuid "{uid()}")\n'
            f'    (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {f(x)} {f(y)} 0) (effects (font (size 1.27 1.27)) hide))\n  )')


def wire(x1, y1, x2, y2):
    return f'  (wire (pts (xy {f(x1)} {f(y1)}) (xy {f(x2)} {f(y2)})) (stroke (width 0) (type default))\n    (uuid "{uid()}")\n  )'


def power_symbol(net, x, y, orient, root_uuid, sheet_uuid, pwr_count):
    """Power symbol placed with its pin at (x,y); GND-type for orient 90 (bottom pins), VCC-type for 270."""
    ref = f"#PWR{pwr_count:03d}"
    rot = 0
    val_y = y + 3.81 if orient == 90 else y - 2.54
    return (f'  (symbol (lib_id "{LIB}:{net}") (at {f(x)} {f(y)} {rot}) (unit 1)\n'
            f'    (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced)\n    (uuid "{uid()}")\n'
            f'    (property "Reference" "{ref}" (at {f(x)} {f(y)} 0) {font(1.27, hide=True)})\n'
            f'    (property "Value" {q(net)} (at {f(x)} {f(val_y)} 0) {font(1.27)})\n'
            f'    (property "Footprint" "" (at {f(x)} {f(y)} 0) {font(1.27, hide=True)})\n'
            f'    (property "Datasheet" "" (at {f(x)} {f(y)} 0) {font(1.27, hide=True)})\n'
            f'    (pin "1" (uuid "{uid()}"))\n'
            f'    (instances (project "{D.PROJECT}" (path "/{root_uuid}/{sheet_uuid}" (reference "{ref}") (unit 1))))\n  )')


def symbol_instance(comp, sym, X, Y, root_uuid, sheet_uuid, sym_uuid):
    rx, ry = sym.ref_pos; vx, vy = sym.val_pos
    props = [("Reference", comp.ref, X + rx, Y - ry, False), ("Value", comp.value, X + vx, Y - vy, False),
             ("Footprint", f"{LIB}:{comp.footprint}", X, Y, True), ("Datasheet", "", X, Y, True),
             ("MPN", comp.mpn, X, Y, True), ("Description", comp.desc, X, Y, True)]
    out = [f'  (symbol (lib_id "{LIB}:{comp.symbol}") (at {f(X)} {f(Y)} 0) (unit 1)',
           f'    (in_bom {"no" if comp.dnp else "yes"}) (on_board yes) (dnp {"yes" if comp.dnp else "no"})', f'    (uuid "{sym_uuid}")']
    for name, val, px, py, hide in props:
        out.append(f'    (property {q(name)} {q(val)} (at {f(px)} {f(py)} 0) {font(1.27, hide=hide, justify="left")})')
    for p in sym.pins:
        out.append(f'    (pin "{p["number"]}" (uuid "{uid()}"))')
    out.append(f'    (instances (project "{D.PROJECT}" (path "/{root_uuid}/{sheet_uuid}" (reference "{comp.ref}") (unit 1))))')
    out.append("  )")
    return "\n".join(out)


def cell_size(sym):
    xs = [p["x"] for p in sym.pins] or [0]; ys = [p["y"] for p in sym.pins] or [0]
    has_lr = any(p["orient"] in (0, 180) for p in sym.pins)
    has_tb = any(p["orient"] in (90, 270) for p in sym.pins)
    w = (max(xs) - min(xs)) + (2 * (STUB + 14.0) if has_lr else 12.0)
    h = (max(ys) - min(ys)) + (2 * (STUB + 6.5) if has_tb else 10.0)
    w = max(w, 20.32); h = max(h, 17.78)
    return (round(w / 2.54) * 2.54, round(h / 2.54) * 2.54)


PAPER = {"A3": (420.0, 297.0), "A2": (594.0, 420.0)}


def layout_sheet(comps, syms):
    """Return list of (comp, X, Y) and group titles [(title, x, y)], paper name."""
    for paper in ("A3", "A2"):
        W, H = PAPER[paper]
        x0, y0, xmax, ymax = 15.24, 25.4, W - 15.24, H - 30.0
        placed, titles = [], []
        x, y, row_h = x0, y0, 0
        cur_group = None
        ok = True
        for c in comps:
            w, h = cell_size(syms[c.symbol])
            if c.group != cur_group:
                cur_group = c.group
                if row_h:
                    y += row_h + 2.54
                x, row_h = x0, 0
                titles.append((cur_group, x0, y))
                y += 5.08
            if x + w > xmax:
                x = x0; y += row_h + 2.54; row_h = 0
            placed.append((c, x + w / 2, y + h / 2))
            x += w; row_h = max(row_h, h)
        if y + row_h > ymax:
            ok = False
        if ok:
            return placed, titles, paper
    return placed, titles, "A2"


def title_block(title, sheet_name, page):
    return (f'  (title_block\n    (title {q(title)})\n    (date "2026-10-09")\n    (rev "A")\n'
            f'    (company "Open hardware - SiC PSFB reference design")\n    (comment 1 {q(sheet_name)})\n'
            f'    (comment 2 "3 kW, 400 V -> 48 V, 100 kHz, ZVS phase-shifted full bridge")\n  )')


def gen_subsheet(sheet_key, sheet_title, comps, syms, root_uuid, sheet_uuid, page, pwr_counter, file_uuid):
    placed, titles, paper = layout_sheet(comps, syms)
    used = set(c.symbol for c in comps)
    body = []
    sym_uuids = {}
    for c, X, Y in placed:
        X = round(X / 1.27) * 1.27; Y = round(Y / 1.27) * 1.27
        sym = syms[c.symbol]
        su = str(uuid.uuid4()); sym_uuids[c.ref] = su
        body.append(symbol_instance(c, sym, X, Y, root_uuid, sheet_uuid, su))
        for p in sym.pins:
            net = c.pins.get(p["number"])
            px, py, orient = pin_abs(sym, X, Y, p["number"])
            if net is None or net.startswith("NC_"):
                body.append(f'  (no_connect (at {f(px)} {f(py)}) (uuid "{uid()}"))')
                continue
            dx, dy = {0: (-STUB, 0), 180: (STUB, 0), 270: (0, -STUB), 90: (0, STUB)}[orient]
            ex, ey = px + dx, py + dy
            body.append(wire(px, py, ex, ey))
            gnd_like = getattr(D, "GROUND_NETS", {"PGND", "SGND"})
            if net in D.POWER_NETS and orient in (90, 270) and ((net in gnd_like) == (orient == 90)):
                pwr_counter[0] += 1
                body.append(power_symbol(net, ex, ey, orient, root_uuid, sheet_uuid, pwr_counter[0]))
                used.add(net)
            else:
                body.append(label_sexpr(net, ex, ey, orient))
    for t, x, y in titles:
        body.append(f'  (text {q(t)} (at {f(x)} {f(y + 3.0)} 0)\n    (effects (font (size 2.0 2.0) bold) (justify left bottom))\n    (uuid "{uid()}")\n  )')
    hdr = (f'(kicad_sch (version 20230121) (generator SiC_PSFB_generator)\n\n  (uuid "{file_uuid}")\n\n  (paper "{paper}")\n\n'
           + title_block("SiC ZVS Phase-Shifted Full-Bridge 3 kW DC-DC", sheet_title, page) + "\n\n"
           + S.lib_symbols_block(syms, used, LIB) + "\n\n")
    return hdr + "\n".join(body) + "\n)\n", sym_uuids


def gen_root(root_uuid, sheet_uuids):
    body = []
    x, y = 25.4, 50.8
    for i, (key, title, fname) in enumerate(D.SHEETS):
        su = sheet_uuids[key]
        body.append(
            f'  (sheet (at {f(x)} {f(y)}) (size 63.5 25.4) (fields_autoplaced)\n'
            f'    (stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0000))\n    (uuid "{su}")\n'
            f'    (property "Sheetname" {q(title)} (at {f(x)} {f(y - 0.7)} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))\n'
            f'    (property "Sheetfile" {q(fname)} (at {f(x)} {f(y + 26.0)} 0) (effects (font (size 1.27 1.27)) (justify left top)))\n'
            f'    (instances (project "{D.PROJECT}" (path "/{root_uuid}" (page "{i + 2}"))))\n  )')
        x += 76.2
    notes = [
        "SiC ZVS PHASE-SHIFTED FULL-BRIDGE ISOLATED DC-DC CONVERTER - 3 kW",
        "Input 370-420 V DC (400 V nominal, PFC output)  |  Output 48 V / 62.5 A  |  100 kHz  |  reinforced isolation 4 kVrms",
        "Primary: 4 x C3M0060065K SiC MOSFET full bridge, 12 uH resonant inductor, C3D04065A clamp diodes, 4.7 uF DC-blocking",
        "Transformer: ETD59 3C95, 18:3:3 centre-tapped.  Secondary: 4 x IPP110N20N3 synchronous rectifiers, 6.8 uH / 2.8 mF output filter",
        "Control: UCC28951 (secondary side, peak current mode) -> UCC21520 isolated drivers (primary), UCC27524 (SR)",
        "Gate bias: 4 x R12P21503D isolated +15 V / -3 V modules.  Bias input: +12 V aux (secondary referenced).",
        "Sheets: 2 - Power Stage, 3 - Primary Gate Drive, 4 - Control and SR Drive.   Generated from tools/kicad (python).",
        "WARNING: primary side nets (VBUS, PGND, SW_A, SW_B, LR_N, PRI_x, G_Q1..4, KS_Q1..4, VDD/VEE_Q1..4) are at hazardous voltage.",
    ]
    yy = 95.0
    for i, n in enumerate(notes):
        sz = 2.5 if i == 0 else 1.5
        body.append(f'  (text {q(n)} (at 25.4 {f(yy)} 0)\n    (effects (font (size {sz} {sz}){" bold" if i == 0 else ""}) (justify left bottom))\n    (uuid "{uid()}")\n  )')
        yy += 6.0 if i == 0 else 4.5
    hdr = (f'(kicad_sch (version 20230121) (generator SiC_PSFB_generator)\n\n  (uuid "{root_uuid}")\n\n  (paper "A3")\n\n'
           + title_block("SiC ZVS Phase-Shifted Full-Bridge 3 kW DC-DC", "Root sheet", 1) + "\n\n  (lib_symbols)\n\n")
    return hdr + "\n".join(body) + '\n\n  (sheet_instances\n    (path "/" (page "1"))\n  )\n)\n'


def write_project(outdir, root_uuid, sheet_uuids):
    classes = [
        {"bus_width": 12, "clearance": 0.2, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
         "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "Default", "pcb_color": "rgba(0, 0, 0, 0.000)",
         "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": 0.3, "via_diameter": 0.8, "via_drill": 0.4, "wire_width": 6},
        {"name": "PRI_POWER", "clearance": 1.0, "track_width": 4.0, "via_diameter": 1.2, "via_drill": 0.6, "bus_width": 12, "wire_width": 6,
         "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
         "pcb_color": "rgba(255, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)"},
        {"name": "PRI_GATE", "clearance": 0.3, "track_width": 0.5, "via_diameter": 0.8, "via_drill": 0.4, "bus_width": 12, "wire_width": 6,
         "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
         "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)"},
        {"name": "SEC_POWER", "clearance": 0.5, "track_width": 4.0, "via_diameter": 1.2, "via_drill": 0.6, "bus_width": 12, "wire_width": 6,
         "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
         "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)"},
        {"name": "SEC_SIGNAL", "clearance": 0.2, "track_width": 0.3, "via_diameter": 0.8, "via_drill": 0.4, "bus_width": 12, "wire_width": 6,
         "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
         "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)"},
    ]
    nets = D.nets_of(D.build())
    patterns = [{"netclass": D.net_class(n), "pattern": n} for n in sorted(nets) if D.net_class(n) != "SEC_SIGNAL" and not n.startswith("NC_")]
    pro = {
        "board": {"3dviewports": [], "design_settings": {
            "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.2, "copper_text_size_h": 1.5, "copper_text_size_v": 1.5,
                         "copper_text_thickness": 0.3, "silk_line_width": 0.15, "silk_text_size_h": 1.0, "silk_text_size_v": 1.0, "silk_text_thickness": 0.15},
            "rules": {"min_clearance": 0.2, "min_connection": 0.0, "min_copper_edge_clearance": 0.5, "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25,
                      "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1, "min_resolved_spokes": 1, "min_silk_clearance": 0.0,
                      "min_text_height": 0.8, "min_text_thickness": 0.08, "min_through_hole_diameter": 0.3, "min_track_width": 0.2,
                      "min_via_annular_width": 0.15, "min_via_diameter": 0.5, "solder_mask_to_copper_clearance": 0.0, "use_height_for_length_calcs": True},
            "rule_severities": {"silk_overlap": "ignore", "silk_over_copper": "ignore", "lib_footprint_mismatch": "warning", "lib_footprint_issues": "ignore",
                                "copper_sliver": "warning", "zones_intersect": "error", "footprint_type_mismatch": "ignore"},
            "track_widths": [0.0, 0.3, 0.5, 1.0, 2.0, 4.0, 6.0], "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.8, "drill": 0.4}, {"diameter": 1.2, "drill": 0.6}],
            "zones_allow_external_fillets": False}, "layer_presets": [], "viewports": []},
        "boards": [], "cvpcb": {"equivalence_files": []},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": f"{D.PROJECT}.kicad_pro", "version": 1},
        "net_settings": {"classes": classes, "meta": {"version": 3}, "net_colors": None, "netclass_assignments": None, "netclass_patterns": patterns},
        "pcbnew": {"last_paths": {"gencad": "", "idf": "", "netlist": "", "specctra_dsn": "", "step": "", "vrml": ""}, "page_layout_descr_file": ""},
        "schematic": {"annotate_start_num": 0, "drawing": {"default_line_thickness": 6.0, "default_text_size": 50.0, "field_names": [], "intersheets_ref_own_page": False,
                      "intersheets_ref_prefix": "", "intersheets_ref_short": False, "intersheets_ref_show": False, "intersheets_ref_suffix": "",
                      "junction_size_choice": 3, "label_size_ratio": 0.375, "pin_symbol_size": 25.0, "text_offset_ratio": 0.15},
                      "legacy_lib_dir": "", "legacy_lib_list": [], "meta": {"version": 1}, "net_format_name": "", "page_layout_descr_file": "",
                      "plot_directory": "", "spice_current_sheet_as_root": False, "spice_external_command": "spice \"%I\"", "spice_model_current_sheet_as_root": True,
                      "spice_save_all_currents": False, "spice_save_all_voltages": False, "subpart_first_id": 65, "subpart_id_separator": 0},
        "sheets": [[root_uuid, ""]] + [[sheet_uuids[k], t] for k, t, _ in D.SHEETS],
        "text_variables": {},
    }
    with open(os.path.join(outdir, f"{D.PROJECT}.kicad_pro"), "w") as fh:
        json.dump(pro, fh, indent=2)
    with open(os.path.join(outdir, "sym-lib-table"), "w") as fh:
        fh.write(f'(sym_lib_table\n  (version 7)\n  (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/lib/{LIB}.kicad_sym")(options "")(descr "Project symbols"))\n)\n')
    with open(os.path.join(outdir, "fp-lib-table"), "w") as fh:
        fh.write(f'(fp_lib_table\n  (version 7)\n  (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/lib/{LIB}.pretty")(options "")(descr "Project footprints"))\n)\n')


def generate(outdir, syms=None, title=None, notes=None):
    os.makedirs(os.path.join(outdir, "lib"), exist_ok=True)
    if syms is None:
        syms = S.write_library(os.path.join(outdir, "lib", f"{LIB}.kicad_sym"))
    comps = D.build()
    ids_path = os.path.join(outdir, "uuids.json")
    ids = json.load(open(ids_path)) if os.path.exists(ids_path) else {}
    root_uuid = ids.setdefault("root", str(uuid.uuid4()))
    sheet_uuids = {k: ids.setdefault(f"sheet_{k}", str(uuid.uuid4())) for k, _, _ in D.SHEETS}      # sheet symbol uuids (used in paths)
    file_uuids = {k: ids.setdefault(f"file_{k}", str(uuid.uuid4())) for k, _, _ in D.SHEETS}        # sub-sheet file uuids
    pwr = [0]
    sym_uuids = {}
    for i, (key, title, fname) in enumerate(D.SHEETS):
        sheet_comps = [c for c in comps if c.sheet == key]
        txt, su = gen_subsheet(key, title, sheet_comps, syms, root_uuid, sheet_uuids[key], i + 2, pwr, file_uuids[key])
        sym_uuids.update({ref: (sheet_uuids[key], u) for ref, u in su.items()})
        with open(os.path.join(outdir, fname), "w") as fh:
            fh.write(txt)
    with open(os.path.join(outdir, f"{D.PROJECT}.kicad_sch"), "w") as fh:
        fh.write(gen_root(root_uuid, sheet_uuids))
    ids["symbols"] = {r: list(v) for r, v in sym_uuids.items()}
    json.dump(ids, open(ids_path, "w"), indent=1)
    write_project(outdir, root_uuid, sheet_uuids)
    return comps, sym_uuids


if __name__ == "__main__":
    out = os.path.join(D.ROOT, "hardware", "kicad")
    comps, _ = generate(out)
    print("schematic written:", len(comps), "symbols")
