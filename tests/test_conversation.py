from modules.conversation import next_question
def test_followup_for_headache():
    x={"symptoms":[{"name":"headache","present":True}],"gestational_age_weeks":24}
    assert "ঝাপসা" in next_question(x)
