document.getElementById("downloadBtn").disabled = true;

document.getElementById("analyzeBtn").onclick = async () => {
  const file = document.getElementById("fileInput").files[0];
  if (!file) {
    document.getElementById("status").innerText = "Please select a PDF file.";
    return;
  }

  document.getElementById("status").innerText = "Uploading and analyzing...";
  document.getElementById("downloadBtn").disabled = true;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/analyze", { method: "POST", body: formData });
    const data = await res.json();
    let memo = data.memo || "⚠️ No memo generated.";

    // Add spacing before Markdown headings
    memo = memo.replace(/(\n#+ .+)/g, "\n\n$1");

    // Render Markdown to HTML inside a dedicated container
    const container = document.getElementById("memo-output");
    container.innerHTML = `<div id="pdf-container">${marked.parse(memo)}</div>`;
    document.getElementById("status").innerText = "Done.";
    document.getElementById("downloadBtn").disabled = false;
  } catch (error) {
    document.getElementById("status").innerText = "Error generating memo.";
    console.error("Memo generation failed:", error);
  }
};

document.getElementById("downloadBtn").onclick = () => {
  const pdfElement = document.getElementById("pdf-container");
  if (!pdfElement) {
    alert("PDF content not ready.");
    return;
  }

  // Scroll into view to ensure visibility
  pdfElement.scrollIntoView({ behavior: "instant", block: "center" });

  const opt = {
    margin: 0.5,
    filename: "investment_memo.pdf",
    html2canvas: { scale: 2, useCORS: true },
    jsPDF: { unit: "in", format: "letter", orientation: "portrait" }
  };

  // Delay to ensure DOM is fully painted
  setTimeout(() => {
    html2pdf().set(opt).from(pdfElement).save();
  }, 800);
};

