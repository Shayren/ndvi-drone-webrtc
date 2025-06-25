import socketio
import base64
import asyncio
import cv2

sio = socketio.AsyncClient()
connected_viewers = set()
send_task = None
current_image_type = "default"  # loại ảnh được host chọn

# Đọc sẵn ảnh mẫu
images = {
    "default": cv2.imread("imgs/rgb.png"),
    "nir":     cv2.imread("imgs/nir.png"),
    "ndvi":    cv2.imread("imgs/ndvi.png")
}

# Kiểm tra ảnh có tồn tại không
for k, img in images.items():
    if img is None:
        raise FileNotFoundError(f"[ERROR] Không tìm thấy ảnh mẫu '{k}.png' trong imgs/")

def get_current_frame():
    img = images.get(current_image_type, images["default"])
    _, buffer = cv2.imencode(".jpg", img)
    b64_frame = base64.b64encode(buffer).decode('utf-8')
    return b64_frame

@sio.event
async def connect():
    print("[BROADCASTER] Connected to server")
    await sio.emit("join_broadcaster")

@sio.event
async def viewer_joined(data):
    print(f"[DEBUG] viewer_joined triggered with data: {data}")
    viewer_id = data['viewer_id']
    connected_viewers.add(viewer_id)
    print(f"[BROADCASTER] Viewer joined: {viewer_id}")
    global send_task
    if send_task is None or send_task.done():
        print("[BROADCASTER] Start sending frames")
        send_task = asyncio.create_task(send_frames())

@sio.event
async def peer_disconnect(data):
    viewer_id = data['from']
    if viewer_id in connected_viewers:
        connected_viewers.remove(viewer_id)
        print(f"[BROADCASTER] Viewer disconnected: {viewer_id}")

@sio.on("image_type_changed")
def on_image_type_changed(data):
    global current_image_type
    img_type = data.get("type", "default")
    if img_type in images:
        current_image_type = img_type
        print(f"[BROADCASTER] Đã nhận lệnh đổi ảnh sang: {img_type}")
    else:
        print(f"[BROADCASTER] Loại ảnh không hợp lệ: {img_type}")

async def send_frames():
    print("[DEBUG] send_frames() started")
    while connected_viewers:
        b64 = get_current_frame()
        await sio.emit("image_frame", {"image": b64})
        await asyncio.sleep(0.2)
    print("[BROADCASTER] Stop sending frames (no viewer)")

async def main():
    await sio.connect("http://localhost:5000")
    await sio.wait()

asyncio.run(main())
