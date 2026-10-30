from scripts.run_phase_acceptance_demo import run


def test_phase_acceptance_demo_is_explicitly_simulated_and_reconciles_values():
    report = run()

    assert report["status"] == "PASS"
    assert report["data_mode"] == "SIMULATED"
    assert report["batch"]["status"] == "COMPLETED"
    assert report["supplier_invoice"]["match_status"] == "MATCHED"
    assert report["delivery"]["status_path"][-1] == "DELIVERED"
    assert report["live_gates"]["supabase_extension_migrations"] == "PENDING_BACKUP_GATE"
