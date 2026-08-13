import argparse,json,tempfile
from pathlib import Path
from .observability import Telemetry
from .protocols import *
from .security_guardrails import GuardrailGateway,Principal
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--data",type=Path,default=Path("data/protocols"));a=p.parse_args(argv);a.data.mkdir(parents=True,exist_ok=True);security=GuardrailGateway(a.data/"security.db",quota=100);telemetry=Telemetry(a.data/"telemetry.db");principal=Principal("demo-agent","tenant-a",("operator",));mcp=MCPServer(security,telemetry,principal);mcp.tool(MCPTool("lookup","lookup item",{"type":"object","required":["id"]},lambda x:{"id":x["id"],"status":"healthy"}));init=mcp.handle({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":MCPServer.REVISION}});mcp.handle({"jsonrpc":"2.0","method":"notifications/initialized"});tool=mcp.handle({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"lookup","arguments":{"id":"node-1"}}});card=AgentCard("ops-agent","operations", "https://localhost/a2a","1.0","1.0",(AgentSkill("health","Health","Check health",("operations",)),));a2a=A2AServer(a.data/"a2a.db",card,lambda x:{"summary":x["text"]},security,telemetry,principal);task=a2a.send_message({"role":"user","parts":[{"type":"text","text":"inspect platform"}]});print(json.dumps({"mcp_initialize":init,"mcp_tool":tool,"agent_card":a2a.agent_card(),"a2a_task":task,"costs":telemetry.cost_breakdown()},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
