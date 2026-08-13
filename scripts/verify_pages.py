#!/usr/bin/env python3
from __future__ import annotations
import json
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
    expected={f"project-{number:02d}" for number in range(1,14)}
    checks={"html_exists":(site/"index.html").is_file(),"css_exists":(site/"styles.css").is_file(),"nojekyll_exists":(site/".nojekyll").is_file(),"title_present":parser.title,"all_13_projects":parser.cards==13,"all_cards_are_links":set(parser.card_links)=={f"projects.html#{item}" for item in expected},"all_detail_targets_exist":expected.issubset(detail.ids),"navigation_targets":{"projects","controls","run"}.issubset(parser.ids),"github_links":any("github.com/abhi32dev/ai-infrastructure-platform-1" in link for link in parser.links),"workflow_exists":(ROOT/".github/workflows/pages.yml").is_file()}
    passed=sum(checks.values()); report={"generated_at":datetime.now(timezone.utc).isoformat(),"summary":{"total":len(checks),"passed":passed,"failed":len(checks)-passed},"checks":checks}; target=ROOT/"artifacts/github-pages"; target.mkdir(parents=True,exist_ok=True); (target/"latest.json").write_text(json.dumps(report,indent=2)+"\n"); (target/"latest.txt").write_text(f"GitHub Pages verification: {passed}/{len(checks)} passed\n"); print(f"GitHub Pages verification: {passed}/{len(checks)} passed"); return int(passed!=len(checks))
if __name__=="__main__":raise SystemExit(main())
