import asyncio
import cv2
import numpy as np
import socketio
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCIceCandidate, RTCConfiguration, RTCIceServer
from av import VideoFrame

sio = socketio.AsyncClient()
pcs = {}
current_image_type = "default"

# Load ảnh tượng trưng
images = {
    "default": cv2.imread("imgs/rgb.png"),
    "nir":     cv2.imread("imgs/nir.png"),
    "ndvi":    cv2.imread("imgs/ndvi.png")
}
for k, img in images.items():
    if img is None:
        raise RuntimeError(f"Ảnh {k}.png không tồn tại!")

class VideoStreamTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()

    async def recv(self):
        global current_image_type
        img = images[current_image_type]

        # Đảm bảo ảnh có đúng kích thước và format BGR
        if img is None:
            raise Exception("No image loaded!")

        # Chuyển ảnh OpenCV sang VideoFrame
        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts, frame.time_base = await self.next_timestamp()

        return frame

@sio.event
async def connect():
    print("[BROADCASTER] ✅ Đã kết nối đến signaling server")
    print("📡 Socket ID:", sio.sid)
    await sio.emit("join_broadcaster")

@sio.on("viewer_joined")
async def on_viewer_joined(data):
    viewer_id = data["viewer_id"]
    print(f"[BROADCASTER] 👤 Viewer joined: {viewer_id}")

    ice_servers = [
    RTCIceServer(urls="stun:stun.l.google.com:19302"),
    RTCIceServer(
        urls=[
            "stun:stun.metered.ca:80",
            "turn:turn.metered.ca:80",
            "turn:turn.metered.ca:443",
            "turns:turn.metered.ca:443?transport=tcp"
        ],
        username="openai",
        credential="webrtc"
    )]
    config = RTCConfiguration(iceServers=ice_servers)
    pc = RTCPeerConnection(configuration=config)
    
    pcs[viewer_id] = pc

    pc.addTrack(VideoStreamTrack())

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

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    await sio.emit("offer", {
        "target": viewer_id,
        "description": {
            "type": pc.localDescription.type,
            "sdp": pc.localDescription.sdp
        }
    })
    print(f"[BROADCASTER] 📩 Sent offer to {viewer_id}")
    
@sio.on("answer")
async def on_answer(data):
    viewer_id = data["from"]
    description = data["description"]
    pc = pcs.get(viewer_id)

    print(f"[BROADCASTER] 📥 Received answer from {viewer_id}")
    print(f"[BROADCASTER]    SDP type: {description['type']}")
    print(f"[BROADCASTER]    SDP first 200 chars:\n{description['sdp'][:200]}")

    if pc:
        try:
            await pc.setRemoteDescription(
                RTCSessionDescription(sdp=description["sdp"], type=description["type"])
            )
            print(f"[BROADCASTER] ✅ setRemoteDescription success for {viewer_id}")
        except Exception as e:
            print(f"[BROADCASTER] ❌ Error setting remote description for {viewer_id}: {e}")
    else:
        print(f"[BROADCASTER] ⚠️ No peer connection found for {viewer_id}")


@sio.event
async def on_candidate(data):
    viewer_id = data.get("from")
    candidate = data.get("candidate")
    pc = pcs.get(viewer_id)

    if pc and candidate:
        print(f"[BROADCASTER] 📩 Received ICE from {viewer_id}")
        await pc.addIceCandidate(RTCIceCandidate(
            sdpMid=candidate["sdpMid"],
            sdpMLineIndex=candidate["sdpMLineIndex"],
            candidate=candidate["candidate"]
        ))

@sio.on("image_type_changed")
def on_image_type_changed(data):
    global current_image_type
    t = data.get("type", "default")
    if t in images:
        current_image_type = t
        print(f"[BROADCASTER] 🔄 Đã chuyển sang ảnh: {t}")

async def main():
    while True:
        try:
            await sio.connect("https://vindvi.ap.ngrok.io/")
            await sio.wait()
        except Exception as e:
            print(f"[❌ ERROR] Kết nối server thất bại: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
