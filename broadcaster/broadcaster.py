import socketio
import base64
import asyncio
import cv2
from picamera2 import Picamera2
from PIL import Image
import io

sio = socketio.AsyncClient()
connected_viewers = set()
send_task = None

# Khởi tạo Picamera2
picam_rgb = Picamera2(0)  # cam1: RGB
picam_nir = Picamera2(1)  # cam2: NIR

picam_rgb.configure(picam_rgb.create_preview_configuration(main={"size": (640, 480)}))
picam_nir.configure(picam_nir.create_preview_configuration(main={"size": (640, 480)}))

picam_rgb.start()
picam_nir.start()

async def capture_frame():
    # Lấy ảnh từ cả 2 camera
    frame_rgb = picam_rgb.capture_array()
    frame_nir = picam_nir.capture_array()

    # Có thể chọn 1 trong 2 frame gửi
    # Hoặc ghép lại side-by-side nếu muốn
    combined = cv2.hconcat([frame_rgb, frame_nir])  # gửi ảnh ghép
    # combined = frame_rgb  # nếu chỉ muốn gửi RGB

    # Encode ảnh thành JPEG và base64
    _, buffer = cv2.imencode(".jpg", combined)
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
    await sio.connect("https://8878-2402-800-63b0-a777-bd8a-de4c-cdd7-b244.ngrok-free.app")
    await sio.wait()

asyncio.run(main())
