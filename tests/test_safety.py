from modules.triage_engine import assess
def test_emergency_cannot_be_overridden_by_uncertainty():
    x={"symptoms":[{"name":"vaginal_bleeding","present":True}],"uncertainty":["other"],"pregnancy_status":"pregnant"}
    assert assess(x)["risk_level"]=="HIGH"
