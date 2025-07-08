import os
import time
import random
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

@sio.on("offer")
async def handle_offer(sid, data):
    target_id = data.get("target")
    description = data.get("description")
    if target_id and description:
        print(f"[SIGNALING] Offer từ {sid} → {target_id}")
        await sio.emit("offer", {"from": sid, "description": description}, room=target_id)

@sio.on("answer")
async def handle_answer(sid, data):
    target_id = data.get("target")
    description = data.get("description")
    if target_id and description:
        print(f"[SIGNALING] Answer từ {sid} → {target_id}")
        await sio.emit("answer", {"from": sid, "description": description}, room=target_id)

@sio.on("candidate")
async def handle_candidate(sid, data):
    target_id = data.get("target")
    candidate = data.get("candidate")
    if target_id and candidate:
        print(f"[SIGNALING] ICE candidate từ {sid} → {target_id}")
        await sio.emit("candidate", {"from": sid, "candidate": candidate}, room=target_id)

@sio.event
async def connect(sid, environ):
    print(f"[+] Client connected: {sid}")
    await sio.emit("re_authenticate", {}, room=sid)

@sio.event
async def disconnect(sid):
    to_remove = []
    print(f"[SERVER] 👋 DISCONNECT: {sid}")
    
    for viewer_id, broadcaster_id in list(peers.items()):
        if broadcaster_id == sid:
            print(f"[SERVER] Sending peer_disconnect to {viewer_id} because broadcaster {sid} disconnected")
            await sio.emit('peer_disconnect', {'from': sid}, room=viewer_id)
            to_remove.append(viewer_id)
        if viewer_id == sid:
            print(f"[SERVER] Sending peer_disconnect to broadcaster {broadcaster_id} because viewer {sid} disconnected")
            await sio.emit('peer_disconnect', {'from': sid}, room=broadcaster_id)
            to_remove.append(viewer_id)

    for viewer_id in to_remove:
        peers.pop(viewer_id, None)

    if sid in broadcasters:
        print(f"[SERVER] Xoá broadcaster đã disconnect: {sid}")
        broadcasters.discard(sid)
        global current_image_type
        current_image_type = "default"
        for viewer_sid in viewer_names:
            await sio.emit("image_type_changed", {"type": current_image_type}, room=viewer_sid)

    viewer_names.pop(sid, None)

    global host_sid
    if sid == host_sid:
        print("[SERVER] Host đã rời khỏi phòng")
        remaining = [vsid for vsid in viewer_names if vsid != sid]
        if remaining:
            host_sid = remaining[0]
            print(f"[SERVER] Chuyển quyền host cho {viewer_names[host_sid]}")

            await sio.emit("host_updated", {"hostId": host_sid})
            await sio.emit("image_type_changed", {"type": current_image_type}, room=host_sid)
        else:
            host_sid = None

    joined_viewers.discard(sid)
    pending_viewers.discard(sid)
    await broadcast_viewer_list()

@sio.event
async def join_broadcaster(sid):
    await sio.save_session(sid, {'role': 'broadcaster'})
    broadcasters.add(sid)
    print(f"[BROADCASTER] {sid} joined")

    # 🔔 Thông báo cho tất cả viewer rằng broadcaster đã online
    for viewer_sid in viewer_names:
        await sio.emit("broadcaster_connected", {}, room=viewer_sid)

    # 🔁 Ghép lại các viewer đang chờ
    for viewer_sid in list(pending_viewers):
        peers[viewer_sid] = sid
        await sio.emit('viewer_joined', {'viewer_id': viewer_sid}, room=sid)
        await sio.emit('broadcaster_joined', {'broadcaster_id': sid}, room=viewer_sid)
        print(f"[SERVER] Pending viewer {viewer_sid} paired → broadcaster {sid}")

    # ✅ Nếu host viewer đã có sẵn từ trước nhưng chưa gán broadcaster
    if host_sid and host_sid not in peers:
        peers[host_sid] = sid
        await sio.emit('viewer_joined', {'viewer_id': host_sid}, room=sid)
        await sio.emit('broadcaster_joined', {'broadcaster_id': sid}, room=host_sid)
        print(f"[SERVER] Gán lại host viewer {host_sid} → broadcaster {sid}")

    # 🔁 Gửi lại image type hiện tại cho broadcaster mới
    await sio.emit("image_type_changed", {"type": current_image_type}, room=sid)

@sio.event
async def transfer_host(sid, data):
    target_id = data.get("targetId")
    global host_sid

    if sid != host_sid:
        print("❌ Không phải host nên không được chuyển quyền.")
        return

    if not target_id or target_id not in viewer_names:
        print("❌ target không hợp lệ")
        return

    host_sid = target_id
    print(f"[HOST TRANSFERRED] New host: {viewer_names[host_sid]}")

    await sio.emit("host_updated", {"hostId": host_sid})
    await broadcast_viewer_list()

@sio.event
async def join_viewer(sid, data=None):
    if not isinstance(data, dict):
        await sio.disconnect(sid)
        return

    raw_username = data.get("username", "").strip()
    if not raw_username:
        # Tạo tên mặc định dạng "Guest42"
        while True:
            guest_name = f"Guest{random.randint(10, 99)}"
            if guest_name not in viewer_names.values():
                username = guest_name
                break
    else:
        username = raw_username

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
        await sio.emit("host_updated", {"hostId": host_sid})
        await sio.emit("image_type_changed", {"type": current_image_type}, room=sid)
        print(f"[SERVER] Đã gửi host_updated tới {sid}")

    print(f"[VIEWER] {sid} joined as '{username}'")

    await sio.emit('join_success', {'username': username}, room=sid)
    print(f"[SERVER] Đã emit join_success cho {sid}")

    joined_viewers.add(sid)
    for vsid in joined_viewers:
        if vsid != sid:
            await sio.emit('new_viewer', {'name': username}, room=vsid)

    await broadcast_viewer_list()

    for broadcaster_sid in broadcasters:
        # Kiểm tra broadcaster đang hoạt động bằng cách dùng sio.manager.is_connected()
        if sio.manager.is_connected(broadcaster_sid, '/'):
            peers[sid] = broadcaster_sid
            await sio.emit('viewer_joined', {'viewer_id': sid}, room=broadcaster_sid)
            print(f"[DEBUG] Đã gửi viewer_joined từ server đến broadcaster {broadcaster_sid}")
            print(f"[SERVER] Viewer {sid} paired to broadcaster {broadcaster_sid}")
            return

    pending_viewers.add(sid)
    print(f"[SERVER] No broadcaster for viewer {sid} ('{username}'). Added to pending.")

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

    broadcaster_sid = peers.get(host_sid)
    if broadcaster_sid:
        print(f"[SERVER] Gửi image_type_changed tới broadcaster: {broadcaster_sid}")
        await sio.emit("image_type_changed", {"type": img_type}, room=broadcaster_sid)

    for viewer_sid in viewer_names:
        await sio.emit("image_type_changed", {"type": img_type}, room=viewer_sid)

    print(f"[SERVER] Image type changed to: {img_type}")

async def broadcast_viewer_list():
    viewers = [
        {"id": sid, "name": name, "is_host": (sid == host_sid)}
        for sid, name in viewer_names.items()
    ]
    for vsid in joined_viewers:
        await sio.emit('viewer_list', {
            'count': len(viewers),
            'viewers': viewers,
            'hostId': host_sid
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"[SERVER] Starting signaling server on http://localhost:{port} or accessible via ngrok tunnel.")
    web.run_app(app, port=port)