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

document.getElementById("analyzeBtn").onclick = () => {
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
  document.getElementById("memo-output").innerHTML = "";
  appendStatus("Uploading pitch deck...");
  document.getElementById("downloadMemoBtn").disabled = true;

  const formData = new FormData();
  formData.append("file", file);

  fetch("/analyze", {
    method: "POST",
    body: formData
  }).then(() => {
    const eventSource = new EventSource("/analyze");
    eventSource.onmessage = (event) => {
      if (event.data.startsWith("memo:")) {
        const memo = JSON.parse(event.data.slice(5));
        const container = document.getElementById("memo-output");
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
        eventSource.close();
      } else {
        appendStatus(event.data);
      }
    };
  }).catch((error) => {
    appendStatus("❌ Failed to start analysis. Please try again.");
    console.error("Streaming error:", error);
  });
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

