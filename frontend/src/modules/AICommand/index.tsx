import { useState, useRef, useEffect } from "react";
import Button from "@/components/Button";
import api from "@/services/api";

interface Message {
  id: number;
  sender: "user" | "ai";
  text: string;
}

export default function AICommand() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const chatRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now(),
      sender: "user",
      text: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const res = await api.post("/ai/ask", {
        prompt: userMessage.text,
      });

      const aiMessage: Message = {
        id: Date.now() + 1,
        sender: "ai",
        text: res.data.answer,
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (err: any) {
      const errorMessage: Message = {
        id: Date.now() + 2,
        sender: "ai",
        text: "⚠️ There was an error contacting the AI engine.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="p-6 bg-white rounded-xl shadow border h-full flex flex-col space-y-4">
      <h2 className="text-2xl font-bold text-blue-700">🧠 Maritime Copilot</h2>

      <div
        ref={chatRef}
        className="flex-1 overflow-y-auto border rounded-lg p-4 bg-gray-50 space-y-4"
      >
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`max-w-xl whitespace-pre-wrap ${
              msg.sender === "user" ? "ml-auto text-right" : "mr-auto text-left"
            }`}
          >
            <div
              className={`inline-block px-4 py-2 rounded-xl shadow ${
                msg.sender === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-200 text-gray-800"
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
        {loading && (
          <div className="text-gray-400 italic text-sm mt-2">DeepSeek is thinking...</div>
        )}
      </div>

      <div className="flex items-center space-x-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about voyages, TCE, emissions, market opportunities..."
          className="flex-1 p-3 border rounded-lg shadow-sm resize-none focus:ring focus:ring-blue-300"
          rows={2}
        />
        <Button onClick={sendMessage} loading={loading}>
          Send
        </Button>
      </div>
    </div>
  );
}
