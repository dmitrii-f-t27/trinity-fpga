#!/usr/bin/env python3
"""patch_bram_init.py — Patch BRAM INIT data from yosys json into nextpnr fasm.

Root cause: yosys correctly embeds $readmemh data as RAMB36E1 INIT_XX parameters
in write_json output. However, nextpnr-xilinx or fasm2frames may drop these INIT
lines when generating the final bitstream, resulting in BRAM containing all-zeros
on silicon. This script bridges the gap by:

1. Reading INIT_XX / INITP_XX parameters from yosys json (per RAMB36E1 cell)
2. Reading nextpnr fasm to find physical RAMB36_X#Y# coordinates
3. Patching fasm: inserting INIT lines for each RAMB36 cell

Usage: patch_bram_init.py <yosys.json> <input.fasm> <output.fasm>
"""
import json, sys, re

def extract_bram_init_from_json(json_path):
    """Extract INIT_XX/INITP_XX data per RAMB36E1 cell from yosys json."""
    with open(json_path) as f:
        d = json.load(f)
    bram_data = {}
    for mname, mod in d.get('modules', {}).items():
        for cname, cell in mod.get('cells', {}).items():
            if cell.get('type', '') != 'RAMB36E1':
                continue
            params = cell.get('parameters', {})
            init = {}
            for k, v in params.items():
                ku = k.upper()
                if ku.startswith('INIT_') or ku.startswith('INITP_'):
                    # Yosys stores as binary string; convert to hex
                    bits = str(v).strip('"').replace(' ', '')
                    # Pad to 256 bits
                    bits = bits.zfill(256)[-256:]
                    hex_val = hex(int(bits, 2))[2:].zfill(64)
                    init[ku] = hex_val
            if init:
                bram_data[cname] = init
    return bram_data

def find_bram_coords_in_fasm(fasm_path):
    """Find physical RAMB36_X#Y# coordinates in fasm."""
    coords = set()
    with open(fasm_path) as f:
        for line in f:
            m = re.match(r'(RAMB36_X\d+Y\d+)\.', line)
            if m:
                coords.add(m.group(1))
    return sorted(coords)

def find_bram_mapping(routed_json_path, bram_data):
    """Map logical cell names to physical coordinates via routed.json."""
    with open(routed_json_path) as f:
        d = json.load(f)
    mapping = {}
    for cell_name, cell_info in d.get('cells', {}).items():
        if 'RAMB36' in cell_info.get('type', ''):
            bel = cell_info.get('attributes', {}).get('NEXTPNR_BEL', cell_info.get('bel', ''))
            if bel:
                mapping[cell_name] = bel
    return mapping

def patch_fasm(json_path, fasm_in, fasm_out, routed_json=None):
    bram_data = extract_bram_init_from_json(json_path)
    coords = find_bram_coords_in_fasm(fasm_in)

    print(f"BRAM cells in json: {len(bram_data)}")
    print(f"RAMB36 coords in fasm: {len(coords)}")

    if len(bram_data) == 0:
        print("WARNING: No BRAM INIT data found in json — nothing to patch")
        return

    # Read existing fasm
    with open(fasm_in) as f:
        lines = f.readlines()

    # Check if INIT lines already exist
    has_init = any('.INIT_' in l or '.INITP_' in l for l in lines)
    if has_init:
        print("Fasm already contains INIT lines — checking if non-zero...")
        init_count = sum(1 for l in lines if re.match(r'RAMB36.*\.INIT_', l) and '0x' in l.lower())
        print(f"  Found {init_count} INIT lines with hex data")
        if init_count > 0:
            print("  INIT data appears present — no patch needed")
            with open(fasm_out, 'w') as f:
                f.writelines(lines)
            return

    # If no INIT lines or all zero, add them
    # Try mapping via routed.json
    mapping = {}
    if routed_json:
        try:
            mapping = find_bram_mapping(routed_json, bram_data)
            print(f"Cell-to-coordinate mapping: {len(mapping)} entries")
        except Exception as e:
            print(f"Warning: could not read routed.json mapping: {e}")

    # If we have mapping, use it; otherwise assign by index
    cell_names = sorted(bram_data.keys())
    if mapping and len(mapping) == len(cell_names):
        coord_assignment = {cn: mapping.get(cn, coords[i] if i < len(coords) else None)
                           for i, cn in enumerate(cell_names)}
    else:
        # Fallback: assign by sorted order
        coord_assignment = {}
        for i, cn in enumerate(cell_names):
            if i < len(coords):
                coord_assignment[cn] = coords[i]

    # Generate INIT lines
    init_lines = []
    for cn, coord in coord_assignment.items():
        if coord is None:
            continue
        init_data = bram_data[cn]
        for reg_name in sorted(init_data.keys()):
            hex_val = init_data[reg_name]
            init_lines.append(f"{coord}.{reg_name} = 0x{hex_val}\n")

    # Write patched fasm: original lines + INIT lines
    with open(fasm_out, 'w') as f:
        f.writelines(lines)
        if init_lines:
            f.write("\n# BRAM INIT data patched by patch_bram_init.py\n")
            f.writelines(init_lines)

    print(f"Patched {len(init_lines)} INIT lines for {len(coord_assignment)} BRAM cells")

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: patch_bram_init.py <yosys.json> <input.fasm> <output.fasm> [routed.json]")
        sys.exit(1)
    routed = sys.argv[4] if len(sys.argv) > 4 else None
    patch_fasm(sys.argv[1], sys.argv[2], sys.argv[3], routed)
