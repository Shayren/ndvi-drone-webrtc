console.log("✅ script.js loaded");

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
const imageSelectorWrapper = document.getElementById("image-selector-wrapper");
const imageSelector = document.getElementById("image-type");

let isHost = false;
let savedUsername = "";

socket.on("broadcaster_connected", () => {
    console.log("📡 Broadcaster đã kết nối");
    waiting.style.display = "none";
    placeholder.style.display = "none";
});

socket.on("you_are_host", () => {
    console.log("[CLIENT] You are host!");
    isHost = true;

    document.getElementById("panel-cp").style.display = "block";
    imageSelectorWrapper.style.display = "block";
    imageSelector.disabled = false;

    activatePanel('cp');
});

socket.on("image_type_changed", ({ type }) => {
    imageSelector.value = type;
});

imageSelector.addEventListener("change", () => {
    if (isHost) {
        const selectedType = imageSelector.value;
        socket.emit("change_image_type", { type: selectedType });
        console.log(`[HOST] Changed image type to: ${selectedType}`);
    }
});

function submitUsername() {
    const username = usernameInput.value.trim();
    if (!username) {
        showAlert("Vui lòng nhập tên của bạn", "warning");
        return;
    }
    savedUsername = username;
    socket.emit("join_viewer", { username });
}

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
    showAlert("🎉 Join success!", "success");

    if (!isHost) {
        imageSelectorWrapper.style.display = "block";
        imageSelector.disabled = true;
    }
});

socket.on("new_viewer", (data) => {
    showAlert(`👋 ${data.name} vừa tham gia phiên xem`, "info");
});

socket.on("viewer_list", (data) => {
    viewerCount.textContent = data.count;
    viewerList.innerHTML = "";
    data.viewers.forEach(viewer => {
        const li = document.createElement("li");
        const icon = document.createElement("div");
        icon.className = "viewer-icon";
        icon.textContent = viewer.name.charAt(0).toUpperCase();

        const nameSpan = document.createElement("span");
        nameSpan.textContent = viewer.name;

        if (viewer.name === savedUsername) {
            nameSpan.style.fontWeight = "bold";
            nameSpan.style.color = "var(--primary-dark)";
            nameSpan.title = "Bạn";
        }

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

socket.on("connect", () => {
    console.log("[Viewer] connected:", socket.id);
    statusIndicator.classList.add("connected");
    statusText.textContent = "Connected to server";
});

socket.on("disconnect", () => {
    statusIndicator.classList.remove("connected");
    statusText.textContent = "Connection lost - Reconnecting...";
});

socket.on("re_authenticate", () => {
    if (savedUsername) {
        socket.emit("join_viewer", { username: savedUsername });
        statusText.textContent = `Reconnected as: ${savedUsername}`;
    }
});

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
    alert.style.backgroundColor = {
        danger: "var(--danger)",
        success: "var(--success)",
        warning: "var(--warning)",
        info: "var(--secondary)"
    }[type] || "var(--danger)";
    alert.textContent = message;

    document.body.appendChild(alert);

    setTimeout(() => {
        alert.style.opacity = "0";
        setTimeout(() => {
            document.body.removeChild(alert);
        }, 300);
    }, 3000);
}

// Fullscreen toggle
video.addEventListener("click", () => {
    video.classList.toggle("fullscreen");
    if (video.classList.contains("fullscreen")) {
        const closeBtn = document.createElement("div");
        closeBtn.textContent = "✕";
        Object.assign(closeBtn.style, {
            position: "fixed",
            top: "20px",
            right: "20px",
            color: "white",
            fontSize: "24px",
            cursor: "pointer",
            zIndex: "1001",
            width: "40px",
            height: "40px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(255,255,255,0.2)",
            borderRadius: "50%",
        });
        closeBtn.onclick = () => {
            video.classList.remove("fullscreen");
            document.body.removeChild(closeBtn);
        };
        document.body.appendChild(closeBtn);
    }
});

// Panel toggle
const btnCp = document.getElementById("btn-cp");
const btnAv = document.getElementById("btn-av");
const panelCp = document.getElementById("panel-cp");
const panelAv = document.getElementById("panel-av");

function activatePanel(type) {
    if (type === "cp") {
        panelCp.style.display = "block";
        panelAv.style.display = "none";
        btnCp.classList.add("active");
        btnAv.classList.remove("active");
    } else {
        panelCp.style.display = "none";
        panelAv.style.display = "block";
        btnCp.classList.remove("active");
        btnAv.classList.add("active");
    }
}

btnCp.addEventListener("click", () => activatePanel("cp"));
btnAv.addEventListener("click", () => activatePanel("av"));

// Init
window.addEventListener("load", () => {
    usernameInput.focus();
    usernameInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") submitUsername();
    });
    placeholder.style.display = "flex";
    waiting.style.display = "none";
    video.style.display = "none";
});
