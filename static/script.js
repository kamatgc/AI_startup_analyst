document.getElementById("downloadMemoBtn").disabled = true;

function getTimestamp() {
  const now = new Date();
  return now.toLocaleTimeString("en-GB", { hour12: false });
}

function appendStatus(message) {
  const statusBox = document.getElementById("status");
  const entry = document.createElement("div");
  entry.textContent = `[${getTimestamp()}] ${message}`;
  statusBox.appendChild(entry);
}

document.getElementById("analyzeBtn").onclick = async () => {
  const file = document.getElementById("fileInput").files[0];
  if (!file) {
    appendStatus("Please select a PDF file.");
    return;
  }

  if (!navigator.onLine) {
    appendStatus("⚠️ You appear to be offline. Please check your connection.");
    return;
  }

  document.getElementById("status").innerHTML = "";
  appendStatus("Uploading pitch deck...");
  document.getElementById("downloadMemoBtn").disabled = true;

  const formData = new FormData();
  formData.append("file", file);

  const tryFetch = async (attempt = 1) => {
    try {
      const res = await fetch("/analyze", { method: "POST", body: formData });
      const data = await res.json();
      let memo = data.memo || "⚠️ No memo generated.";
      const statusUpdates = data.status_updates || [];

      const container = document.getElementById("memo-output");
      container.innerHTML = "";

      let i = 0;
      const showNextStatus = () => {
        if (i < statusUpdates.length) {
          appendStatus(statusUpdates[i]);
          i++;
          setTimeout(showNextStatus, 800);
        } else {
          memo = memo.replace(/(\n#+ .+)/g, "\n\n$1");

          const pdfWrapper = document.createElement("div");
          pdfWrapper.id = "pdf-container";
          pdfWrapper.style.pageBreakInside = "avoid";
          pdfWrapper.style.minHeight = "auto";
          pdfWrapper.style.padding = "20px";
          pdfWrapper.style.backgroundColor = "white";
          pdfWrapper.style.color = "#1f2937";
          pdfWrapper.style.whiteSpace = "pre-line";
          pdfWrapper.style.overflow = "visible";
          pdfWrapper.style.display = "block";
          pdfWrapper.style.width = "100%";

          pdfWrapper.innerHTML = marked.parse(memo);
          container.appendChild(pdfWrapper);

          appendStatus("Memo generation complete.");
          document.getElementById("downloadMemoBtn").disabled = false;
        }
      };

      showNextStatus();
    } catch (error) {
      if (attempt === 1) {
        appendStatus("Network error detected. Retrying...");
        setTimeout(() => tryFetch(2), 2000);
      } else {
        appendStatus("❌ Failed to generate memo due to network or server error. Please check your connection and try again.");
        console.error("Memo generation failed:", error);
      }
    }
  };

  tryFetch();
};

document.getElementById("downloadMemoBtn").onclick = () => {
  const pdfElement = document.getElementById("pdf-container");
  if (!pdfElement) {
    alert("Memo not ready.");
    return;
  }

  const newWindow = window.open("", "_blank");
  newWindow.document.write(`
    <html>
      <head>
        <title>Investment Memo</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 40px; color: #1f2937; background: white; }
          h2 { font-weight: bold; margin-top: 24px; }
          table { border-collapse: collapse; width: 100%; margin-top: 20px; }
          th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
        </style>
      </head>
      <body>${pdfElement.innerHTML}</body>
    </html>
  `);
  newWindow.document.close();

  newWindow.onload = () => {
    newWindow.print();
  };
};

