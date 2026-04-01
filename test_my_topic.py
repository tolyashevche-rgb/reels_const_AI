"""
Інтерактивний тест: запускає повний pipeline з вашою темою.

    python test_my_topic.py
    python test_my_topic.py "ваша тема"
"""
import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Завжди реальний API
os.environ["USE_MOCK"] = "0"

# Перезавантажуємо singleton LLM з новим налаштуванням
import importlib
import app.llm
importlib.reload(app.llm)

from app.graph import content_graph

def main():
    # Тема — з аргументу або інтерактивно
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])
    else:
        print("─" * 60)
        print("  Reels Construction AI — Реальний тест")
        print("─" * 60)
        topic = input("\n📝 Введіть тему рілза (укр/англ): ").strip()
        if not topic:
            topic = "як розвинути мовлення дитини 2-3 роки"
            print(f"   (використовую дефолтну: {topic})")

    lang = input("🌐 Мова [uk/en, default uk]: ").strip() or "uk"
    dur  = input("⏱  Тривалість [15/30/60, default 30]: ").strip() or "30"

    try:
        dur = int(dur)
    except ValueError:
        dur = 30

    print(f"\n🚀 Запуск pipeline для: «{topic}»")
    print(f"   Мова: {lang}, тривалість: {dur}с")
    print("─" * 60)

    t0 = time.time()

    initial_state = {
        "topic": topic,
        "language": lang,
        "duration_sec": dur,
        "style": "warm_expert",
        "user_id": "test-user",
        "project_id": "my-test",
        "marketing_chunks": [],
        "child_dev_chunks": [],
        "search_candidates": [],
        "selected_assets": [],
        "errors": [],
    }

    result = content_graph.invoke(initial_state)

    elapsed = time.time() - t0
    print(f"\n⏱  Виконано за {elapsed:.1f}с")

    # ── Скрипт ──
    script = result.get("script", {})
    print("\n📜 СЦЕНАРІЙ:")
    print(f"  Hook: {script.get('hook', '—')}")
    print(f"  Body: {script.get('body', '—')}")
    print(f"  CTA:  {script.get('cta', '—')}")
    overlays = script.get("text_overlays", [])
    if overlays:
        print(f"  Overlays ({len(overlays)}): {' | '.join(overlays[:4])}...")

    # ── Policy ──
    policy = result.get("policy_result", {})
    status = "✅ APPROVED" if policy.get("approved") else "❌ REJECTED"
    print(f"\n🛡  Policy: {status}")
    for issue in policy.get("issues", []):
        if isinstance(issue, dict):
            print(f"   [{issue.get('severity')}] {issue.get('reason', '')}")

    # ── Shot list ──
    shots = result.get("shot_list", [])
    print(f"\n🎬 Shot list ({len(shots)} кадрів):")
    for s in shots:
        print(f"  Shot {s.get('order')}: {s.get('duration_sec')}s — {s.get('description','')[:70]}")

    # ── TwelveLabs ──
    sc = result.get("search_candidates", [])
    total_c = sum(len(s.get("candidates",[])) for s in sc)
    sa = result.get("selected_assets", [])
    real = sum(1 for a in sa if a.get("selected"))
    print(f"\n🔍 TwelveLabs: знайдено {total_c} кандидатів → обрано {real} реальних кліпів")

    # ── Voice-over ──
    vt = result.get("voice_track", "")
    vd = result.get("voice_duration_sec", 0)
    if vt and os.path.exists(vt):
        size_kb = os.path.getsize(vt) / 1024
        print(f"\n🎙  Voice-over: {os.path.basename(vt)} ({size_kb:.0f} KB, {vd:.1f}s)")
    else:
        print(f"\n🎙  Voice-over: немає")

    # ── Render ──
    ro = result.get("render_output", "")
    if ro and os.path.exists(ro):
        size_mb = os.path.getsize(ro) / (1024 * 1024)
        print(f"🎥 Відео: {ro} ({size_mb:.1f} MB)")
    else:
        print(f"🎥 Відео: не згенеровано")

    # ── Preview URL ──
    pu = result.get("preview_url", "")
    if pu:
        print(f"🔗 Preview: http://localhost:8084{pu}")

    # ── Errors ──
    errors = result.get("errors", [])
    if errors:
        print(f"\n⚠️  Помилки:")
        for e in errors:
            print(f"   {e[:120]}")

    print("\n" + "=" * 60)
    if not errors or ro:
        print("  ✅ Готово! Перевірте відео за шляхом вище.")
    else:
        print("  ⚠️  Pipeline завершено з помилками.")
    print("=" * 60)


if __name__ == "__main__":
    main()
