import os
import socketio
from aiohttp import web

# Khởi tạo server
sio = socketio.AsyncServer(cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

# Lưu thông tin mapping giữa viewer <-> broadcaster
peers = {}              # viewer_id -> broadcaster_id
broadcasters = set()    # các broadcaster đang online
pending_viewers = set() # các viewer chưa được ghép

@sio.event
async def connect(sid, environ):
    print(f"[+] Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"[-] Client disconnected: {sid}")
    # Xoá khỏi mapping
    peers.pop(sid, None)
    pending_viewers.discard(sid)
    broadcasters.discard(sid)

    # Nếu là broadcaster, thông báo cho các viewer ghép với nó
    for viewer_id, broadcaster_id in list(peers.items()):
        if broadcaster_id == sid:
            await sio.emit('peer_disconnect', {'from': sid}, room=viewer_id)
            peers.pop(viewer_id)

    # Nếu là viewer, thông báo cho broadcaster
    for viewer_id, broadcaster_id in list(peers.items()):
        if viewer_id == sid:
            await sio.emit('peer_disconnect', {'from': sid}, room=broadcaster_id)
            peers.pop(sid)

@sio.event
async def join_broadcaster(sid):
    await sio.save_session(sid, {'role': 'broadcaster'})
    broadcasters.add(sid)
    print(f"[BROADCASTER] {sid} joined")

    # Ghép các viewer đang chờ
    for viewer_sid in list(pending_viewers):
        peers[viewer_sid] = sid
        await sio.emit('viewer_joined', {'viewer_id': viewer_sid}, room=sid)
        print(f"[SERVER] Pending viewer {viewer_sid} paired → broadcaster {sid}")
        pending_viewers.remove(viewer_sid)

@sio.event
async def join_viewer(sid):
    await sio.save_session(sid, {'role': 'viewer'})
    print(f"[VIEWER] {sid} joined")

    # Ghép với broadcaster đầu tiên đang hoạt động
    for broadcaster_sid in broadcasters:
        if broadcaster_sid in sio.manager.rooms['/']:
            peers[sid] = broadcaster_sid
            await sio.emit('viewer_joined', {'viewer_id': sid}, room=broadcaster_sid)
            print(f"[SERVER] Viewer {sid} paired with broadcaster {broadcaster_sid}")
            return

    # Không có broadcaster
    pending_viewers.add(sid)
    print(f"[SERVER] No broadcaster for viewer {sid}. Added to pending.")

@sio.event
async def offer(sid, data):
    target = peers.get(sid)
    if target:
        print(f"[OFFER] {sid} -> {target}")
        await sio.emit('offer', {'sdp': data['sdp'], 'from': sid}, room=target)

@sio.event
async def answer(sid, data):
    target = data.get('to')
    if target:
        print(f"[ANSWER] {sid} -> {target}")
        await sio.emit('answer', {'sdp': data['sdp'], 'from': sid}, room=target)

@sio.event
async def candidate(sid, data):
    target = data.get('to')
    if target:
        print(f"[CANDIDATE] {sid} -> {target}")
        await sio.emit('candidate', {
            'candidate': data['candidate'],
            'sdpMid': data.get('sdpMid'),
            'sdpMLineIndex': data.get('sdpMLineIndex'),
            'from': sid
        }, room=target)

@sio.event
async def image_frame(sid, data):
    for viewer_id, broadcaster_id in list(peers.items()): 
        if broadcaster_id == sid:
            await sio.emit("image_frame", data, room=viewer_id)

# Static file serving
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(ROOT_DIR, 'static')

# Trả về index.html
async def index(request):
    return web.FileResponse(path=os.path.join(STATIC_DIR, 'index.html'))

app.router.add_get('/', index)
app.router.add_static('/static/', path=STATIC_DIR, name='static')

# Chạy server
if __name__ == '__main__':
    print("[SERVER] Listening on http://localhost:5000")
    web.run_app(app, port=5000)
