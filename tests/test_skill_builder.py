import io, os, sys, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skill_builder import slugify, build_skill_md, validate_skill_md, make_skill_zip, repair_skill_md
from samples import SAMPLE_EXTRACTIONS

def run():
    assert slugify("Pour Over Coffee!") == "pour-over-coffee"
    for name, x in SAMPLE_EXTRACTIONS.items():
        folder, zip_bytes, md = make_skill_zip(x)
        names = zipfile.ZipFile(io.BytesIO(zip_bytes)).namelist()
        assert f"{folder}/SKILL.md" in names and f"{folder}/references/source-notes.md" in names, names
        v = validate_skill_md(md, folder_name=folder)
        print(f"{name}\n  folder={folder} zip={len(zip_bytes)}B files={len(names)} validator={v['score']}/{v['total']} passed={v['passed']}")
        assert v["passed"]
    # validator must CATCH a bad skill, repair must FIX it
    bad_md = "# My Cool Trick\n- first do this\n- then do that\n- finish it"
    assert not validate_skill_md(bad_md)["passed"]
    fixed = repair_skill_md(bad_md)
    import re as _r; nm = _r.search(r"^name:\s*(\S+)", fixed, flags=_r.MULTILINE).group(1)
    vf = validate_skill_md(fixed, folder_name=nm)
    print(f"Fix-My-Skill: bad -> repaired validator={vf['score']}/{vf['total']} passed={vf['passed']}")
    assert vf["passed"] and "first do this" in fixed
    print("ALL SNAP2SKILL TESTS PASSED")

if __name__ == "__main__":
    run()
