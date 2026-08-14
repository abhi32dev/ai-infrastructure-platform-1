#!/usr/bin/env python3
"""Verify all production guides contain reviewed answers and resolvable code evidence."""
from __future__ import annotations
import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from discussion_answers import ANSWERS, QUESTIONS

ROOT=Path(__file__).resolve().parents[1]

LEGACY_ANSWER_COUNTS={
 "docs/milestone-1.md":10,
 "docs/project-2-agent-runtime.md":9,
 "docs/project-3-model-gateway.md":8,
 "docs/project-4-evaluation-gate.md":6,
}

LEGACY_PROD_LINKS={
 "docs/milestone-1.md":"projects/project-01-rag/PROD.md",
 "docs/project-2-agent-runtime.md":"projects/project-02-agent-runtime/PROD.md",
 "docs/project-3-model-gateway.md":"projects/project-03-model-gateway/PROD.md",
 "docs/project-4-evaluation-gate.md":"projects/project-04-evaluation/PROD.md",
 "docs/project-5-inference-serving.md":"projects/project-05-inference-serving/PROD.md",
 "docs/project-6-streaming-features.md":"projects/project-06-streaming-features/PROD.md",
 "docs/project-7-recommendations.md":"projects/project-07-recommendations/PROD.md",
 "docs/project-8-self-healing-batch.md":"projects/project-08-batch-platform/PROD.md",
 "docs/project-9-golden-path.md":"projects/project-09-golden-path/PROD.md",
 "docs/project-10-observability.md":"projects/project-10-observability/PROD.md",
 "docs/project-11-security-guardrails.md":"projects/project-11-security/PROD.md",
 "docs/project-12-ml-cv-lifecycle.md":"projects/project-12-ml-cv/PROD.md",
 "docs/protocols-mcp-a2a.md":"projects/project-13-protocols/PROD.md",
}

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
 legacy=[]
 for filename,target in LEGACY_PROD_LINKS.items():
  path=ROOT/filename; text=path.read_text() if path.is_file() else ""
  expected=LEGACY_ANSWER_COUNTS.get(filename)
  checks={
   "prod_guide_exists":(ROOT/target).is_file(),
   "prod_guide_linked":target.split("/",1)[1] in text,
   "inline_answers_complete":expected is None or text.count("**Answer.**")==expected,
  }
  legacy.append({"document":filename,"status":"passed" if all(checks.values()) else "failed","checks":checks})
 legacy_passed=sum(item["status"]=="passed" for item in legacy)
 report={"generated_at":datetime.now(timezone.utc).isoformat(),"summary":{"total":len(results),"passed":passed,"failed":len(results)-passed,"answers":sum(len(v) for v in ANSWERS.values()),"legacy_tutorials":len(legacy),"legacy_tutorials_passed":legacy_passed,"legacy_inline_answers":sum(LEGACY_ANSWER_COUNTS.values())},"projects":results,"legacy_tutorials":legacy}
 target=ROOT/"artifacts/production-guides";target.mkdir(parents=True,exist_ok=True)
 (target/"latest.json").write_text(json.dumps(report,indent=2)+"\n")
 (target/"latest.txt").write_text(f"Production guide verification: {passed}/{len(results)} projects, {report['summary']['answers']} answers; legacy tutorials: {legacy_passed}/{len(legacy)}, {report['summary']['legacy_inline_answers']} inline answers\n")
 print((target/"latest.txt").read_text().strip())
 return int(passed!=len(results) or legacy_passed!=len(legacy))

if __name__=="__main__":raise SystemExit(main())
