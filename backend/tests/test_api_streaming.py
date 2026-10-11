"""Real-time events: the broker, the SSE endpoint and the checkpoint history."""

import asyncio

from langchain_core.messages import AIMessage

from brain_agent.runtime.events import EventBroker
from tests.api_support import make_settings, register, running_api
from tests.fakes import tool_call
from tests.test_api_threads import APPROVE, EXTERNAL_EMAIL, new_thread, settled


async def test_broker_numbers_events_and_replays_after_an_id() -> None:
    broker = EventBroker(buffer_size=3)
    ids = [broker.publish("t", "node", {"n": n}).id for n in range(5)]
    assert ids == sorted(set(ids))
    assert broker.latest_id("t") == ids[-1] and broker.latest_id("other") == 0

    stream = broker.subscribe("t", ids[2])  # the buffer only holds the last three
    assert [(await anext(stream)).id for _ in range(2)] == ids[3:]
    replay = broker.subscribe("t", 0)
    assert [(await anext(replay)).id for _ in range(3)] == ids[2:]
    await stream.aclose()
    await replay.aclose()


async def test_broker_delivers_live_events_and_stops_on_close() -> None:
    broker = EventBroker()
    received: list[str] = []

    async def listen() -> None:
        async for event in broker.subscribe("t", broker.latest_id("t")):
            received.append(event.type)

    task = asyncio.create_task(listen())
    await asyncio.sleep(0)
    broker.publish("t", "token", {})
    broker.publish("t", "run_completed", {})
    await asyncio.sleep(0.01)
    assert received == ["token", "run_completed"] and broker.subscriber_count("t") == 1
    broker.close()
    await asyncio.wait_for(task, 1)
    assert broker.subscriber_count("t") == 0


async def test_broker_forgets_idle_threads_but_keeps_ids_increasing() -> None:
    now = [0.0]
    broker = EventBroker(idle_seconds=60, clock=lambda: now[0])
    first = broker.publish("idle", "node", {}).id
    broker.publish("watched", "node", {})
    watcher = broker.subscribe("watched", 0)
    await anext(watcher)
    now[0] = 61
    broker.sweep()
    assert broker.thread_count == 1  # only the watched thread survives
    assert broker.publish("idle", "node", {}).id > first  # a reconnecting client never skips
    await watcher.aclose()


