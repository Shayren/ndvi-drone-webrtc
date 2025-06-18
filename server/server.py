import os
import socketio
from aiohttp import web

# Khởi tạo server
sio = socketio.AsyncServer(cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

# Dữ liệu server
peers = {}               # viewer_id -> broadcaster_id
viewer_names = {}        # sid -> username
broadcasters = set()     # broadcaster đang online
pending_viewers = set()  # viewer chưa ghép được

host_sid = None  # Global biến để lưu viewer đầu tiên

@sio.event
async def connect(sid, environ):
    print(f"[+] Client connected: {sid}")
    await sio.emit("re_authenticate", {}, room=sid)

@sio.event
async def disconnect(sid):
    print(f"[-] Client disconnected: {sid}")
    peers.pop(sid, None)
    pending_viewers.discard(sid)
    broadcasters.discard(sid)

    # Nếu là broadcaster, thông báo các viewer
    for viewer_id, broadcaster_id in list(peers.items()):
        if broadcaster_id == sid:
            await sio.emit('peer_disconnect', {'from': sid}, room=viewer_id)
            peers.pop(viewer_id)

    # Nếu là viewer, thông báo broadcaster
    for viewer_id, broadcaster_id in list(peers.items()):
        if viewer_id == sid:
            await sio.emit('peer_disconnect', {'from': sid}, room=broadcaster_id)
            peers.pop(sid)

    viewer_names.pop(sid, None)
    
    global host_sid
    if sid == host_sid:
        print("[SERVER] Host đã rời khỏi phòng")

        # Tìm viewer tiếp theo (nếu có)
        remaining_viewers = [vsid for vsid in viewer_names if vsid != sid]
        if remaining_viewers:
            host_sid = remaining_viewers[0]
            print(f"[SERVER] Chuyển quyền host cho viewer {viewer_names[host_sid]}")
        else:
            host_sid = None

    await broadcast_viewer_list()

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
async def join_viewer(sid, data):
    username = data.get("username", "").strip()

    if not (3 <= len(username) <= 10):
        await sio.emit('username_error', {
            'message': 'Tên người dùng phải từ 3 đến 10 ký tự.'
        }, room=sid)
        print(f"[SERVER] Viewer {sid} attempted invalid-length username '{username}'")
        return

    if username in viewer_names.values():
        await sio.emit('username_error', {
            'message': 'Username đã tồn tại, vui lòng chọn tên khác.'
        }, room=sid)
        print(f"[SERVER] Viewer {sid} attempted duplicate username '{username}'")
        return

    await sio.save_session(sid, {'role': 'viewer', 'username': username})
    viewer_names[sid] = username
    global host_sid
    if host_sid is None:
        host_sid = sid
    print(f"[SERVER] Viewer '{username}' được đánh dấu là HOST")
    print(f"[VIEWER] {sid} joined as '{username}'")
    await sio.emit('join_success', {}, room=sid)

    await broadcast_viewer_list()
    for broadcaster_sid in broadcasters:
        if broadcaster_sid in sio.manager.rooms['/']:
            peers[sid] = broadcaster_sid
            await sio.emit('viewer_joined', {'viewer_id': sid}, room=broadcaster_sid)
            print(f"[SERVER] Viewer {sid} ('{username}') paired with broadcaster {broadcaster_sid}")
            return

    pending_viewers.add(sid)
    print(f"[SERVER] No broadcaster for viewer {sid} ('{username}'). Added to pending.")

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

async def broadcast_viewer_list():
    unique_list = []
    for sid, name in viewer_names.items():
        unique_list.append({
            "name": name,
            "is_host": (sid == host_sid)
        })

    await sio.emit('viewer_list', {
        'count': len(unique_list),
        'viewers': unique_list
    })

# Static file serving
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(ROOT_DIR, 'static')

async def index(request):
    return web.FileResponse(path=os.path.join(STATIC_DIR, 'index.html'))

app.router.add_get('/', index)
app.router.add_static('/static/', path=STATIC_DIR, name='static')

if __name__ == '__main__':
    # from pyngrok import ngrok

    port = 5000
    print("[SERVER] Starting on http://localhost:5000")

    # public_url = ngrok.connect(port)
    # print(f"[NGROK] Public URL: {public_url}")

    web.run_app(app, port=port)
