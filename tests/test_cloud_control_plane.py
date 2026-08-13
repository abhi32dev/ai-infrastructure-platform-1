import pytest
from ailab.cloud_control_plane import *
def spec(**changes):return DeploymentSpec(**({"name":"model-api","provider":"aws","region":"us-west-2","instance_type":"cpu-small","replicas":1,"monthly_budget":100}|changes))
@pytest.mark.parametrize("changes",[{"name":""},{"name":"../x"},{"provider":"other"},{"region":""},{"instance_type":""},{"replicas":0},{"monthly_budget":0}])
def test_invalid_spec_matrix(changes):
 with pytest.raises(ValueError):spec(**changes).validate()
@pytest.mark.parametrize("changes",[{"private_network":False},{"encrypted":False},{"replicas":3,"monthly_budget":100}])
def test_policy_violation_matrix(changes):
 with pytest.raises(PolicyViolation):CloudMLControlPlane().plan(spec(**changes))
def test_unknown_instance_type():
 with pytest.raises(ValueError):CloudMLControlPlane().plan(spec(instance_type="unknown"))
@pytest.mark.parametrize("provider",["aws","gcp","azure"])
def test_all_provider_plans(provider):assert CloudMLControlPlane().plan(spec(provider=provider))["estimated_monthly_cost"]==50
def test_apply_idempotency():
 c=CloudMLControlPlane();p=c.plan(spec());assert c.apply(p)=="applied" and c.apply(p)=="unchanged"
def test_tampered_plan_rejected():
 c=CloudMLControlPlane();p=c.plan(spec());p["spec"]["replicas"]=2
 with pytest.raises(PolicyViolation):c.apply(p)
def test_drift_and_reconciliation():
 c=CloudMLControlPlane();c.apply(c.plan(spec()));c.actual["model-api"]["replicas"]=9;r=c.reconcile("model-api");assert r["drifted"] and not c.drift("model-api")["drifted"]
def test_unknown_deployment():
 with pytest.raises(KeyError):CloudMLControlPlane().drift("missing")
def test_failover_changes_region():
 c=CloudMLControlPlane();c.apply(c.plan(spec()));assert c.failover("model-api","us-east-1")["spec"]["region"]=="us-east-1"
def test_empty_failover_region():
 c=CloudMLControlPlane();c.apply(c.plan(spec()))
 with pytest.raises(ValueError):c.failover("model-api","")
