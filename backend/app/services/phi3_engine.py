import os
from transformers import AutoTokenizer, AutoModelForCausalLM, TextStreamer
import torch

# Cargar modelo desde carpeta local
PHI3_PATH = os.getenv("PHI3_MODEL_PATH", "./models/phi-3-mini-4k-instruct")

tokenizer = AutoTokenizer.from_pretrained(PHI3_PATH, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(PHI3_PATH, torch_dtype=torch.float16, device_map="auto")
streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)


def query_phi3(prompt: str) -> str:
    """Procesa una consulta simple a Phi-3 y retorna la respuesta."""

    system_message = "You are a maritime AI assistant helping optimize fleet operations and business intelligence."

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]

    input_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([input_text], return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            streamer=streamer,
            max_new_tokens=512,
            temperature=0.5,
            do_sample=True,
            top_k=50,
            top_p=0.95
        )

    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
    response = decoded.split(system_message)[-1].strip()
    return response
