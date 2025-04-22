import { useState } from "react";
import api from "@/services/api";
import Button from "@/components/Button";

export default function ReportUploader() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setFile(e.target.files[0]);
      setResult(null);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await api.post("/ocr/analyze", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(res.data.text);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to analyze document.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 bg-white rounded-xl shadow border space-y-6">
      <h2 className="text-2xl font-bold text-blue-700">📂 Upload & Analyze Documents</h2>

      <div className="flex items-center space-x-4">
        <input
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          onChange={handleFileChange}
          className="file-input border rounded-lg p-2"
        />
        <Button onClick={handleUpload} loading={loading} disabled={!file}>
          Analyze with OCR
        </Button>
      </div>

      {error && <div className="text-red-600">{error}</div>}

      {result && (
        <div className="mt-4 p-4 bg-gray-50 border rounded-lg whitespace-pre-wrap text-sm text-gray-700">
          <strong>🧠 OCR Output:</strong>
          <br />
          {result}
        </div>
      )}
    </div>
  );
}
