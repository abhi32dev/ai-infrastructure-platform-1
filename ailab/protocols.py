from __future__ import annotations
import json,sqlite3,time,uuid
from dataclasses import asdict,dataclass,field
from pathlib import Path
from typing import Any,Callable
from .observability import Telemetry
from .security_guardrails import GuardrailGateway,Principal

class ProtocolError(RuntimeError):
 def __init__(self,code:int,message:str,data:Any=None):super().__init__(message);self.code=code;self.message=message;self.data=data
 def response(self,id):return {"jsonrpc":"2.0","id":id,"error":{"code":self.code,"message":self.message,"data":self.data}}
@dataclass(frozen=True)
class MCPTool:name:str;description:str;input_schema:dict;handler:Callable[[dict],Any];risk:str="low"
@dataclass(frozen=True)
class MCPResource:uri:str;name:str;mime_type:str;reader:Callable[[],str]
@dataclass(frozen=True)
class MCPPrompt:name:str;description:str;arguments:tuple[str,...];renderer:Callable[[dict],list[dict]]

class MCPServer:
 REVISION="2025-06-18"
 def __init__(self,security:GuardrailGateway,telemetry:Telemetry,principal:Principal):self.security=security;self.telemetry=telemetry;self.principal=principal;self.tools={};self.resources={};self.prompts={};self.initialized=False;self.cancelled=set()
 def tool(self,spec:MCPTool):self.tools[spec.name]=spec
 def resource(self,spec:MCPResource):self.resources[spec.uri]=spec
 def prompt(self,spec:MCPPrompt):self.prompts[spec.name]=spec
 def handle(self,request:dict)->dict|None:
  id=request.get("id");method=request.get("method","");params=request.get("params",{})
  if request.get("jsonrpc")!="2.0":return ProtocolError(-32600,"Invalid Request").response(id)
  try:
   with self.telemetry.span(f"mcp.{method}",protocol="mcp",method=method) as span:
    if method=="initialize":result=self._initialize(params)
    elif method=="notifications/initialized":self.initialized=True;return None
    elif method=="notifications/cancelled":self.cancelled.add(params.get("requestId"));return None
    else:
     if not self.initialized:raise ProtocolError(-32002,"Server not initialized")
     result=self._dispatch(method,params,id)
    self.telemetry.log("INFO","mcp request completed",span["trace_id"],method=method)
    return {"jsonrpc":"2.0","id":id,"result":result}
  except ProtocolError as exc:return exc.response(id)
  except Exception as exc:return ProtocolError(-32603,"Internal error",str(exc)).response(id)
 def _initialize(self,p):
  if p.get("protocolVersion")!=self.REVISION:raise ProtocolError(-32602,"Unsupported protocol version",{"supported":[self.REVISION]})
  return {"protocolVersion":self.REVISION,"capabilities":{"tools":{"listChanged":False},"resources":{"subscribe":False},"prompts":{"listChanged":False},"logging":{}},"serverInfo":{"name":"ai-infrastructure-lab","version":"1.0"}}
 def _dispatch(self,m,p,id):
  if id in self.cancelled:raise ProtocolError(-32800,"Request cancelled")
  if m=="tools/list":return {"tools":[{"name":x.name,"description":x.description,"inputSchema":x.input_schema} for x in self.tools.values()]}
  if m=="resources/list":return {"resources":[{"uri":x.uri,"name":x.name,"mimeType":x.mime_type} for x in self.resources.values()]}
  if m=="prompts/list":return {"prompts":[{"name":x.name,"description":x.description,"arguments":[{"name":a,"required":True} for a in x.arguments]} for x in self.prompts.values()]}
  if m=="resources/read":
   uri=p.get("uri");resource=self.resources.get(uri)
   if not resource:raise ProtocolError(-32002,"Resource not found")
   self.security.enforce(self.principal,"retrieve",self.principal.tenant,uri);return {"contents":[{"uri":uri,"mimeType":resource.mime_type,"text":resource.reader()}]}
  if m=="prompts/get":
   prompt=self.prompts.get(p.get("name"))
   if not prompt:raise ProtocolError(-32602,"Unknown prompt")
   missing=set(prompt.arguments)-p.get("arguments",{}).keys()
   if missing:raise ProtocolError(-32602,"Missing prompt arguments",sorted(missing))
   return {"description":prompt.description,"messages":prompt.renderer(p["arguments"])}
  if m=="tools/call":
   tool=self.tools.get(p.get("name"))
   if not tool:raise ProtocolError(-32602,"Unknown tool")
   arguments=p.get("arguments",{});required=set(tool.input_schema.get("required",[]));missing=required-arguments.keys()
   if missing:raise ProtocolError(-32602,"Invalid tool arguments",sorted(missing))
   decision=self.security.input_guard(json.dumps(arguments))
   if not decision.allowed:raise ProtocolError(-32001,"Guardrail blocked tool input",asdict(decision))
   self.security.enforce(self.principal,"tool:write" if tool.risk=="high" else "tool:read",self.principal.tenant,tool.name,tool.risk)
   started=time.perf_counter();value=tool.handler(arguments);self.telemetry.request("mcp",True,(time.perf_counter()-started)*1000,cost=.00001,model="tool",tenant=self.principal.tenant);return {"content":[{"type":"text","text":json.dumps(value)}],"isError":False}
  raise ProtocolError(-32601,"Method not found")

