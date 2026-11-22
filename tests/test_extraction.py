from modules.conversation import fallback_extract
def test_headache_detected():
    x=fallback_extract("আমার মাথা ব্যথা করছে","pregnant",20)
    assert any(s["name"]=="headache" and s["present"] for s in x["symptoms"])
def test_unmentioned_not_added():
    x=fallback_extract("আমি ভালো আছি")
    assert x["symptoms"]==[]
