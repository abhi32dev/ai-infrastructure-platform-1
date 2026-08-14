#!/usr/bin/env python3
"""Verify all production guides contain reviewed answers and resolvable code evidence."""
from __future__ import annotations
import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from discussion_answers import ANSWERS, QUESTIONS

ROOT=Path(__file__).resolve().parents[1]

def symbol_exists(filename: str, symbol: str) -> bool:
 path=ROOT/filename
 if not path.is_file(): return False
 tree=ast.parse(path.read_text()); parts=symbol.split(".")
 node=next((item for item in tree.body if isinstance(item,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and item.name==parts[0]),None)
 if node is None: return False
 return len(parts)==1 or isinstance(node,ast.ClassDef) and any(isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)) and item.name==parts[1] for item in node.body)

def main() -> int:
 results=[]
 for directory,entries in ANSWERS.items():
  path=ROOT/"projects"/directory/"PROD.md"; text=path.read_text() if path.is_file() else ""
  references=[(filename,symbol) for _,filename,symbol in entries]
  checks={
   "seven_answers":len(entries)==7 and text.count("**Staff/Principal answer.**")==7,
   "seven_evidence_blocks":text.count("**Implementation evidence.**")==7 and text.count("```python")==7,
   "all_questions_present":all(f"### {number}. {question}" in text for number,question in enumerate(QUESTIONS,1)),
   "all_symbols_resolve":all(symbol_exists(filename,symbol) for filename,symbol in references),
   "all_source_links_present":all(f"../../{filename}" in text and f"`{filename} · {symbol}`" in text for filename,symbol in references),
  }
  results.append({"project":directory,"status":"passed" if all(checks.values()) else "failed","checks":checks})
 passed=sum(item["status"]=="passed" for item in results)
 report={"generated_at":datetime.now(timezone.utc).isoformat(),"summary":{"total":len(results),"passed":passed,"failed":len(results)-passed,"answers":sum(len(v) for v in ANSWERS.values())},"projects":results}
 target=ROOT/"artifacts/production-guides";target.mkdir(parents=True,exist_ok=True)
 (target/"latest.json").write_text(json.dumps(report,indent=2)+"\n")
 (target/"latest.txt").write_text(f"Production guide verification: {passed}/{len(results)} projects, {report['summary']['answers']} answers\n")
 print((target/"latest.txt").read_text().strip())
 return int(passed!=len(results))

if __name__=="__main__":raise SystemExit(main())
