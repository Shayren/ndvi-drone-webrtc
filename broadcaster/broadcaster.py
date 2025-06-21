import socketio
import base64
import asyncio
import cv2

sio = socketio.AsyncClient()
connected_viewers = set()
send_task = None

# Đọc ảnh RGB từ file (một lần duy nhất)
rgb_image = cv2.imread("imgs/rgb.jpg")
if rgb_image is None:
    raise FileNotFoundError("Không tìm thấy file 'rgb.jpg'")

async def capture_frame():
    # Encode ảnh thành JPEG và base64
    _, buffer = cv2.imencode(".jpg", rgb_image)
    b64_frame = base64.b64encode(buffer).decode('utf-8')
    return b64_frame

@sio.event
async def connect():
    print("[BROADCASTER] Connected to server")
    await sio.emit("join_broadcaster")

@sio.event
async def viewer_joined(data):
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

async def send_frames():
    while connected_viewers:
        b64 = await capture_frame()
        await sio.emit("image_frame", {"image": b64})
        await asyncio.sleep(0.2)  # 5 FPS (tuỳ chỉnh)

    print("[BROADCASTER] Stop sending frames (no viewer)")

async def main():
    await sio.connect("http://localhost:5000")  # hoặc ngrok URL
    await sio.wait()

asyncio.run(main())
