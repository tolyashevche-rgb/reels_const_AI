"""Quick test: verify TwelveLabs API key and list indexes."""
from twelvelabs import TwelveLabs

client = TwelveLabs(api_key="tlk_31ZY2PN25RYHHV2Y201R20N3NKK7")

print("Listing indexes...")
for idx in client.indexes.list():
    vcount = getattr(idx, "video_count", "?")
    print(f"  - {idx.id}: {idx.index_name} (videos: {vcount})")

print("\nDone!")
