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
        showAlert("Vui lòng nhập tên của bạn", "warning");
        return;
    }
    savedUsername = username;
    socket.emit("join_viewer", { username });
}

// Lắng nghe kết quả
socket.on("username_error", (data) => {
    showAlert(data.message, "danger");
});

socket.on("join_success", () => {
    statusIndicator.classList.add("connected");
    statusText.textContent = `Connected as: ${savedUsername}`;

    loginScreen.classList.remove("active");
    viewerScreen.classList.add("active");
    document.getElementById("page-footer").style.display = "block";

    activatePanel('av');

    showAlert("🎉 Đã kết nối thành công!", "success");
});

socket.on("new_viewer", (data) => {
    showAlert(`👋 ${data.name} vừa tham gia phiên xem`, "info");
});

const colorMap = {
    danger: "var(--danger)",
    success: "var(--success)",
    warning: "var(--warning)",
    info: "var(--secondary)"
};

function showAlert(message, type = "danger") {
    console.log(`[showAlert] type: ${type}, message: ${message}`);
    const alert = document.createElement("div");

    alert.style.position = "fixed";
    alert.style.top = "20px";
    alert.style.left = "50%";
    alert.style.transform = "translateX(-50%)";
    alert.style.padding = "12px 24px";
    alert.style.borderRadius = "8px";
    alert.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
    alert.style.zIndex = "1000";
    alert.style.fontWeight = "500";
    alert.style.color = "white";
    alert.style.opacity = "1";
    alert.style.transition = "opacity 0.3s ease";

    // Apply background using var(...)
    alert.style.backgroundColor = colorMap[type] || colorMap.danger;
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
    statusText.textContent = "Connected to server";
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

        if (viewer.name === savedUsername) {
            nameSpan.style.fontWeight = "bold";
            nameSpan.style.color = "var(--primary-dark)"; // Hoặc màu khác tuỳ thích
            nameSpan.title = "Bạn";
        }

        // Nếu là host, thêm dấu sao
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

    usernameInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            submitUsername();
        }
    });
});

const btnCp = document.getElementById('btn-cp');
const btnAv = document.getElementById('btn-av');
const panelCp = document.getElementById('panel-cp');
const panelAv = document.getElementById('panel-av');

function activatePanel(type) {
    if (type === 'cp') {
        panelCp.style.display = 'block';
        panelAv.style.display = 'none';
        btnCp.classList.add('active');
        btnAv.classList.remove('active');
    } else {
        panelCp.style.display = 'none';
        panelAv.style.display = 'block';
        btnCp.classList.remove('active');
        btnAv.classList.add('active');
    }
}

btnCp.addEventListener('click', () => activatePanel('cp'));
btnAv.addEventListener('click', () => activatePanel('av'));
