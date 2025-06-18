# NDVI Drone Telemetry System 🌱

A real-time NDVI image streaming system using WebRTC and Socket.IO, designed for agriculture and remote vegetation monitoring.

## 📸 Features

- ✅ **Live NDVI drone image streaming**
- ✅ **Supports multiple image types**:
  - `default` (RGB),
  - `nir` (near-infrared),
  - `ndvi` (calculated)
- ✅ **Host-controlled image type** (viewers auto-sync)
- ✅ **Responsive UI**: works on desktop, mobile, tablet (e.g. Xiaomi MiPad 7)
- ✅ **Dynamic viewer list with host indication (⭐)**
- ✅ **Single broadcaster – multiple viewers model**
- ✅ **Username validation** (length + uniqueness)

---

## ⚙️ System Architecture

[Raspberry Pi / Broadcaster]
|
| Socket.IO (WebRTC signaling + image stream)
v
[Server: Python + aiohttp + socketio]
|
v
[Client Browsers: HTML/JS viewers]

---

## 🚀 How It Works

### 🛰 Broadcaster

- Connects to the server
- Waits for `image_type_request` from host
- Captures image (RGB / NIR / NDVI) accordingly
- Sends encoded frame via Socket.IO

### 👨‍🌾 Viewer

- Enters name (must be 3–10 characters, unique)
- First viewer becomes **Host**
- Host can select image type (dropdown menu)
- Other viewers auto-switch to the selected type
- Fullscreen supported on click

---

## 🛠 Technologies Used

- `Python 3`, `aiohttp`, `python-socketio`
- `HTML`, `CSS`, `JavaScript`, `Socket.IO client`
- Responsive layout with media queries

---

## 📁 Folder Structure

.
├── server.py # WebSocket + HTTP server
├── static/
│ ├── index.html # Main UI
│ ├── script.js # Socket logic (host/viewer)
│ └── style.css # Responsive UI
└── README.md

---

## 🧪 Development

Run the server:

```bash
python server.py

By default, opens at:
📡 http://localhost:5000

You can expose using tools like ngrok:

ngrok http 5000

📌 Future Improvements

    ⬜ NDVI processing on broadcaster side (Raspberry Pi)

    ⬜ Multi-room support

    ⬜ Viewer chat or reactions

    ⬜ Recording + storage (optional)

📚 Author

Graduation Thesis –
Faculty of Electronics and Telecommunications
Can Tho University

Designed by Thành TSM
```
