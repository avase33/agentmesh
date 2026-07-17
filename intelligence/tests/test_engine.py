import pytest

from agentmesh_intelligence.engine import AgentEngine
from agentmesh_intelligence.executor_client import (
    _local_csv,
    _local_eval,
    _local_tokenize,
)
from agentmesh_intelligence.models import Workflow
from agentmesh_intelligence.workflows import rag_cost_workflow

pytestmark = pytest.mark.asyncio


def test_topo_order_and_cycle_detection():
    wf = rag_cost_workflow()
    order = wf.topo_order()
    assert order[0] == "in" and order[-1] == "out"

    cyclic = Workflow.from_dict(
        {"nodes": [{"id": "a", "type": "input"}, {"id": "b", "type": "output"}],
         "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}]}
    )
    with pytest.raises(ValueError):
        cyclic.topo_order()


def test_local_tokenize_matches_rust_semantics():
    # long word chunked into 4-char pieces; punctuation separate; whitespace dropped
    assert _local_tokenize("internationalization") == ["inte", "rnat", "iona", "liza", "tion"]
    toks = _local_tokenize("Hello, world 2026!")
    assert "," in toks and "2026" in toks and "!" in toks


def test_local_eval_sandbox():
    assert _local_eval("2 + 3 * 4", {})[0] == 14.0
    assert _local_eval("tokens * 0.5", {"tokens": 10})[0] == 5.0
    assert _local_eval("3 > 2 and 1 < 2", {})[1] is True  # is_bool
    import pytest as _pytest

    with _pytest.raises(Exception):
        _local_eval("__import__('os').system('ls')", {})
    with _pytest.raises(Exception):
        _local_eval("1 / 0", {})


def test_local_csv_aggregation():
    csv = "id,amount\n1,10\n2,20\n3,5\n"
    assert _local_csv(csv, "sum", "amount") == (3, 35.0)
    assert _local_csv(csv, "max", "amount") == (3, 20.0)


async def test_full_workflow_run_offline():
    engine = AgentEngine()  # local executor, mock llm
    events, final = await engine.run_collect("t", rag_cost_workflow(), "How does the Go gateway scale?")

    phases = {e.phase for e in events}
    assert {"start", "tool_call", "tool_result", "token", "node_done", "done"} <= phases

    # retrieval surfaced the Go doc; llm grounded on it
    nodes_started = [e.node for e in events if e.phase == "start"]
    assert nodes_started == ["in", "rag", "brain", "cost", "out"]

    # the eval tool produced a numeric cost from the token count
    cost_results = [e.data for e in events if e.phase == "tool_result" and "value" in e.data]
    assert cost_results and cost_results[0]["ok"] is True
    assert final  # non-empty synthesized answer


async def test_engine_streams_tokens():
    engine = AgentEngine()
    tokens = []
    async for ev in engine.run("t2", rag_cost_workflow(), "what is rust for?"):
        if ev.phase == "token":
            tokens.append(ev.text)
    assert len(tokens) > 3
