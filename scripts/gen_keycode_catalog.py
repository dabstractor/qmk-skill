#!/usr/bin/env python3
"""Generate the QMK per-release keycode-change catalog, split one-file-per-release.

The catalog has two parts:

  references/19-keycodes-changelog.md
      A hand-written index (discovery rule, how-to, methodology). The *derived*
      part (catalog scope, per-layer cross-check, and the version→file index) is
      regenerated in place between two HTML-comment sentinels:

          <!-- BEGIN GENERATED INDEX -->
          ... (regenerated each run) ...
          <!-- END GENERATED INDEX -->

      Everything outside those sentinels is left untouched, so hand-written prose
      is never clobbered.

  references/keycodes-changelog/<version>.md
      One self-contained file per release that changed at least one keycode
      layer (e.g. 0.25.0.md). Agents (and scripts/keycodes_migration.py) load
      only the versions in their migration window.

Tracks four complementary layers (chosen as the cleanest faithful signal for each):
  - quantum/keycodes.h                 core keycode C enum (generated; readable interface)
  - quantum/quantum_keycodes.h         helper/convenience macros (hand-written)
  - quantum/quantum_keycodes_legacy.h  backward-compat deprecation shims (hand-written)
  - data/constants/keycodes/extras/    layout keycodes, DD source (generates keymap_extras/*.h)

All git operations are run inside <path-to-qmk_firmware>.

Usage:
    gen_keycode_catalog.py <path-to-qmk_firmware> -o references/19-keycodes-changelog.md
    gen_keycode_catalog.py <path-to-qmk_firmware> -o references/19-keycodes-changelog.md --split-dir references/keycodes-changelog
"""
import argparse, os, subprocess, sys, re, datetime

# (key, repo-relative path, human label, short header)
FILES = [
    ("kc",  "quantum/keycodes.h",                "Core keycodes — `keycodes.h` (generated C enum)",       "keycodes.h"),
    ("qk",  "quantum/quantum_keycodes.h",        "Helper macros — `quantum_keycodes.h` (hand-written)",   "quantum_keycodes.h"),
    ("leg", "quantum/quantum_keycodes_legacy.h", "Deprecated aliases — `quantum_keycodes_legacy.h`",       "legacy.h"),
    ("lay", "data/constants/keycodes/extras/",   "Layout keycodes — `data/constants/keycodes/extras/` (DD source)", "extras (layouts)"),
]
PATH  = {k: p for k, p, _, _ in FILES}
LABEL = {k: lbl for k, _, lbl, _ in FILES}
HDR   = {k: h   for k, _, _, h in FILES}

DIFF_CAP = 250  # max diff lines shown inline for any single layer

# Sentinels bounding the regenerated block inside the hand-written index file.
INDEX_BEGIN = "<!-- BEGIN GENERATED INDEX -->"
INDEX_END   = "<!-- END GENERATED INDEX -->"

QMK = None  # set in main(); absolute path to the qmk_firmware checkout

def run(*a):
    """Run a git command inside the qmk repo, return stdout."""
    return subprocess.run(a, cwd=QMK, capture_output=True, text=True).stdout

def ok(*a):
    """Run a command inside the qmk repo, return True on exit 0."""
    return subprocess.run(a, cwd=QMK, capture_output=True, text=True).returncode == 0

def github_identity():
    """Return canonical 'owner/repo' for the checkout's origin remote.

    Used in place of the local filesystem path so no personal/absolute path is
    ever baked into the generated catalog."""
    url = run("git", "remote", "get-url", "origin").strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else "qmk/qmk_firmware"

# ---------- tag discovery ----------
def get_tags():
    """Return the version-sorted list of release tags from the first one that contains
    quantum/keycodes.h (the file's introduction defines the catalog baseline)."""
    raw = run("git", "tag")
    ver = sorted((t for t in raw.split() if re.fullmatch(r"\d+\.\d+\.\d+", t)),
                 key=lambda v: tuple(int(x) for x in v.split(".")))
    if not ver:
        sys.exit("error: no numeric release tags found — is this the qmk_firmware repo?")
    baseline = next((t for t in ver if ok("git", "cat-file", "-e", f"{t}:quantum/keycodes.h")), None)
    if baseline is None:
        sys.exit("error: quantum/keycodes.h not found at any release tag.")
    return ver[ver.index(baseline):]

