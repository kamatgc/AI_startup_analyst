document.getElementById("downloadMemoBtn").disabled = true;

document.getElementById("analyzeBtn").onclick = async () => {
  const file = document.getElementById("fileInput").files[0];
  if (!file) {
    document.getElementById("status").innerText = "Please select a PDF file.";
    return;
  }

  if (!navigator.onLine) {
    document.getElementById("status").innerText = "⚠️ You appear to be offline. Please check your connection.";
    return;
  }

  document.getElementById("status").innerText = "Uploading and analyzing...";
  document.getElementById("downloadMemoBtn").disabled = true;

  const formData = new FormData();
  formData.append("file", file);

  const tryFetch = async (attempt = 1) => {
    try {
      const res = await fetch("/analyze", { method: "POST", body: formData });
      const data = await res.json();
      let memo = data.memo || "⚠️ No memo generated.";

      // Estimate time based on page count (roughly 8 sec per page)
      const pageCountMatch = memo.match(/## \d+\. /g);
      const estimatedTimeSec = Math.max(30, pageCountMatch ? pageCountMatch.length * 8 : 60);
      const estimatedMin = Math.floor(estimatedTimeSec / 60);
      const estimatedSec = estimatedTimeSec % 60;

      document.getElementById("status").innerText =
        `PDF uploaded.\nEstimated processing time: ${estimatedMin} min ${estimatedSec} sec.\nGenerating memo...`;

      memo = memo.replace(/(\n#+ .+)/g, "\n\n$1");

      const container = document.getElementById("memo-output");
      container.innerHTML = "";

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

      document.getElementById("status").innerText += "\nMemo generation complete.";
      document.getElementById("downloadMemoBtn").disabled = false;
    } catch (error) {
      if (attempt === 1) {
        document.getElementById("status").innerText = "Network error detected. Retrying...";
        setTimeout(() => tryFetch(2), 2000);
      } else {
        document.getElementById("status").innerText =
          "❌ Failed to generate memo due to network or server error. Please check your connection and try again.";
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

