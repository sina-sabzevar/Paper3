import importlib.util as u, json, io, sys, pathlib
CELLS = []
def md(s): CELLS.append(("markdown", s.strip("\n")))
def co(s): CELLS.append(("code", s.strip("\n")))

# part 1 appends directly; parts 2-6 expose add(md, co)
spec = u.spec_from_file_location("p1", "build_cells_1.py"); p1 = u.module_from_spec(spec)
spec.loader.exec_module(p1); CELLS.extend(p1.CELLS)
for n in range(2, 7):
    spec = u.spec_from_file_location(f"p{n}", f"build_cells_{n}.py")
    m = u.module_from_spec(spec); spec.loader.exec_module(m); m.add(md, co)

code_cells = [s for t, s in CELLS if t == "code"]
pathlib.Path("verify.py").write_text(
    "# generated from the notebook cells - run to prove they execute\n" +
    "\n\n# ---- CELL ----\n".join(code_cells) + "\n")

nb = {"cells": [], "metadata": {"kernelspec": {"display_name": "Python 3",
      "language": "python", "name": "python3"},
      "language_info": {"name": "python", "version": "3.11"}},
      "nbformat": 4, "nbformat_minor": 5}
for t, s in CELLS:
    lines = s.split("\n")
    src = [l + "\n" for l in lines[:-1]] + [lines[-1]]
    cell = {"cell_type": t, "metadata": {}, "source": src}
    if t == "code": cell |= {"execution_count": None, "outputs": []}
    nb["cells"].append(cell)
pathlib.Path("telco_credit_model.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False))
print(f"{len(CELLS)} cells  ({len(code_cells)} code, {len(CELLS)-len(code_cells)} markdown)")
