"""
Quick test: TwelveLabs search for a single shot description.
Tests the real API without running the full pipeline.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.twelvelabs_client import get_twelvelabs_client

client = get_twelvelabs_client()
if client is None:
    print("ERROR: client is None (USE_MOCK=1?)")
    sys.exit(1)

# List indexes
print("=== Indexes ===")
index_ids = []
for idx in client.indexes.list():
    vcount = getattr(idx, "video_count", "?")
    print(f"  {idx.id}: {idx.index_name} ({vcount} videos)")
    index_ids.append(idx.id)

# Search for a child-related query
query = "toddler playing with toys"
print(f"\n=== Search: '{query}' ===")

for index_id in index_ids:
    print(f"\nIndex: {index_id}")
    try:
        results = client.search.query(
            index_id=index_id,
            query_text=query,
            search_options=["visual"],
            group_by="clip",
            threshold="low",
            page_limit=3,
        )
        count = 0
        for item in results:
            count += 1
            print(f"  #{count}: video={item.video_id}, score={item.score}, "
                  f"start={item.start}, end={item.end}, conf={item.confidence}")
            if item.thumbnail_url:
                print(f"        thumb: {item.thumbnail_url[:80]}...")
        if count == 0:
            print("  (no results)")
    except Exception as e:
        print(f"  ERROR: {e}")

# Also check video retrieval (HLS URL)
if index_ids:
    print("\n=== Video info (first index, first video) ===")
    try:
        videos = client.indexes.videos.list(index_id=index_ids[0])
        for v in videos:
            print(f"  Video: {v.id}")
            vid_info = client.indexes.videos.retrieve(
                index_id=index_ids[0],
                video_id=v.id,
            )
            hls = getattr(vid_info, "hls", None)
            print(f"  HLS type: {type(hls)}")
            print(f"  HLS value: {hls}")
            if hasattr(hls, "video_url"):
                print(f"  HLS video_url: {hls.video_url[:80]}...")
            if hasattr(hls, "thumbnail_urls"):
                print(f"  HLS thumbnail_urls: {hls.thumbnail_urls}")
            # Show all attributes
            print(f"  All attrs: {[a for a in dir(vid_info) if not a.startswith('_')]}")
            break
    except Exception as e:
        print(f"  ERROR: {e}")

print("\nDone!")