@dataclass(frozen=True)
class AgentSkill:id:str;name:str;description:str;tags:tuple[str,...];input_modes:tuple[str,...]=("text/plain",);output_modes:tuple[str,...]=("application/json",)
@dataclass(frozen=True)
class AgentCard:name:str;description:str;url:str;version:str;protocol_version:str;skills:tuple[AgentSkill,...];streaming:bool=False
class A2AServer:
 VERSION="1.0"
 STATES={"submitted","working","input-required","completed","failed","canceled","rejected"}
 def __init__(self,path:Path,card:AgentCard,handler:Callable[[dict],dict],security:GuardrailGateway,telemetry:Telemetry,principal:Principal):
  path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row;self.card=card;self.handler=handler;self.security=security;self.telemetry=telemetry;self.principal=principal;self.db.executescript("CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,context_id TEXT,state TEXT,messages TEXT,artifacts TEXT,metadata TEXT,created_at REAL,updated_at REAL);");self.db.commit()
 def agent_card(self)->dict:
  return {"name":self.card.name,"description":self.card.description,"version":self.card.version,"supportedInterfaces":[{"url":self.card.url,"protocolBinding":"HTTP+JSON","protocolVersion":self.card.protocol_version}],"capabilities":{"streaming":self.card.streaming},"defaultInputModes":["text/plain"],"defaultOutputModes":["application/json"],"skills":[asdict(x) for x in self.card.skills]}
 def send_message(self,message:dict,version="1.0",context_id=None)->dict:
  if version!=self.VERSION:raise ProtocolError(-32009,"VersionNotSupportedError",{"supported":[self.VERSION]})
  parts=message.get("parts",[])
  if message.get("role")!="user" or not parts:raise ProtocolError(-32602,"invalid message")
  text=" ".join(p.get("text","") for p in parts if p.get("type")=="text");guard=self.security.input_guard(text)
  if not guard.allowed:raise ProtocolError(-32001,"message blocked",asdict(guard))
  self.security.enforce(self.principal,"infer",self.principal.tenant,"a2a-task");task_id=uuid.uuid4().hex;now=time.time();self.db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?)",(task_id,context_id or uuid.uuid4().hex,"working",json.dumps([message]),json.dumps([]),json.dumps({}),now,now));self.db.commit()
  if message.get("metadata",{}).get("defer"):
   self.db.execute("UPDATE tasks SET state='submitted',updated_at=? WHERE id=?",(time.time(),task_id));self.db.commit();return self.get_task(task_id)
  with self.telemetry.span("a2a.send_message",protocol="a2a",task_id=task_id):
   started=time.perf_counter()
   try:artifact=self.handler({"text":guard.redacted or text,"task_id":task_id});state="completed";artifacts=[{"artifactId":uuid.uuid4().hex,"name":"result","parts":[{"type":"data","data":artifact}],"lastChunk":True}]
   except Exception as exc:state="failed";artifacts=[{"artifactId":uuid.uuid4().hex,"name":"error","parts":[{"type":"text","text":str(exc)}],"lastChunk":True}]
   self.telemetry.request("a2a",state=="completed",(time.perf_counter()-started)*1000,cost=.0001,model="remote-agent",tenant=self.principal.tenant)
  self.db.execute("UPDATE tasks SET state=?,artifacts=?,updated_at=? WHERE id=?",(state,json.dumps(artifacts),time.time(),task_id));self.db.commit();return self.get_task(task_id)
 def get_task(self,id):
  row=self.db.execute("SELECT * FROM tasks WHERE id=?",(id,)).fetchone()
  if not row:raise ProtocolError(-32001,"TaskNotFoundError")
  return {"id":row["id"],"contextId":row["context_id"],"status":{"state":row["state"]},"history":json.loads(row["messages"]),"artifacts":json.loads(row["artifacts"]),"metadata":json.loads(row["metadata"])}
 def list_tasks(self):return [self.get_task(row[0]) for row in self.db.execute("SELECT id FROM tasks ORDER BY created_at")]
 def cancel_task(self,id):
  task=self.get_task(id)
  if task["status"]["state"] in {"completed","failed","canceled","rejected"}:raise ProtocolError(-32002,"TaskNotCancelableError")
  self.db.execute("UPDATE tasks SET state='canceled',updated_at=? WHERE id=?",(time.time(),id));self.db.commit();return self.get_task(id)
