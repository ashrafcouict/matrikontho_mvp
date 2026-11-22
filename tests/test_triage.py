from modules.triage_engine import assess
def ext(names, severity="unknown", uncertainty=None):
    return {"symptoms":[{"name":n,"present":True,"severity":severity} for n in names],
            "uncertainty":uncertainty or [],"pregnancy_status":"pregnant","missing_information":[]}
def test_bleeding_high(): assert assess(ext(["vaginal_bleeding"]))["risk_level"]=="HIGH"
def test_seizure_high(): assert assess(ext(["convulsions"]))["risk_level"]=="HIGH"
def test_headache_blurred_high(): assert assess(ext(["headache","blurred_vision"]))["risk_level"]=="HIGH"
def test_reduced_movement_high(): assert assess(ext(["reduced_fetal_movement"]))["risk_level"]=="HIGH"
def test_severe_pain_high(): assert assess(ext(["abdominal_pain"],"severe"))["risk_level"]=="HIGH"
def test_severe_breathing_high(): assert assess(ext(["breathing_difficulty"],"severe"))["risk_level"]=="HIGH"
def test_fever_weakness_high(): assert assess(ext(["fever","severe_weakness"]))["risk_level"]=="HIGH"
def test_swelling_medium(): assert assess(ext(["facial_hand_swelling"]))["risk_level"]=="MEDIUM"
def test_empty_incomplete(): assert assess(ext([]))["risk_level"]=="INCOMPLETE"
def test_uncertainty_does_not_erase_known_concern(): assert assess(ext(["headache"],uncertainty=["ASR unclear"]))["risk_level"]=="MEDIUM"
