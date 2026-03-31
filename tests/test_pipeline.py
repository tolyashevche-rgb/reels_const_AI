"""
End-to-end test — запускає повний LangGraph pipeline з MockLLM.

    python -m tests.test_pipeline
"""
import os
import json
import sys

# Mock mode — без реального API
os.environ["USE_MOCK"] = "1"

# Додаємо root до path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.graph import content_graph


def main():
    print("=" * 60)
    print("  Reels Construction AI — E2E Pipeline Test (MOCK)")
    print("=" * 60)

    initial_state = {
        "topic": "як розвинути мовлення дитини 1-3 роки",
        "language": "uk",
        "duration_sec": 30,
        "style": "warm_expert",
        "user_id": "test-user",
        "project_id": "test-project",
        "marketing_chunks": [],
        "child_dev_chunks": [],
        "errors": [],
    }

    print(f"\n📥 Вхід: {initial_state['topic']}")
    print(f"   Мова: {initial_state['language']}, Тривалість: {initial_state['duration_sec']}с\n")

    result = content_graph.invoke(initial_state)

    # ── 1. Normalized topic ──
    print("─" * 60)
    print("1️⃣  input_normalizer")
    print(f"   Тема: {result.get('normalized_topic', '???')}")

    # ── 2. Intent ──
    print("\n2️⃣  audience_intent_analysis")
    intent = result.get("intent", {})
    print(f"   Емоція:    {intent.get('emotion')}")
    print(f"   Біль:      {intent.get('pain_point')}")
    print(f"   Тип рілза: {intent.get('reel_type')}")
    print(f"   Вік:       {intent.get('age_focus')}")

    # ── 3. RAG ──
    print("\n3️⃣  retrieve_knowledge")
    mc = result.get("marketing_chunks", [])
    cc = result.get("child_dev_chunks", [])
    print(f"   Marketing chunks: {len(mc)}")
    print(f"   Child dev chunks: {len(cc)}")

    # ── 4. Script ──
    print("\n4️⃣  script_writer")
    script = result.get("script", {})
    print(f"   Hook: {script.get('hook', '—')}")
    print(f"   Body: {script.get('body', '—')[:100]}...")
    print(f"   CTA:  {script.get('cta', '—')}")
    print(f"   Overlays: {len(script.get('text_overlays', []))} шт.")

    # ── 5. Policy ──
    print("\n5️⃣  policy_review")
    policy = result.get("policy_result", {})
    status = "✅ APPROVED" if policy.get("approved") else "❌ REJECTED"
    print(f"   Статус: {status}")
    for issue in policy.get("issues", []):
        if isinstance(issue, dict):
            print(f"   ⚠ [{issue.get('severity')}] {issue.get('reason')}")

    # ── 6. Shot list ──
    print("\n6️⃣  shot_planner")
    shots = result.get("shot_list", [])
    total_dur = 0
    for shot in shots:
        dur = shot.get("duration_sec", 0)
        total_dur += dur
        print(f"   Shot {shot.get('order')}: {dur}s — {shot.get('description', '')[:60]}...")
    print(f"   Total: {total_dur}s")

    # ── Errors ──
    errors = result.get("errors", [])
    if errors:
        print(f"\n⚠️  Errors: {errors}")

    print("\n" + "=" * 60)
    print("  Pipeline завершено успішно! ✅")
    print("=" * 60)

    # Full JSON dump
    print("\n📋 Full result JSON:")
    safe_result = {k: v for k, v in result.items() if k != "errors" or v}
    print(json.dumps(safe_result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
