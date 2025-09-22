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
  document.getElementById("memoContainer").innerText = memo;
  document.getElementById("status").innerText = "Done.";
  document.getElementById("downloadBtn").disabled = false;

  const timestamp = new Date().toISOString();
  localStorage.setItem(`memo_${timestamp}`, memo);
  updateMemoHistory();
};

document.getElementById("downloadBtn").onclick = () => {
  const element = document.getElementById("memoContainer");
  const opt = {
    margin: 0.5,
    filename: "investment_memo.pdf",
    html2canvas: { scale: 2 },
    jsPDF: { unit: "in", format: "letter", orientation: "portrait" }
  };
  html2pdf().set(opt).from(element).save();
};

function updateMemoHistory() {
  const dropdown = document.getElementById("memoHistory");
  dropdown.innerHTML = "";
  Object.keys(localStorage).forEach((key) => {
    if (key.startsWith("memo_")) {
      const option = document.createElement("option");
      option.value = key;
      option.text = key.replace("memo_", "");
      dropdown.appendChild(option);
    }
  });

  dropdown.onchange = () => {
    const selected = dropdown.value;
    document.getElementById("memoContainer").innerText = localStorage.getItem(selected);
    document.getElementById("downloadBtn").disabled = false;
  };
}

updateMemoHistory();

