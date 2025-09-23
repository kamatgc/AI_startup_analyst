document.getElementById("downloadBtn").disabled = true;

document.getElementById("analyzeBtn").onclick = async () => {
  const file = document.getElementById("fileInput").files[0];
  if (!file) return;

  document.getElementById("status").innerText = "Uploading and analyzing...";
  document.getElementById("downloadBtn").disabled = true;

  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch("/analyze", { method: "POST", body: formData });
  const data = await res.json();

  const memo = data.memo || "No memo generated.";
  document.getElementById("memoContainer").innerHTML = marked.parse(memo);
  document.getElementById("status").innerText = "Done.";
  document.getElementById("downloadBtn").disabled = false;
};

document.getElementById("downloadBtn").onclick = () => {
  const element = document.getElementById("memoContainer");
  const opt = {
    margin: 0.5,
    filename: "investment_memo.pdf",
    html2canvas: { scale: 2, useCORS: true },
    jsPDF: { unit: "in", format: "letter", orientation: "portrait" }
  };
  html2pdf().set(opt).from(element).save();
};

