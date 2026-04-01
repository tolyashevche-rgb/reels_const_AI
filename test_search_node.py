"""Quick test: TwelveLabs search node with a single shot."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

# Force real API
os.environ["USE_MOCK"] = "0"

from app.nodes.twelvelabs_search import twelvelabs_search

result = twelvelabs_search({
    "shot_list": [
        {"order": 1, "description": "Close-up of toddler trying to speak", "duration_sec": 3, "text_overlay": "", "audio_cue": ""},
        {"order": 2, "description": "Parent reading book to child before bed", "duration_sec": 5, "text_overlay": "", "audio_cue": ""},
    ],
    "errors": [],
})

for sc in result.get("search_candidates", []):
    cands = sc.get("candidates", [])
    print(f"Shot {sc['shot_order']}: {len(cands)} candidates")
    for c in cands:
        print(f"  video={c['video_id'][:16]}... idx={c['index_id'][:8]}... "
              f"start={c['start']} end={c['end']}")

if result.get("errors"):
    print(f"Errors: {result['errors']}")
print("Done!")
