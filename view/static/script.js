console.log("✅ script.js loaded");

const socket = io();

const loginScreen = document.getElementById("login-screen");
const viewerScreen = document.getElementById("viewer-screen");
const usernameInput = document.getElementById("username");
const status = document.getElementById("status");
const statusIndicator = status.querySelector(".status-indicator");
const statusText = status.querySelector("span");

const streamImg = document.getElementById("stream-img");
const videoPlaceholder = document.getElementById("video-placeholder");
const waiting = document.getElementById("waiting");

const viewerCount = document.getElementById("viewer-count");
const viewerList = document.getElementById("viewer-list");
const imageSelectorWrapper = document.getElementById("image-selector-wrapper");
const imageSelector = document.getElementById("image-type");

let isHost = false;
let savedUsername = "";
let alertActive = false;
const alertQueue = [];

function updateViewerList(viewers, currentHostId, myId) {
    const list = document.getElementById("viewer-list");
    list.innerHTML = "";

    viewers.forEach((viewer) => {
        const li = document.createElement("li");
        li.textContent = viewer.name;

        if (myId === currentHostId && viewer.id !== myId) {
            li.style.cursor = "pointer";
            li.title = "Click to transfer host";
            li.onclick = () => {
                const confirmTransfer = confirm(
                    `Transfer host role to ${viewer.name}?`
                );
                if (confirmTransfer) {
                    socket.emit("transfer_host", { targetId: viewer.id });
                }
            };
        }

        // Đánh dấu host hiện tại
        if (viewer.id === currentHostId) {
            li.style.fontWeight = "bold";
            li.textContent += " (Host)";
        }

        list.appendChild(li);
    });
}

socket.on("host_updated", (data) => {
    const newHostId = data.hostId;
    isHost = (socket.id === newHostId);
    console.log("[CLIENT] Host_update: ", newHostId, isHost);
    updateHostUI(isHost);
});

function safeDisplay(el, display = "block") {
    if (el) el.style.display = display;
}

function updateImageSelectorAccess() {

    if (!isHost) {
        imageChoices.disable();
        imageSelector.title = "Chỉ host mới có thể thay đổi loại ảnh";
    } else {
        imageChoices.enable();
        imageSelector.title = "";
    }
}

function updateHostUI(isHostNow) {
    isHost = isHostNow;

    if (isHostNow) {
        imageSelectorWrapper.style.display = "block";
        imageSelector.disabled = false;
        showAlert("🎖️ Bạn là Host mới", "info");

        setTimeout(() => {
            activatePanel("cp");
        }, 2300);
    } else {
        imageSelectorWrapper.style.display = "block";
        imageSelector.disabled = true;
    }
    updateImageSelectorAccess();
}

// Fullscreen toggle for both videos
[streamImg, videoPlaceholder].forEach((vid) => {
    vid.addEventListener("click", () => {
        if (!document.fullscreenElement) {
            vid.requestFullscreen().catch((err) =>
                console.error(`❌ Failed to fullscreen: ${err.message}`)
            );
        } else {
            document.exitFullscreen();
        }
    });
});

// Broadcaster connected
socket.on("broadcaster_connected", () => {
    console.log("📡 Broadcaster đã kết nối");
    safeDisplay(waiting, "none");
    safeDisplay(streamImg, "block");
    safeDisplay(videoPlaceholder, "none");
});

