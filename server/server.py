import os
import time
import atexit
import socketio
import subprocess
from aiohttp import web

sio = socketio.AsyncServer(cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

peers = {}
viewer_names = {}
broadcasters = set()
joined_viewers = set()
pending_viewers = set()
current_image_type = "default"
host_sid = None

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

    for viewer_id, broadcaster_id in list(peers.items()):
        if broadcaster_id == sid:
            await sio.emit('peer_disconnect', {'from': sid}, room=viewer_id)
            peers.pop(viewer_id)
        elif viewer_id == sid:
            await sio.emit('peer_disconnect', {'from': sid}, room=broadcaster_id)
            peers.pop(sid)

    viewer_names.pop(sid, None)

    global host_sid
    if sid == host_sid:
        print("[SERVER] Host đã rời khỏi phòng")
        remaining = [vsid for vsid in viewer_names if vsid != sid]
        if remaining:
            host_sid = remaining[0]
            print(f"[SERVER] Chuyển quyền host cho {viewer_names[host_sid]}")
            
            await sio.emit("you_are_host", {}, room=host_sid)
            await sio.emit("image_type_changed", {"type": current_image_type}, room=host_sid)
        else:
            host_sid = None

    joined_viewers.discard(sid)
    await broadcast_viewer_list()

@sio.event
async def join_broadcaster(sid):
    await sio.save_session(sid, {'role': 'broadcaster'})
    broadcasters.add(sid)
    print(f"[BROADCASTER] {sid} joined")

    # Thông báo broadcaster đã kết nối tới viewer
    for viewer_sid in viewer_names:
        await sio.emit("broadcaster_connected", {}, room=viewer_sid)

    # Ghép các viewer đang chờ (gồm cả host nếu host là người join đầu)
    for viewer_sid in list(pending_viewers):
        peers[viewer_sid] = sid
        await sio.emit('viewer_joined', {'viewer_id': viewer_sid}, room=sid)
        print(f"[SERVER] Pending viewer {viewer_sid} paired → broadcaster {sid}")
        pending_viewers.remove(viewer_sid)

    # Gửi type hiện tại
    await sio.emit("image_type_changed", {"type": current_image_type}, room=sid)

@sio.event
async def join_viewer(sid, data):
    username = data.get("username", "").strip()

    if not (3 <= len(username) <= 10):
        await sio.emit('username_error', {
            'message': 'Tên người dùng phải từ 3 đến 10 ký tự.'
        }, room=sid)
        return

    if username in viewer_names.values():
        await sio.emit('username_error', {
            'message': 'Username đã tồn tại, vui lòng chọn tên khác.'
        }, room=sid)
        return

    await sio.save_session(sid, {'role': 'viewer', 'username': username})
    viewer_names[sid] = username

    global host_sid
    if host_sid is None:
        host_sid = sid
        print(f"[SERVER] Viewer '{username}' được đánh dấu là HOST")
        await sio.emit("you_are_host", {}, room=sid)
        # await sio.emit("image_type_changed", {"type": current_image_type}, room=sid)
        print(f"[SERVER] Đã gửi you_are_host tới {sid}")

    print(f"[VIEWER] {sid} joined as '{username}'")
    
    await sio.emit('join_success', {}, room=sid)
    print(f"[SERVER] Đã emit join_success cho {sid}")

    joined_viewers.add(sid)
    for vsid in joined_viewers:
        if vsid != sid:
            await sio.emit('new_viewer', {'name': username}, room=vsid)

    await broadcast_viewer_list()

    for broadcaster_sid in broadcasters:
        if broadcaster_sid in sio.manager.rooms['/']:
            peers[sid] = broadcaster_sid
            await sio.emit('viewer_joined', {'viewer_id': sid}, room=broadcaster_sid)
            return

    pending_viewers.add(sid)
    print(f"[SERVER] No broadcaster for viewer {sid} ('{username}'). Added to pending.")

@sio.event
async def image_frame(sid, data):
    for viewer_id, broadcaster_id in list(peers.items()): 
        if broadcaster_id == sid:
            await sio.emit("image_frame", data, room=viewer_id)

@sio.event
async def change_image_type(sid, data):
    global current_image_type, host_sid
    if sid != host_sid:
        return

    img_type = data.get("type")
    if img_type not in ("default", "nir", "ndvi"):
        print(f"[SERVER] Invalid image type received: {img_type}")
        return

    current_image_type = img_type

    # Gửi cho broadcaster duy nhất
    broadcaster_sid = next(iter(broadcasters), None)
    if broadcaster_sid:
        print(f"[SERVER] Gửi image_type_changed tới broadcaster: {broadcaster_sid}")
        await sio.emit("image_type_changed", {"type": img_type}, room=broadcaster_sid)

    # Gửi cho toàn bộ viewer để cập nhật giao diện
    for viewer_sid in viewer_names:
        await sio.emit("image_type_changed", {"type": img_type}, room=viewer_sid)

    print(f"[SERVER] Image type changed to: {img_type}")

async def broadcast_viewer_list():
    viewers = [
        {"name": name, "is_host": (sid == host_sid)}
        for sid, name in viewer_names.items()
    ]
    for vsid in joined_viewers:
        await sio.emit('viewer_list', {
            'count': len(viewers),
            'viewers': viewers
        }, room=vsid)

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(ROOT_DIR, '..', 'view', 'static')

async def index(request):
    timestamp = str(int(time.time()))
    html_path = os.path.join(STATIC_DIR, 'index.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read().replace("{{TIMESTAMP}}", timestamp)
    return web.Response(text=html, content_type='text/html')

app.router.add_get('/', index)
app.router.add_static('/static/', path=STATIC_DIR, name='static')

@atexit.register
def cleanup():
    print("[SERVER] Shutting down ngrok...")
    try:
        ngrok_proc.terminate()
    except Exception as e:
        print(f"[ERROR] Could not terminate ngrok: {e}")

if __name__ == '__main__':
    ngrok_proc = subprocess.Popen(
        ["ngrok", "http", "--subdomain=vindvi", "--region=ap", "5000"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    print("[SERVER] Starting on http://localhost:5000")
    web.run_app(app, port=5000)