def diff_lines(prev, cur, spec):
    d = run("git", "diff", prev, cur, "--", spec)
    add = [ln[1:] for ln in d.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    rem = [ln[1:] for ln in d.splitlines() if ln.startswith("-") and not ln.startswith("---")]
    return add, rem, d

MACRO_RE = re.compile(r"\s*#define\s+([A-Za-z0-9_]+)(\([^)]*\))?\s+(.+)")
ENUM_RE  = re.compile(r"\s*(QK_[A-Z0-9_]+|KC_[A-Z0-9_]+)\s*=")
COPYRIGHT_RE = re.compile(r"//\s*Copyright\s+\d{4}")
KEY_RE = re.compile(r'"key"\s*:\s*"([^"]+)"')

def macro_names(lines):
    out = []
    for ln in lines:
        m = MACRO_RE.match(ln)
        if m:
            out.append(m.group(1) + (m.group(2) or ""))
    return out

def enum_names(lines):
    out = []
    for ln in lines:
        m = ENUM_RE.match(ln)
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out

def strip_ws(s):
    return re.sub(r"\s+", "", s)

def classify(add, rem):
    all_lines = add + rem
    if not all_lines:
        return None
    if sorted(strip_ws(x) for x in add) == sorted(strip_ws(x) for x in rem) and add:
        return "whitespace-only"
    if all(COPYRIGHT_RE.match(x) for x in all_lines):
        return "copyright-only"
    return None

# ---------- index-file in-place update ----------
def update_index_file(path, block):
    """Replace whatever lives between INDEX_BEGIN/INDEX_END in `path` with `block`.

    Sentinels are matched as WHOLE LINES (after strip()), so an inline mention
    of the sentinel text inside hand-written prose can never be mistaken for the
    real marker. The prose outside the sentinels is preserved verbatim. If the
    file lacks whole-line sentinels we refuse rather than guess where to inject,
    so the contract (markers placed by a human) is never silently violated. On
    first creation (file absent) we emit a minimal shell with the sentinels."""
    if os.path.exists(path):
        lines = open(path, encoding="utf-8").read().splitlines(keepends=True)
        begin_idx = end_idx = None
        for i, ln in enumerate(lines):
            s = ln.strip()
            if begin_idx is None and s == INDEX_BEGIN:
                begin_idx = i
            elif begin_idx is not None and end_idx is None and s == INDEX_END:
                end_idx = i
                break
        if begin_idx is None or end_idx is None:
            sys.exit(
                f"error: index file {path} has no whole-line generated-section sentinels.\n"
                f"  Put each sentinel on its own line where the version index should live:\n\n"
                f"    {INDEX_BEGIN}\n"
                f"    {INDEX_END}\n\n"
                f"  Then re-run. Everything outside the sentinels is left untouched.")
        pre = "".join(lines[:begin_idx])
        post = "".join(lines[end_idx + 1:])
        new = f"{pre}{INDEX_BEGIN}\n\n{block}\n\n{INDEX_END}\n{post}"
    else:
        header = (
            "# QMK per-release keycode changes (keycode migration catalog)\n\n"
            "<!-- Hand-written discovery rule / how-to / methodology prose belongs here. -->\n"
            "<!-- Only the block between the sentinels below is regenerated. -->\n\n")
        new = f"{header}{INDEX_BEGIN}\n\n{block}\n\n{INDEX_END}\n"
        print(f"(note: created new index file {path} with a minimal header — "
              "edit the prose outside the sentinels as needed.)")
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)