socket.on("image_type_changed", ({ type }) => {
    if (imageChoices) {
        imageChoices.setChoiceByValue(type);
    } else {
        imageSelector.value = type; // fallback nếu Choices chưa được khởi tạo
    }
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
    savedUsername = username;
    socket.emit("join_viewer", { username });
}

// Xử lý sự kiện khi lỗi tên
socket.on("username_error", (data) => {
    showAlert(data.message, "danger");
    usernameInput.classList.add("shake");
    setTimeout(() => {
        usernameInput.classList.remove("shake");
    }, 300);
});

socket.on("join_success", ({ username }) => {

    savedUsername = username;
    localStorage.setItem("ndvi-username", savedUsername);

    statusIndicator.classList.add("connected");
    statusText.textContent = `Connected as: ${savedUsername}`;

    loginScreen.classList.add("fade-out");

    showAlert("🎉 Join success!", "success");
    activatePanel("av");

    if (!isHost) {
        imageSelectorWrapper.style.display = "block";
        imageSelector.disabled = true;
    }

    const header = document.getElementById("top-header");
    const footer = document.getElementById("page-footer");
    const main = document.getElementById("main");

    setTimeout(() => {
        header.classList.add("hide-header-anim");
        footer.classList.add("hide-footer-anim");
    }, 50);

    setTimeout(() => {
        header.style.display = "none";
        footer.style.display = "none";
        main.classList.add("fullscreen");

        setTimeout(() => {
            viewerScreen.classList.add("active");
            viewerScreen.classList.add("animate-viewscreen");
            loginScreen.classList.remove("fade-out");
            loginScreen.classList.remove("active");
        }, 300);
    }, 600);
});

// Viewer mới
socket.on("new_viewer", (data) => {
    showAlert(`👋 ${data.name} vừa tham gia phiên xem`, "info");
});

// Danh sách viewer
socket.on("viewer_list", ({ viewers, count, hostId }) => {
    viewerCount.textContent = count;
    viewerList.innerHTML = "";

    // Cập nhật lại trạng thái host
    isHost = (socket.id === hostId);
    updateImageSelectorAccess();

    viewers.forEach((viewer) => {
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

        // Nếu là host và viewer khác bạn thì có thể nhấn để chuyển quyền
        if (isHost && viewer.name !== savedUsername) {
            li.style.cursor = "pointer";
            li.title = `Nhấn để nhượng quyền host cho ${viewer.name}`;
            li.onclick = () => {
                const ok = confirm(`Bạn có chắc muốn nhượng quyền host cho ${viewer.name}?`);
                if (ok) {
                    socket.emit("transfer_host", { targetId: viewer.id });
                }
            };
        }

        li.appendChild(icon);
        li.appendChild(nameSpan);
        viewerList.appendChild(li);
    });
});

// Khi nhận được frame từ broadcaster (chỉ dùng cho MJPEG stream base64)
socket.on("image_frame", (data) => {

    streamImg.src = "data:image/jpeg;base64," + data.image;
    safeDisplay(waiting, "none");
    safeDisplay(streamImg, "block");
    safeDisplay(videoPlaceholder, "none");
});

// Broadcaster rời đi
socket.on("peer_disconnect", () => {
    safeDisplay(waiting, "none");
    safeDisplay(streamImg, "none");
    safeDisplay(videoPlaceholder, "block");
});

// Chưa có broadcaster
socket.on("no_broadcaster", () => {
    safeDisplay(waiting, "flex");
    safeDisplay(streamImg, "none");
    safeDisplay(videoPlaceholder, "block");
});

// Trạng thái kết nối
socket.on("connect", () => {
    console.log("[Viewer] connected:", socket.id);
    statusIndicator.classList.add("connected");
    statusText.textContent = "Connected to server";
});

socket.on("disconnect", () => {
    statusIndicator.classList.remove("connected");
    statusText.textContent = "Connection lost - Reconnecting...";
    document.getElementById("top-header").classList.remove("animate-header");
    document.getElementById("main").classList.remove("animate-main");
    document.getElementById("page-footer").classList.remove("animate-footer");
});

socket.on("re_authenticate", () => {
    if (savedUsername) {
        socket.emit("join_viewer", { username: savedUsername });
        statusText.textContent = `Reconnected as: ${savedUsername}`;
    }
});

function showAlert(message, type = "danger") {
    alertQueue.push({ message, type });
    if (!alertActive) {
        processNextAlert();
    }
}

function processNextAlert() {
    if (alertQueue.length === 0) {
        alertActive = false;
        return;
    }

    alertActive = true;
    const { message, type } = alertQueue.shift();

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
            processNextAlert(); // ✅ Hiển thị alert tiếp theo
        }, 300);
    }, 2000);
}

// Panel toggle
const btnCp = document.getElementById("btn-cp");
const btnAv = document.getElementById("btn-av");
const panelCp = document.getElementById("panel-cp");
const panelAv = document.getElementById("panel-av");

function activatePanel(type) {
    console.log(`[activatePanel] Switching to panel: ${type}`);
    const panelCp = document.getElementById("panel-cp");
    const panelAv = document.getElementById("panel-av");

    const toHide = (type === "cp") ? panelAv : panelCp;
    const toShow = (type === "cp") ? panelCp : panelAv;

    btnCp.classList.toggle("active", type === "cp");
    btnAv.classList.toggle("active", type === "av");

    toHide.classList.remove("fade-in-panel");
    toHide.classList.add("fade-out-panel");

    setTimeout(() => {
        toHide.style.display = "none";

        toShow.style.display = "block";
        toShow.classList.remove("fade-out-panel");
        toShow.classList.add("fade-in-panel");
    }, 300); // trễ 1 chút để chờ fadeOut chạy xong
}

btnCp.addEventListener("click", () => activatePanel("cp"));
btnAv.addEventListener("click", () => activatePanel("av"));

// Init
let imageChoices;
window.addEventListener("load", () => {
    imageChoices = new Choices("#image-type", {
        searchEnabled: false,
        itemSelectText: "",
        shouldSort: false,
    });

    usernameInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") submitUsername();
    });

    safeDisplay(waiting, "none");
    safeDisplay(streamImg, "none");
    safeDisplay(videoPlaceholder, "block");
});

const header = document.getElementById("top-header");
const main = document.getElementById("main");
const footer = document.getElementById("page-footer");

header.classList.remove("animate-header");
main.classList.remove("animate-main");
footer.classList.remove("animate-footer");

void header.offsetWidth;
void main.offsetWidth;
void footer.offsetWidth;

header.classList.add("animate-header");
main.classList.add("animate-main");
footer.classList.add("animate-footer");