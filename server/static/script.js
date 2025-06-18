const socket = io();
const loginScreen = document.getElementById("login-screen");
const viewerScreen = document.getElementById("viewer-screen");
const usernameInput = document.getElementById("username");
const status = document.getElementById("status");
const statusIndicator = status.querySelector(".status-indicator");
const statusText = status.querySelector("span");
const video = document.getElementById("video");
const waiting = document.getElementById("waiting");
const placeholder = document.getElementById("placeholder");
const viewerCount = document.getElementById("viewer-count");
const viewerList = document.getElementById("viewer-list");

let savedUsername = "";

function submitUsername() {
    const username = usernameInput.value.trim();
    if (!username) {
        showAlert("Please enter your name");
        return;
    }
    savedUsername = username;
    socket.emit("join_viewer", { username });
    // không tự chuyển màn ở đây nữa
}

// Lắng nghe kết quả
socket.on("username_error", (data) => {
    showAlert(data.message);
});

socket.on("join_success", () => {
    // Update status
    statusIndicator.classList.add("connected");
    statusText.textContent = `Connected as: ${savedUsername}`;
    // Transition to viewer screen
    loginScreen.classList.remove("active");
    viewerScreen.classList.add("active");
    document.getElementById("page-footer").style.display = "block";
});

function showAlert(message) {
    const alert = document.createElement("div");
    alert.style.position = "fixed";
    alert.style.top = "20px";
    alert.style.left = "50%";
    alert.style.transform = "translateX(-50%)";
    alert.style.backgroundColor = "var(--danger)";
    alert.style.color = "white";
    alert.style.padding = "12px 24px";
    alert.style.borderRadius = "8px";
    alert.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
    alert.style.zIndex = "1000";
    alert.style.fontWeight = "500";
    alert.textContent = message;

    document.body.appendChild(alert);

    setTimeout(() => {
        alert.style.opacity = "0";
        setTimeout(() => {
            document.body.removeChild(alert);
        }, 300);
    }, 3000);
}

socket.on("re_authenticate", () => {
    if (savedUsername) {
        console.log("[Viewer] Re-authenticating as", savedUsername);
        socket.emit("join_viewer", { username: savedUsername });
        statusText.textContent = `Reconnected as: ${savedUsername}`;
    }
});

socket.on("connect", () => {
    console.log("[Viewer] connected:", socket.id);
    statusIndicator.classList.add("connected");
    statusText.textContent = savedUsername
        ? `Connected as: ${savedUsername}`
        : "Connected";
});

socket.on("disconnect", () => {
    statusIndicator.classList.remove("connected");
    statusText.textContent = "Connection lost - Reconnecting...";
});

socket.on("image_frame", (data) => {
    video.src = "data:image/jpeg;base64," + data.image;
    video.style.display = "block";
    waiting.style.display = "none";
    placeholder.style.display = "none";
});

socket.on("peer_disconnect", () => {
    video.style.display = "none";
    placeholder.style.display = "flex";
    waiting.style.display = "none";
});

socket.on("no_broadcaster", () => {
    video.style.display = "none";
    placeholder.style.display = "flex";
    waiting.style.display = "flex";
});

socket.on("viewer_list", (data) => {
    viewerCount.textContent = data.count;
    viewerList.innerHTML = "";

    data.viewers.forEach((viewer) => {
        const li = document.createElement("li");

        const icon = document.createElement("div");
        icon.className = "viewer-icon";
        icon.textContent = viewer.name.charAt(0).toUpperCase();

        const nameSpan = document.createElement("span");
        nameSpan.textContent = viewer.name;

        if (viewer.is_host) {
            const star = document.createElement("span");
            star.textContent = " ⭐";
            star.style.color = "#ffc107";
            star.title = "Host";
            nameSpan.appendChild(star);
        }

        li.appendChild(icon);
        li.appendChild(nameSpan);
        viewerList.appendChild(li);
    });
});

video.addEventListener("click", () => {
    video.classList.toggle("fullscreen");

    // Add close button in fullscreen mode
    if (video.classList.contains("fullscreen")) {
        const closeBtn = document.createElement("div");
        closeBtn.textContent = "✕";
        closeBtn.style.position = "fixed";
        closeBtn.style.top = "20px";
        closeBtn.style.right = "20px";
        closeBtn.style.color = "white";
        closeBtn.style.fontSize = "24px";
        closeBtn.style.cursor = "pointer";
        closeBtn.style.zIndex = "1001";
        closeBtn.style.width = "40px";
        closeBtn.style.height = "40px";
        closeBtn.style.display = "flex";
        closeBtn.style.alignItems = "center";
        closeBtn.style.justifyContent = "center";
        closeBtn.style.background = "rgba(255,255,255,0.2)";
        closeBtn.style.borderRadius = "50%";
        closeBtn.addEventListener("click", () => {
            video.classList.remove("fullscreen");
            document.body.removeChild(closeBtn);
        });

        document.body.appendChild(closeBtn);
    }
});

// Initialize placeholder
placeholder.style.display = "flex";
waiting.style.display = "none";
video.style.display = "none";

// Focus username input on load
window.addEventListener("load", () => {
    usernameInput.focus();
});

window.addEventListener("load", () => {
    usernameInput.focus();

    // 👉 Cho phép nhấn Enter để gửi username
    usernameInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            submitUsername();
        }
    });
});