async def test_stream_delivers_run_events_in_order_then_resumes_from_last_event_id() -> None:
    async with running_api([AIMessage(content="Hello Ana!")]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        async with h.sse(f"/threads/{tid}/events", headers) as stream:
            assert stream.status == 200
            assert stream.headers["content-type"].startswith("text/event-stream")
            await h.client.post(f"/threads/{tid}/messages", json={"content": "hi"}, headers=headers)
            events = await stream.until("run_completed")
        ids = [e.id for e in events]
        assert ids == sorted(set(ids))
        assert [e.event for e in events if e.event != "node"] == ["token", "run_completed"]
        names = [e.data["node"] for e in events if e.event == "node"]
        assert "reason" in names
        token = next(e for e in events if e.event == "token")
        assert token.data == {"text": "Hello Ana!"}
        assert events[-1].data["status"] == "completed"
        assert events.index(token) < next(
            i for i, e in enumerate(events) if e.data.get("node") == "reason"
        )

        async with h.sse(f"/threads/{tid}/events", {**headers, "Last-Event-ID": str(ids[1])}) as s2:
            assert [e.id for e in await s2.until("run_completed")] == ids[2:]
        async with h.sse(f"/threads/{tid}/events?after={ids[-2]}", headers) as s3:
            assert [e.id for e in await s3.until("run_completed")] == ids[-1:]


async def test_stream_heartbeats_and_stops_on_disconnect_and_shutdown() -> None:
    async with running_api([], make_settings(sse_heartbeat_seconds=0.05)) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        stream = h.sse(f"/threads/{tid}/events", headers)
        async with stream:
            assert (await stream.frame()).startswith(":")
            assert h.container.events.subscriber_count(tid) == 1
        assert stream.finished and h.container.events.subscriber_count(tid) == 0

        closing = h.sse(f"/threads/{tid}/events", headers)
        async with closing:
            await asyncio.sleep(0.01)
            h.container.events.close()  # what the lifespan does on shutdown
            await asyncio.wait_for(closing._task, 1)


async def test_stream_auth_ownership_and_query_token_only_on_events() -> None:
    async with running_api([]) as h:
        ana = await register(h.client, "ana@acme.com")
        bob = await register(h.client, "bob@acme.com")
        tid = await new_thread(h, ana)
        token = ana["Authorization"].removeprefix("Bearer ")
        async with h.sse(f"/threads/{tid}/events?access_token={token}") as ok:
            assert ok.status == 200
        for path, headers, expected in (
            (f"/threads/{tid}/events", None, 401),
            (f"/threads/{tid}/events?access_token=garbage", None, 401),
            (f"/threads/{tid}/events", bob, 404),
        ):
            async with h.sse(path, headers) as denied:
                assert denied.status == expected
        for path in (f"/threads/{tid}", "/threads", "/auth/me", "/memories", "/rules"):
            assert (await h.client.get(f"{path}?access_token={token}")).status_code == 401


async def test_approval_flow_streams_interrupt_then_tool_events() -> None:
    async with running_api([EXTERNAL_EMAIL, AIMessage(content="Email sent.")]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        async with h.sse(f"/threads/{tid}/events", headers) as stream:
            await h.client.post(
                f"/threads/{tid}/messages", json={"content": "Email bob"}, headers=headers
            )
            first = await stream.until("run_completed")
            kinds = [e.event for e in first]
            assert kinds.index("tool_call") < kinds.index("interrupt")
            call = next(e for e in first if e.event == "tool_call")
            assert call.data["name"] == "send_email" and call.data["id"] == "call-1"
            assert (
                next(e for e in first if e.event == "interrupt").data["kind"] == "approval_required"
            )
            assert first[-1].data["status"] == "interrupted"

            await h.client.post(f"/threads/{tid}/approvals", json=APPROVE, headers=headers)
            second = await stream.until("run_completed")
            result = next(e for e in second if e.event == "tool_result")
            assert result.data["id"] == "call-1" and result.data["status"] == "success"
            assert second[-1].data["status"] == "completed"
            assert [e.data["text"] for e in second if e.event == "token"] == ["Email sent."]
            assert first[-1].id < second[0].id


async def test_failed_run_streams_a_safe_error() -> None:
    async with running_api([ValueError("secret-detail-xyz")]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        async with h.sse(f"/threads/{tid}/events", headers) as stream:
            await h.client.post(f"/threads/{tid}/messages", json={"content": "go"}, headers=headers)
            events = await stream.until("run_failed")
        assert events[-1].data == {"code": "run_failed", "message": "The run failed."}
        state = await settled(h.client, headers, tid)
        assert state["run"] == {"status": "failed", "error": "run_failed"}
        assert "secret" not in str(state)


async def test_history_lists_checkpoints_newest_first() -> None:
    async with running_api([tool_call("list_tasks", {}, "c1"), AIMessage(content="None.")]) as h:
        ana = await register(h.client, "ana@acme.com")
        bob = await register(h.client, "bob@acme.com")
        tid = await new_thread(h, ana)
        await h.client.post(f"/threads/{tid}/messages", json={"content": "tasks?"}, headers=ana)
        await settled(h.client, ana, tid)

        history = (await h.client.get(f"/threads/{tid}/history", headers=ana)).json()
        steps = [c["step"] for c in history]
        assert steps == sorted(steps, reverse=True) and len(steps) > 4
        newest, oldest = history[0], history[-1]
        assert set(newest) == {
            "checkpoint_id",
            "step",
            "created_at",
            "source",
            "writes",
            "next",
            "message_count",
        }
        assert newest["next"] == [] and newest["message_count"] == 4
        assert "reason" in {node for c in history for node in c["writes"]}
        assert (oldest["source"], oldest["writes"], oldest["message_count"]) == ("input", [], 0)
        assert len((await h.client.get(f"/threads/{tid}/history?limit=2", headers=ana)).json()) == 2
        assert (
            await h.client.get(f"/threads/{tid}/history?limit=0", headers=ana)
        ).status_code == 422
        assert (await h.client.get(f"/threads/{tid}/history", headers=bob)).status_code == 404
