(() => {
  let currentVideoId = null;

  // ---------------- Elements ----------------
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanels = document.querySelectorAll(".tab-panel");

  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const uploadBtn = document.getElementById("uploadBtn");

  const urlInput = document.getElementById("urlInput");
  const fetchUrlBtn = document.getElementById("fetchUrlBtn");

  const sourceStatus = document.getElementById("sourceStatus");
  const settingsCard = document.getElementById("settingsCard");
  const resultCard = document.getElementById("resultCard");
  const errorBox = document.getElementById("errorBox");

  const intervalValue = document.getElementById("intervalValue");
  const intervalUnit = document.getElementById("intervalUnit");
  const formatSelect = document.getElementById("formatSelect");
  const fpsHint = document.getElementById("fpsHint");

  const extractBtn = document.getElementById("extractBtn");
  const progressWrap = document.getElementById("progressWrap");
  const progressFill = document.getElementById("progressFill");
  const progressLabel = document.getElementById("progressLabel");

  const resultSummary = document.getElementById("resultSummary");
  const downloadLink = document.getElementById("downloadLink");

  // ---------------- Tabs ----------------
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      tabPanels.forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(btn.dataset.tab).classList.add("active");
      hideError();
    });
  });

  // ---------------- Helpers ----------------
  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.remove("hidden");
  }
  function hideError() {
    errorBox.classList.add("hidden");
  }
  function showStatus(msg) {
    sourceStatus.textContent = msg;
    sourceStatus.classList.remove("hidden");
  }
  function resetDownstream() {
    settingsCard.style.display = "none";
    resultCard.style.display = "none";
    progressWrap.classList.add("hidden");
  }
  function updateFpsHint() {
    const val = parseFloat(intervalValue.value);
    if (!val || val <= 0) { fpsHint.textContent = ""; return; }
    const seconds = intervalUnit.value === "milliseconds" ? val / 1000 : val;
    const fps = 1 / seconds;
    fpsHint.textContent = `≈ ${fps.toFixed(3)} frame(s) captured per second of video`;
  }
  intervalValue.addEventListener("input", updateFpsHint);
  intervalUnit.addEventListener("change", updateFpsHint);
  updateFpsHint();

  // ---------------- File upload ----------------
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-over");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      onFileSelected();
    }
  });
  fileInput.addEventListener("change", onFileSelected);

  function onFileSelected() {
    hideError();
    if (fileInput.files.length) {
      uploadBtn.disabled = false;
      const f = fileInput.files[0];
      dropzone.querySelector(".dropzone-inner p strong").textContent = f.name;
    }
  }

  uploadBtn.addEventListener("click", async () => {
    if (!fileInput.files.length) return;
    hideError();
    resetDownstream();
    uploadBtn.disabled = true;
    uploadBtn.textContent = "Uploading…";

    const formData = new FormData();
    formData.append("video", fileInput.files[0]);

    try {
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Upload failed");

      currentVideoId = data.video_id;
      showStatus(`Loaded: ${data.filename} (${(data.size_bytes / (1024*1024)).toFixed(2)} MB)`);
      settingsCard.style.display = "block";
    } catch (err) {
      showError(err.message);
    } finally {
      uploadBtn.disabled = false;
      uploadBtn.textContent = "Upload Video";
    }
  });

  // ---------------- URL fetch ----------------
  fetchUrlBtn.addEventListener("click", async () => {
    const url = urlInput.value.trim();
    if (!url) { showError("Please paste a video URL first."); return; }
    hideError();
    resetDownstream();
    fetchUrlBtn.disabled = true;
    fetchUrlBtn.textContent = "Fetching…";

    try {
      const res = await fetch("/api/fetch-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to fetch video");

      currentVideoId = data.video_id;
      showStatus(`Loaded: ${data.filename}${data.duration ? ` (${Math.round(data.duration)}s)` : ""}`);
      settingsCard.style.display = "block";
    } catch (err) {
      showError(err.message);
    } finally {
      fetchUrlBtn.disabled = false;
      fetchUrlBtn.textContent = "Fetch Video";
    }
  });

  // ---------------- Extraction ----------------
  extractBtn.addEventListener("click", async () => {
    if (!currentVideoId) { showError("Load a video first."); return; }
    const val = parseFloat(intervalValue.value);
    if (!val || val <= 0) { showError("Enter a valid interval greater than 0."); return; }

    hideError();
    resultCard.style.display = "none";
    progressWrap.classList.remove("hidden");
    progressFill.style.width = "10%";
    progressLabel.textContent = "Extracting frames — this can take a while for long videos…";
    extractBtn.disabled = true;

    // simple animated progress (extraction itself is a single blocking request)
    let fake = 10;
    const ticker = setInterval(() => {
      fake = Math.min(fake + Math.random() * 8, 90);
      progressFill.style.width = fake + "%";
    }, 500);

    try {
      const res = await fetch("/api/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_id: currentVideoId,
          interval_value: val,
          interval_unit: intervalUnit.value,
          format: formatSelect.value
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Extraction failed");

      clearInterval(ticker);
      progressFill.style.width = "100%";
      progressLabel.textContent = "Done!";

      resultSummary.textContent =
        `${data.frame_count} frame(s) extracted as .${data.format}. Ready to download.`;
      downloadLink.href = data.download_url;
      resultCard.style.display = "block";
    } catch (err) {
      clearInterval(ticker);
      progressWrap.classList.add("hidden");
      showError(err.message);
    } finally {
      extractBtn.disabled = false;
    }
  });
})();
