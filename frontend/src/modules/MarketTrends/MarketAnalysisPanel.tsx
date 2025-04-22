import { useState } from "react";
import Button from "@/components/Button";
import api from "@/services/api";

export default function MarketAnalysisPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [insight, setInsight] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) {
      setFile(e.target.files[0]);
      setInsight(null);
      setError(null);
    }
  };

  const analyzeFile = async () => {
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    setLoading(true);
    setError(null);
    setInsight(null);

    try {
      const res = await api.post("/market/analyze", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setInsight(res.data.insights);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to analyze market file.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 bg-white rounded-xl shadow border space-y-6">
      <h2 className="text-2xl font-bold text-blue-700">🤖 AI-Powered Market Analysis</h2>

      <input
        type="file"
        accept=".txt,.csv,.pdf"
        onChange={handleFileChange}
        className="block border rounded p-2"
      />

      <Button onClick={analyzeFile} loading={loading} disabled={!file}>
        Analyze
      </Button>

      {error && <p className="text-red-600">{error}</p>}

      {insight && (
        <div className="mt-4 p-4 bg-gray-50 border border-gray-300 rounded-md shadow-inner">
          <h3 className="font-semibold text-gray-700 mb-2">🧠 Insight Summary:</h3>
          <pre className="text-sm text-gray-800 whitespace-pre-wrap">{insight}</pre>
        </div>
      )}

      {!insight && !loading && file && (
        <p className="text-gray-500 italic">Click "Analyze" to get insights from the uploaded file.</p>
      )}
    </div>
  );
}