def build(tags, out_path, split_dir):
    BASELINE = tags[0]
    repo_id = github_identity()  # canonical owner/repo — never bake a local path into the output

    # ---------- churn + change-driven pairings per layer ----------
    change_at = {k: {} for k in PATH}
    prev_changed = {k: {} for k in PATH}
    for k in PATH:
        last = BASELINE
        p = tags[0]
        for t in tags[1:]:
            a, r, _ = diff_lines(p, t, PATH[k])
            if a or r:
                change_at[k][t] = (len(a), len(r))
                prev_changed[k][t] = last
                last = t
            p = t

    all_versions = sorted(
        set().union(*[set(change_at[k]) for k in PATH]),
        key=lambda v: tuple(int(x) for x in v.split(".")))

    def meta(tag):
        return (run("git", "log", "-1", "--format=%ad", "--date=short", tag).strip(),
                run("git", "rev-parse", "--short", tag).strip())

    # ---------- per-layer briefs ----------
    def kc_brief(cur, max_items=10):
        a, r, _ = diff_lines(prev_changed["kc"][cur], cur, PATH["kc"])
        cls = classify(a, r)
        if cls:
            return cls
        added = enum_names(a); macros = macro_names(a); removed = enum_names(r)
        parts = []
        if added:
            s = ", ".join(f"`{x}`" for x in added[:max_items])
            if len(added) > max_items: s += f" … (+{len(added)-max_items} more)"
            parts.append(f"added {len(added)} keycode(s): {s}")
        if macros:
            s = ", ".join(f"`{x}`" for x in macros[:max_items])
            if len(macros) > max_items: s += f" … (+{len(macros)-max_items} more)"
            parts.append(f"added {len(macros)} macro(s): {s}")
        if removed:
            parts.append(f"removed/renamed {len(removed)} keycode(s)")
        return "; ".join(parts) or "modified"

    def qk_brief(cur, max_items=10):
        a, r, _ = diff_lines(prev_changed["qk"][cur], cur, PATH["qk"])
        cls = classify(a, r)
        if cls:
            return cls
        added = macro_names(a); removed = macro_names(r)
        parts = []
        if added:
            s = ", ".join(f"`{x}`" for x in added[:max_items])
            if len(added) > max_items: s += f" … (+{len(added)-max_items} more)"
            parts.append(f"added {len(added)} macro(s): {s}")
        if removed:
            s = ", ".join(f"`{x}`" for x in removed[:max_items])
            if len(removed) > max_items: s += f" … (+{len(removed)-max_items} more)"
            parts.append(f"removed {len(removed)} macro(s): {s}")
        return "; ".join(parts) or "reorganized"

    def leg_brief(cur, max_added=8, max_removed=8):
        a, r, _ = diff_lines(prev_changed["leg"][cur], cur, PATH["leg"])
        added = []
        for ln in a:
            m = MACRO_RE.match(ln)
            if m:
                added.append((m.group(1) + (m.group(2) or ""), m.group(3).strip()))
        removed = macro_names(r)
        parts = []
        if added:
            s = ", ".join(f"`{old}`→`{new}`" for old, new in added[:max_added])
            if len(added) > max_added: s += f" … (+{len(added)-max_added} more)"
            parts.append(f"newly deprecated {len(added)}: {s}")
        if removed:
            s = ", ".join(f"`{x}`" for x in removed[:max_removed])
            if len(removed) > max_removed: s += f" … (+{len(removed)-max_removed} more)"
            parts.append(f"retired {len(removed)} old alias(es): {s}")
        return "; ".join(parts) or "modified"

    def layout_name(path):
        b = path.split("/")[-1]
        return re.sub(r"^keycodes_|_0\.0\.\d+\.hjson$", "", b)

    def layouts_brief(cur, max_names=15):
        prev = prev_changed["lay"][cur]
        a, r, _ = diff_lines(prev, cur, PATH["lay"])
        status = run("git", "diff", "--name-status", prev, cur, "--", PATH["lay"])
        new_lay, mod_lay = [], []
        for line in status.splitlines():
            if not line.strip():
                continue
            code, _, path = line.partition("\t")
            nm = layout_name(path)
            if code.startswith("A"):
                new_lay.append(nm)
            elif code.startswith("M"):
                mod_lay.append(nm)
        added_keys = sum(1 for ln in a if KEY_RE.search(ln))
        parts = []
        if new_lay:
            s = ", ".join(new_lay[:max_names])
            if len(new_lay) > max_names: s += f" … (+{len(new_lay)-max_names} more)"
            parts.append(f"{len(new_lay)} new layout(s): {s}")
        if mod_lay:
            s = ", ".join(mod_lay[:max_names])
            if len(mod_lay) > max_names: s += f" … (+{len(mod_lay)-max_names} more)"
            parts.append(f"{len(mod_lay)} layout(s) modified: {s}")
        if added_keys:
            parts.append(f"+{added_keys} keycode definitions")
        return "; ".join(parts) or "modified"

    BRIEF = {"kc": kc_brief, "qk": qk_brief, "leg": leg_brief, "lay": layouts_brief}

    def cell(k, v):
        if v not in change_at[k]:
            return "—"
        a, r = change_at[k][v]
        return f"+{a}/−{r}"

    def summary_brief(k, v):
        a, r, _ = diff_lines(prev_changed[k][v], v, PATH[k])
        cls = classify(a, r)
        return cls if cls else BRIEF[k](v)

    def is_semantic(v):
        """A release is 'semantic' if at least one changed layer is non-cosmetic.
        Written as a machine-readable marker at the top of each per-version file so
        scripts/keycodes_migration.py can skip cosmetic-only releases cheaply."""
        return any(classify(*diff_lines(prev_changed[k][v], v, PATH[k])[:2]) is None
                   for k in PATH if v in change_at[k])

    def emit_diff(w, k, v):
        prev = prev_changed[k][v]
        pdate, psha = meta(prev)
        a, r, d = diff_lines(prev, v, PATH[k])
        cls = classify(a, r)
        tag = f"  ·  *{cls}*" if cls else ""
        w(f"**{LABEL[k]}** (diff vs `{prev}`, {pdate})  ·  +{len(a)} added / −{len(r)} removed{tag}")
        b = BRIEF[k](v)
        if cls:
            w(f"> *No semantic keycode change ({cls}).*")
        elif b:
            w(f"> {b}")
        lines = d.splitlines()
        w("```diff")
        if len(lines) > DIFF_CAP:
            w("\n".join(lines[:DIFF_CAP]))
            w(f"...  /* {len(lines)-DIFF_CAP} more diff lines omitted (see `git diff {prev} {v} -- {PATH[k]}`) */")
        else:
            w(d.rstrip())
        w("```")
        w("")

    def esc(s):
        return s.replace("|", "\\|")

    # ============================ EMIT ============================
    gdate = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")
    latest = tags[-1]

    # ---------- per-version files ----------
    def emit_version_file(v):
        date, sha = meta(v)
        semantic = is_semantic(v)
        L = []
        w = L.append
        # Machine-readable marker consumed by scripts/keycodes_migration.py.
        w(f"<!-- qmk-keycodes: version={v} semantic={'true' if semantic else 'false'} -->")
        w("")
        w(f"# `{v}` — keycode changes")
        w("")
        w(f"<sub>{date} · commit `{sha}`</sub>")
        w("")
        w(f"> One release in the QMK keycode migration catalog "
          f"(`references/19-keycodes-changelog.md`). Apply the entries below only if "
          f"your migration window `(from, to]` includes `{v}`.")
        w(">")
        w("> **Change-kind legend:** `deprecated OLD→NEW` → rename to **NEW** now "
          "(OLD still compiles via `quantum_keycodes_legacy.h`); `retired OLD` → replace "
          "with the **NEW** named where it was *deprecated* (OLD no longer compiles); "
          "`removed` → delete/substitute (no replacement); `added` → informational, "
          "not a migration requirement.")
        w("")
        briefs = [summary_brief(k, v) for k in ("kc", "qk", "leg", "lay") if v in change_at[k]]
        if briefs:
            w(f"**Summary:** {esc('; '.join(briefs))}")
            w("")
        if not semantic:
            w("> ⚠️ **No semantic keycode changes in this release** — every changed layer "
              "is copyright/whitespace only. There is nothing to migrate here; this file "
              "exists only so the catalog is complete.")
            w("")
        w("---")
        w("")
        for k, _, _, _ in FILES:
            if v in change_at[k]:
                emit_diff(w, k, v)
        return "\n".join(L).rstrip() + "\n"

    # ---------- index block (regenerated between sentinels) ----------
    def build_index_block():
        B = []
        w = B.append
        w(f"- **Source repo:** [{repo_id}](https://github.com/{repo_id})")
        w(f"- **Scope:** scanned `{BASELINE}` → **`{latest}`** ({len(tags)} release tags). "
          f"**{len(all_versions)}** of those releases changed at least one keycode layer "
          f"(newest cataloged: `{all_versions[-1]}` — `keycodes_migration.py --to latest` "
          f"resolves to it).")
        w(f"- **Generated:** UTC `{gdate}`.")
        w("")
        w("## Per-layer change coverage (cross-check)")
        w("")
        w("| Layer | File(s) | Versions changed |")
        w("|-------|---------|------------------|")
        for k, _, lbl, h in FILES:
            w(f"| {h} | `{PATH[k]}` | {len(change_at[k])} |")
        w(f"| **union (this catalog)** | — | **{len(all_versions)}** |")
        w("")
        w("## Version index — one file per release")
        w("")
        w("Each release's full changeset is its own file under "
          f"[`keycodes-changelog/`](keycodes-changelog/) (named `<version>.md`, e.g. "
          f"[`0.25.0.md`](keycodes-changelog/0.25.0.md)). **Load only the versions in your "
          f"migration window** `(from, to]` — do not read them all. To dump a whole window "
          f"as one document instead of opening each file, use the tool below.")
        w("")
        hdr = ("| Version | Date | " + " | ".join(f"`{HDR[k]}`" for k in ("kc", "qk", "leg", "lay"))
               + " | What changed | File |")
        sep = ("|---------|------|" + "|".join(["-" * len(HDR[k].strip('`'))] * 4)
               + "|--------------|------|")
        w(hdr)
        w(sep)
        for v in all_versions:
            date, _sha = meta(v)
            briefs = [summary_brief(k, v) for k in ("kc", "qk", "leg", "lay") if v in change_at[k]]
            brief = esc("; ".join(briefs))
            w(f"| `{v}` | {date} | {cell('kc', v)} | {cell('qk', v)} | {cell('leg', v)} | "
              f"{cell('lay', v)} | {brief} | [`{v}.md`](keycodes-changelog/{v}.md) |")
        w("")
        w("### Migration-window tool — `scripts/keycodes_migration.py`")
        w("")
        w("Given `--from` and `--to`, prints every release changeset in the half-open "
          "interval `(from, to]` as one document (cosmetic-only releases are skipped by default):")
        w("")
        w("```")
        w("# Everything that changed between two versions, as one dump:")
        w("scripts/keycodes_migration.py --from 0.22.0 --to 0.30.0")
        w("# From a version up to the newest cataloged release (--to defaults to latest):")
        w("scripts/keycodes_migration.py --from 0.25.0")
        w("# Just list which release files fall in the window:")
        w("scripts/keycodes_migration.py --from 0.22.0 --to 0.30.0 --list")
        w("# Keep copyright/whitespace-only releases too (skipped by default):")
        w("scripts/keycodes_migration.py --from 0.22.0 --include-cosmetic")
        w("```")
        return "\n".join(B)

    # ---------- write per-version files ----------
    os.makedirs(split_dir, exist_ok=True)
    keep = {f"{v}.md" for v in all_versions}
    for fn in os.listdir(split_dir):
        if fn.endswith(".md") and fn not in keep:
            os.remove(os.path.join(split_dir, fn))
    for v in all_versions:
        with open(os.path.join(split_dir, f"{v}.md"), "w", encoding="utf-8") as f:
            f.write(emit_version_file(v))

    # ---------- update the index in place ----------
    update_index_file(out_path, build_index_block())

    print(f"Updated index {out_path} (in place, between GENERATED INDEX sentinels)")
    print(f"Wrote {len(all_versions)} per-version files to {split_dir}/")
    print("Per-layer diff blocks:",
          ", ".join(f"{HDR[k]}={len(change_at[k])}" for k in ('kc', 'qk', 'leg', 'lay')))

