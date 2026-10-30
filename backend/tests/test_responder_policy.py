from app.responder_policy import authorize_action

def test_unknown_action_is_denied():
    result = authorize_action("arbitrary_shell", evidence_complete=True,
                              production=False, human_approved=False)
    assert result.allowed is False

def test_missing_evidence_is_denied():
    result = authorize_action("restart_demo_api", evidence_complete=False,
                              production=False, human_approved=False)
    assert result.allowed is False

def test_production_action_requires_approval():
    result = authorize_action("restart_demo_api", evidence_complete=True,
                              production=True, human_approved=False)
    assert result.allowed is False

def test_allowlisted_action_can_be_authorized_in_nonproduction():
    result = authorize_action("restart_demo_api", evidence_complete=True,
                              production=False, human_approved=False)
    assert result.allowed is True
