"""Static guard for V1.1 PostgreSQL integration fixtures."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def _block(path,name,next_name):
    text=path.read_text(encoding="utf-8"); start=text.index(f"def {name}("); end=text.index(f"\ndef {next_name}(",start); return text[start:end]
def test_pg_api_fixtures_do_not_submit_creator_nodes():
    cases=((ROOT/"tests/integration/test_core_workflow_api_postgresql.py","_create_payload","_post_action"),(ROOT/"tests/integration/test_completion_review_api_postgresql.py","_create_ready_task","_cleanup"),(ROOT/"tests/integration/test_task_board_api_postgresql.py","_task_payload","_post_action"))
    for path,name,next_name in cases:
        block=_block(path,name,next_name); assert not any(x in block for x in ('"nodes":','"dependencies":','"node_participants":')),path.name
def test_pg_main_flows_do_not_restore_manual_plan_confirmation():
    for rel in ("tests/integration/test_business_capabilities_postgresql.py","tests/integration/test_core_workflow_postgresql.py"):
        assert "confirm_task_plan(" not in (ROOT/rel).read_text(encoding="utf-8"),rel