def derive_split_dir(out_path):
    """Default per-version dir: sibling of the index named after its stem minus a
    leading 'NN-' prefix.  references/19-keycodes-changelog.md -> references/keycodes-changelog/"""
    d = os.path.dirname(os.path.abspath(out_path))
    stem = os.path.splitext(os.path.basename(out_path))[0]
    name = re.sub(r"^\d+-", "", stem) or stem
    return os.path.join(d, name)

def main():
    ap = argparse.ArgumentParser(
        description="Generate the per-release keycode-change catalog from a qmk_firmware checkout.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="The index (OUTPUT) is updated in place between GENERATED INDEX sentinels; "
               "one file per release is written under the split dir (default: derived from OUTPUT).")
    ap.add_argument("qmk_path", help="Relative or absolute path to the qmk_firmware project on disk")
    ap.add_argument("-o", "--output", default="keycodes_changelog.md",
                    help="Index file to update in place (default: ./keycodes_changelog.md)")
    ap.add_argument("--split-dir", default=None,
                    help="Directory for per-version files (default: derived from --output)")
    args = ap.parse_args()

    global QMK
    QMK = os.path.abspath(os.path.expanduser(args.qmk_path))
    if not os.path.isdir(QMK):
        sys.exit(f"error: not a directory: {QMK}")
    if subprocess.run(["git", "-C", QMK, "rev-parse", "--is-inside-work-tree"],
                      capture_output=True).returncode != 0:
        sys.exit(f"error: not a git work tree: {QMK}")
    if not ok("git", "cat-file", "-e", "HEAD:quantum/keycodes.h"):
        sys.exit(f"error: quantum/keycodes.h not found at HEAD — is this qmk_firmware?: {QMK}")

    tags = get_tags()
    build(tags, args.output, args.split_dir or derive_split_dir(args.output))

if __name__ == "__main__":
    main()