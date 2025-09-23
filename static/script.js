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
    const memo = data.memo || "⚠️ No memo generated.";

