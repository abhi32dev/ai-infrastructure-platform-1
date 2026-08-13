import json
import pytest
from ailab.golden_path import *
def test_generates_complete_valid_service(tmp_path):
 g=GoldenPath();target=g.generate(tmp_path,ServiceConfig("rag-service"));result=g.validate(target);assert result["valid"] and result["files"]>=15
def test_four_environments_isolated(tmp_path):
 target=GoldenPath().generate(tmp_path,ServiceConfig("model-api",port=9000));values=[(target/f"environments/{x}.env").read_text() for x in ("dev","test","stage","prod")];assert len(set(values))==4 and all("PORT=9000" in x for x in values)
def test_rejects_unsafe_name_and_port(tmp_path):
 with pytest.raises(ValueError):GoldenPath().generate(tmp_path,ServiceConfig("Bad Name"))
 with pytest.raises(ValueError):GoldenPath().generate(tmp_path,ServiceConfig("good-name",80))
def test_refuses_overwrite(tmp_path):
 g=GoldenPath();g.generate(tmp_path,ServiceConfig("safe-api"));
 with pytest.raises(ScaffoldError):g.generate(tmp_path,ServiceConfig("safe-api"))
def test_validator_detects_root_container(tmp_path):
 g=GoldenPath();target=g.generate(tmp_path,ServiceConfig("unsafe-api"));(target/"Dockerfile").write_text((target/"Dockerfile").read_text().replace("USER app\n",""));result=g.validate(target);assert not result["valid"] and "container_runs_as_root" in result["violations"]
def test_validator_detects_wildcard_iam(tmp_path):
 g=GoldenPath();target=g.generate(tmp_path,ServiceConfig("unsafe-iam"));policy=json.loads((target/"security/iam-policy.json").read_text());policy["Statement"][0]["Action"]="*";(target/"security/iam-policy.json").write_text(json.dumps(policy));assert "wildcard_iam" in g.validate(target)["violations"]
def test_validator_detects_missing_file(tmp_path):
 g=GoldenPath();target=g.generate(tmp_path,ServiceConfig("broken-api"));(target/"k8s/service.yaml").unlink();assert "k8s/service.yaml" in g.validate(target)["missing"]
