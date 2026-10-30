from app.services.delivery_service import _TRANSITIONS


def test_delivery_transition_graph_does_not_allow_skipping_steps():
    assert _TRANSITIONS['PLANNED'] == {'ASSIGNED', 'CANCELLED'}
    assert 'DELIVERED' not in _TRANSITIONS['PLANNED']
    assert _TRANSITIONS['OUT_FOR_DELIVERY'] == {'DELIVERED', 'FAILED'}
    assert _TRANSITIONS['DELIVERED'] == set()
