import argparse,json
from pathlib import Path
from .security_guardrails import *
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--db",type=Path,default=Path("data/security.db"));a=p.parse_args(argv);g=GuardrailGateway(a.db);operator=Principal("demo","tenant-a",("operator",));token=g.issue(operator);principal=g.authenticate(token);g.add_document(principal,"doc-1","tenant-a","internal","AI platform reliability");print(json.dumps({"input":g.input_guard("Contact user@example.com").__dict__,"retrieval":g.retrieve(principal,"reliability"),"audit_valid":g.verify_audit_chain()},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
