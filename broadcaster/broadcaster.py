import asyncio
import socketio
import cv2
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer, VideoStreamTrack
from av import VideoFrame
from aiortc.sdp import candidate_from_sdp
from picamera2 import Picamera2
import threading
import time

# ==== TURN/STUN Configuration ====
ICE_SERVERS = [
    RTCIceServer(urls=['stun:global.stun.twilio.com:3478']),
    RTCIceServer(
        urls=[
            'turn:global.turn.twilio.com:3478?transport=udp',
            'turn:global.turn.twilio.com:3478?transport=tcp',
            'turn:global.turn.twilio.com:443?transport=tcp',
        ],
        username='e6cc068f3ad53c8733550f71a82a4fef33edd4e993625db6168901f1288dd960',
        credential='iOTDpkraJq+JmfJ1tf7S4YLY553Tdk8FRBSRt8N1loE='
    ),
]
config = RTCConfiguration(iceServers=ICE_SERVERS)
pcs = {}
pending_candidates = {}
current_image_type = "default"

# ==== NDVI Default Image ====
ndvi_image = cv2.imread("imgs/ndvi.png")
if ndvi_image is None:
    raise RuntimeError("Ảnh 'ndvi.png' không tồn tại trong thư mục imgs/")

# === CameraCapture class ===
class CameraCapture:
    def __init__(self, camera_id):
        # Initialize Picamera2 for given camera index
        self.picam2 = Picamera2(camera_num=camera_id)
        camera_config = self.picam2.create_preview_configuration(
            main={"format": "RGB888", "size": (1536, 864)},
        )
        self.picam2.configure(camera_config)
        self.picam2.start()
        self.frame = None
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _capture_loop(self):
        while self.running:
            frame = self.picam2.capture_array()
            with self.lock:
                self.frame = frame
            time.sleep(0.001)

    def read(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self):
        self.running = False
        self.thread.join()
        # Stop and close camera to free resource
        self.picam2.stop()
        self.picam2.close()

# === CameraManager to handle single active camera ===
class CameraManager:
    def __init__(self):
        self.current_cam = None
        self.active_type = None

    def switch(self, camera_type):
        if self.active_type == camera_type:
            return

        if self.current_cam:
            self.current_cam.stop()
            time.sleep(0.05)
            self.current_cam = None

        if camera_type == "rgb":
            self.current_cam = CameraCapture(camera_id=0)
            self.active_type = "rgb"
        elif camera_type == "nir":
            self.current_cam = CameraCapture(camera_id=1)
            self.active_type = "nir"
        else:
            self.active_type = "default"
            self.current_cam = None

    def read(self):
        if self.current_cam:
            return self.current_cam.read()
        return None

# Instantiate manager, no camera open initially
cam_manager = CameraManager()

# === Custom Video Track from Camera / Static NDVI ===
class DynamicImageStream(VideoStreamTrack):
    kind = "video"
    def __init__(self):
        super().__init__()
        self._interval = 1 / 60 

    async def recv(self):
        global current_image_type
        pts, time_base = await self.next_timestamp()

        if current_image_type in ("rgb", "nir"):
            cam_manager.switch(current_image_type)
            img = cam_manager.read()
        else:
            img = ndvi_image.copy()

        if img is None:
            img = ndvi_image.copy()

        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        await asyncio.sleep(self._interval)
        return frame

# === Socket.IO + WebRTC ===

sio = socketio.AsyncClient()

@sio.event
async def connect():
    print("Connected to signaling server")
    print("Broadcaster ID:", sio.sid)
    await sio.emit("join_broadcaster")

@sio.on("viewer_joined")
async def on_viewer_joined(data):
    viewer_id = data["viewer_id"]
    print(f"Viewer joined: {viewer_id}")

    pc = RTCPeerConnection(configuration=config)
    pcs[viewer_id] = pc
    pc.addTrack(DynamicImageStream())

    @pc.on("icecandidate")
    async def on_icecandidate(event):
        if event.candidate:
            await sio.emit("candidate", {
                "target": viewer_id,
                "candidate": {
                    "candidate": event.candidate.to_sdp(),
                    "sdpMid": event.candidate.sdp_mid,
                    "sdpMLineIndex": event.candidate.sdp_mline_index
                }
            })

    @pc.on("iceconnectionstatechange")
    async def on_state():
        print(f"ICE state for {viewer_id}: {pc.iceConnectionState}")
        if pc.iceConnectionState in ["disconnected", "failed", "closed"]:
            print(f"Closing connection with {viewer_id}")
            await pc.close()
            pcs.pop(viewer_id, None)

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    print(f"Sending offer to {viewer_id}")
    await sio.emit("offer", {
        "target": viewer_id,
        "description": {
            "type": pc.localDescription.type,
            "sdp": pc.localDescription.sdp
        }
    })

@sio.on("answer")
async def on_answer(data):
    viewer_id = data["from"]
    pc = pcs.get(viewer_id)
    print(f"Answer received from {viewer_id}")
    if pc:
        await pc.setRemoteDescription(RTCSessionDescription(
            sdp=data["description"]["sdp"],
            type=data["description"]["type"]
        ))
        for ice in pending_candidates.pop(viewer_id, []):
            await pc.addIceCandidate(ice)
            print(f"Queued ICE added for {viewer_id}")
    else:
        print(f"No peer for {viewer_id} when answer received")

@sio.on("candidate")
async def on_candidate(data):
    viewer_id = data["from"]
    cand = data.get("candidate")
    pc = pcs.get(viewer_id)
    if not pc or not cand:
        print(f"No peer to handle ICE from {viewer_id}")
        return

    raw = cand["candidate"].strip()
    if not raw.startswith("candidate:"):
        print(f"Ignored malformed ICE from {viewer_id}: {raw!r}")
        return

    ice = candidate_from_sdp(raw)
    ice.sdpMid = cand["sdpMid"]
    ice.sdpMLineIndex = cand["sdpMLineIndex"]

    if pc.remoteDescription is None:
        print(f"ICE queued for {viewer_id}")
        pending_candidates.setdefault(viewer_id, []).append(ice)
    else:
        await pc.addIceCandidate(ice)
        print(f"ICE added for {viewer_id}")

@sio.on("image_type_changed")
def on_image_type_changed(data):
    global current_image_type
    t = data.get("type", "default")
    if t in ("rgb", "nir", "default"):
        current_image_type = t
        print(f" Đã chuyển ảnh sang: {t}")

# === Main loop ===
async def main():
    while True:
        try:
            await sio.connect("https://vindvi.ap.ngrok.io/")
            await sio.wait()
        except Exception as e:
            print(f"Kết nối thất bại: {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        # Ensure camera is closed on exit
        cam_manager.switch(None)
