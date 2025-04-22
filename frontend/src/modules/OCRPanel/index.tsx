import { useState } from "react";
import Button from "@/components/Button";
import Table from "@/components/Table";
import Modal from "@/components/Modal";
import api from "@/services/api";

export default function OCRPanel() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [extractedData, setExtractedData] = useState<Array<{ field: string; value: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const uploadAndAnalyze = async () => {
    if (!selectedFile) return;

    setLoading(true);
    setError(null);
    setExtractedData([]);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await api.post("/ocr/process", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setExtractedData(response.data.fields);
      setModalOpen(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to process document.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 bg-white rounded-xl shadow border space-y-6">
      <h2 className="text-2xl font-bold text-blue-700">🧾 OCR Document Analyzer</h2>

      <div className="space-y-2">
        <input
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          onChange={handleFileChange}
          className="block w-full border border-gray-300 rounded-lg p-2 bg-gray-50"
        />
        <div className="flex justify-between items-center">
          <p className="text-sm text-gray-500">
            Supported formats: PDF, JPG, PNG — max 5MB
          </p>
          <Button onClick={uploadAndAnalyze} disabled={!selectedFile} loading={loading}>
            Analyze Document
          </Button>
        </div>
        {error && <p className="text-red-600 font-medium">{error}</p>}
      </div>

      <Modal isOpen={modalOpen} title="Extracted Document Data" onClose={() => setModalOpen(false)} size="lg">
        <Table
          columns={["Field", "Value"]}
          data={extractedData.map((entry, index) => ({
            id: index,
            Field: entry.field,
            Value: entry.value,
          }))}
        />
        <div className="mt-6 text-right">
          <Button variant="primary" onClick={() => setModalOpen(false)}>
            Confirm & Close
          </Button>
        </div>
      </Modal>
    </div>
  );
}
