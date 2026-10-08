"""Liest öffentliche TikTok-Video-Stats aus einer gespeicherten Videoseite.

Aufruf: python3 -I tiktok_stats.py <seite.html> <video_id>
Ausgabe: id, createTime, Views, Likes, Kommentare, Shares, Favoriten | Caption
"""
import re, json, sys
s = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
m = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', s, re.S)
if not m:
    print(sys.argv[2], "kein Daten-Block"); sys.exit()
d = json.loads(m.group(1)).get("__DEFAULT_SCOPE__", {})
it = d.get("webapp.video-detail", {}).get("itemInfo", {}).get("itemStruct", {})
st = it.get("stats", {})
print(sys.argv[2], it.get("createTime"), st.get("playCount"), st.get("diggCount"), st.get("commentCount"), st.get("shareCount"), st.get("collectCount"), "|", (it.get("desc") or "")[:60])
