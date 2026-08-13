#!/usr/bin/env python3
from __future__ import annotations
import ast
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Inspector(HTMLParser):
    def __init__(self): super().__init__(); self.ids=set(); self.links=[]; self.title=False; self.cards=0; self.card_links=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if "id" in values:self.ids.add(values["id"])
        if tag=="a" and "href" in values:self.links.append(values["href"])
        if tag=="title":self.title=True
        if "card" in values.get("class","").split():self.cards+=1; self.card_links.append(values.get("href",""))
def main():
    site=ROOT/"site"; parser=Inspector(); parser.feed((site/"index.html").read_text())
    detail=Inspector(); detail.feed((site/"projects.html").read_text())
    flow=Inspector(); flow.feed((site/"flowcharts.html").read_text())
    flow_source=(site/"flowcharts.js").read_text()
    references=re.findall(r'S\("[^"]+","(ailab/[^"]+#[^"]+)"',flow_source)
    def source_exists(reference):
        filename,symbol=reference.split("#",1); path=ROOT/filename
        if not path.is_file(): return False
        tree=ast.parse(path.read_text()); parts=symbol.split(".")
        parent=next((node for node in tree.body if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==parts[0]),None)
        if parent is None: return False
        return len(parts)==1 or isinstance(parent,ast.ClassDef) and any(isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==parts[1] for node in parent.body)
    expected={f"project-{number:02d}" for number in range(1,21)}
    checks={"html_exists":(site/"index.html").is_file(),"css_exists":(site/"styles.css").is_file(),"nojekyll_exists":(site/".nojekyll").is_file(),"title_present":parser.title,"all_20_projects":parser.cards==20,"all_cards_are_links":set(parser.card_links)=={f"projects.html#{item}" for item in expected},"all_detail_targets_exist":expected.issubset(detail.ids),"navigation_targets":{"projects","controls","run","learn"}.issubset(parser.ids),"flow_atlas_linked_first":parser.links.index("flowcharts.html") < parser.links.index("#projects"),"flow_assets_exist":all((site/name).is_file() for name in ("flowcharts.html","flowcharts.css","flowcharts-mobile.css","flowcharts.js","homepage.css")),"flow_has_20_projects":len(re.findall(r'^P\(',flow_source,re.MULTILINE))==20,"flow_has_120_stages":len(references)==120,"all_flow_sources_resolve":len(references)==120 and all(source_exists(ref) for ref in references),"github_links":any("github.com/abhi32dev/ai-infrastructure-platform-1" in link for link in parser.links),"workflow_exists":(ROOT/".github/workflows/pages.yml").is_file()}
    passed=sum(checks.values()); report={"generated_at":datetime.now(timezone.utc).isoformat(),"summary":{"total":len(checks),"passed":passed,"failed":len(checks)-passed},"checks":checks}; target=ROOT/"artifacts/github-pages"; target.mkdir(parents=True,exist_ok=True); (target/"latest.json").write_text(json.dumps(report,indent=2)+"\n"); (target/"latest.txt").write_text(f"GitHub Pages verification: {passed}/{len(checks)} passed\n"); print(f"GitHub Pages verification: {passed}/{len(checks)} passed"); return int(passed!=len(checks))
if __name__=="__main__":raise SystemExit(main())
