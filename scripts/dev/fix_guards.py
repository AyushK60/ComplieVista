import ast

p = "backend/tests/test_m4_execution.py"
lines = open(p, encoding="utf-8").read().splitlines(keepends=True)
out = []
Q = '"'
APOS = "'"
BSN = chr(92) + "n"
skip = 0
for l in lines:
    if skip > 0:
        skip -= 1
        continue
    if "SPAWNED" in l and l.rstrip().endswith(Q + ")"):
        out.append(f"                {Q}print({APOS}SPAWNED{APOS}, spawned){BSN}{Q}" + "\n")
        out.append(f"                {Q}if __name__ == {APOS}__main__{APOS}:{BSN}{Q}" + "\n")
        out.append(f"                {Q}    run(){BSN}{Q})" + "\n")
        continue
    if '"content": "v = 7' in l:
        out.append(f'        {Q}content{Q}: {Q}if __name__ == {APOS}__main__{APOS}:{BSN}    v = 7{BSN}    print(v){BSN}{Q}}}).json()' + "\n")
        continue
    if '"for i in range(5):' in l and "pg.py" in "".join(out[-6:]):
        out.append(f'                {Q}if __name__ == {APOS}__main__{APOS}:{BSN}{Q}' + "\n")
        out.append(f'                {Q}for i in range(5):{BSN}    print(i){BSN}{Q})' + "\n")
        continue
    out.append(l)
open(p, "w", encoding="utf-8", newline="\n").write("".join(out))
ast.parse("".join(out))
print("fixed")
