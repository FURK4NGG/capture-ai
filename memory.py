import json
import re
import math
import hashlib
from pathlib import Path
from collections import Counter


def normalize_chat_data(raw):
    if isinstance(raw, list):
        return {
            "summary": "",
            "messages": raw,
            "code_context": {},
            "memory_chunks": []
        }

    if not isinstance(raw, dict):
        raw = {}

    raw.setdefault("summary", "")
    raw.setdefault("messages", [])
    raw.setdefault("code_context", {})
    raw.setdefault("memory_chunks", [])

    return raw


def load_chat_data(chat_file: Path) -> dict:
    try:
        raw = json.loads(chat_file.read_text(encoding="utf-8")) or []
    except Exception:
        raw = []

    return normalize_chat_data(raw)


def save_chat_data(chat_file: Path, chat_data: dict):
    chat_file.write_text(
        json.dumps(chat_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def get_chat_messages(chat_data: dict) -> list:
    return chat_data.get("messages", [])


def add_memory_chunk(chat_data: dict, text: str, source: str = "chat"):
    text = str(text or "").strip()
    if not text:
        return

    cid = hashlib.sha256((source + text).encode("utf-8")).hexdigest()[:16]

    for item in chat_data.get("memory_chunks", []):
        if item.get("id") == cid:
            return

    chat_data.setdefault("memory_chunks", []).append({
        "id": cid,
        "source": source,
        "text": text[:4000]
    })


def tokenize(text: str):
    return re.findall(r"\w+", str(text).lower())


def cosine_similarity(a: str, b: str) -> float:
    va = Counter(tokenize(a))
    vb = Counter(tokenize(b))

    if not va or not vb:
        return 0.0

    common = set(va) & set(vb)
    dot = sum(va[w] * vb[w] for w in common)

    na = math.sqrt(sum(v * v for v in va.values()))
    nb = math.sqrt(sum(v * v for v in vb.values()))

    if na == 0 or nb == 0:
        return 0.0

    return dot / (na * nb)


def retrieve_relevant_chunks(chat_data: dict, query: str, limit: int = 5) -> list:
    scored = []

    for chunk in chat_data.get("memory_chunks", []):
        text = chunk.get("text", "")
        score = cosine_similarity(query, text)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for score, chunk in scored[:limit]]


def summarize_code_basic(file_path: Path) -> dict:
    try:
        code = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}

    classes = []
    functions = []

    for line in code.splitlines():
        s = line.strip()
        if s.startswith("class "):
            classes.append(s)
        elif s.startswith("def "):
            functions.append(s)

    return {
        "path": str(file_path),
        "name": file_path.name,
        "summary": f"{file_path.name}: {len(classes)} class, {len(functions)} function bulundu.",
        "classes": classes[:30],
        "functions": functions[:80]
    }


def update_code_context_from_message(chat_data: dict, msg: dict):
    files = msg.get("files") or []
    if not isinstance(files, list):
        return

    for f in files:
        if not isinstance(f, dict):
            continue

        p_raw = str(f.get("path") or "").strip()
        if not p_raw:
            continue

        p = Path(p_raw)
        if not p.exists() or not p.is_file():
            continue

        if p.suffix.lower() not in {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".html",
            ".css", ".cpp", ".c", ".h", ".hpp", ".java", ".go",
            ".rs", ".sh", ".md", ".txt", ".yaml", ".yml"
        }:
            continue

        ctx = summarize_code_basic(p)
        if not ctx:
            continue

        chat_data.setdefault("code_context", {})[str(p)] = ctx

        add_memory_chunk(
            chat_data,
            ctx["summary"] + "\nFunctions:\n" + "\n".join(ctx.get("functions", [])[:30]),
            source=f"code:{p.name}"
        )


def build_memory_context(chat_data: dict, user_message: str) -> str:
    parts = []

    summary = str(chat_data.get("summary") or "").strip()
    if summary:
        parts.append("Conversation summary:\n" + summary)

    relevant = retrieve_relevant_chunks(chat_data, user_message, limit=5)
    if relevant:
        txt = "Relevant old context:\n"
        for ch in relevant:
            txt += f"- [{ch.get('source')}] {ch.get('text')}\n"
        parts.append(txt)

    code_context = chat_data.get("code_context") or {}
    if isinstance(code_context, dict) and code_context:
        txt = "Known code context:\n"
        for path, ctx in code_context.items():
            txt += f"\nFile: {ctx.get('name') or path}\n"
            txt += f"{ctx.get('summary', '')}\n"

            funcs = ctx.get("functions") or []
            if funcs:
                txt += "Functions:\n" + "\n".join(funcs[:30]) + "\n"

            classes = ctx.get("classes") or []
            if classes:
                txt += "Classes:\n" + "\n".join(classes[:20]) + "\n"

        parts.append(txt)

    return "\n\n".join(parts).strip()


def should_update_summary(chat_data: dict, every: int = 20) -> bool:
    messages = chat_data.get("messages", [])
    real = [m for m in messages if isinstance(m, dict) and m.get("role") in ("user", "bot", "assistant")]
    return len(real) > 0 and len(real) % every == 0

def make_simple_summary(chat_data: dict) -> str:
    messages = chat_data.get("messages", [])

    real_messages = [
        m for m in messages
        if isinstance(m, dict) and m.get("role") in ("user", "bot", "assistant")
    ]

    last_items = real_messages[-20:]

    parts = []

    for m in last_items:
        role = str(m.get("role") or "").strip()
        text = str(m.get("content") or "").strip()

        if not text:
            continue

        text = text.replace("\n", " ")
        if len(text) > 300:
            text = text[:300] + "..."

        parts.append(f"{role}: {text}")

    code_context = chat_data.get("code_context") or {}
    known_files = []

    if isinstance(code_context, dict):
        for _path, ctx in code_context.items():
            if not isinstance(ctx, dict):
                continue

            name = str(ctx.get("name") or "").strip()
            summary = str(ctx.get("summary") or "").strip()

            if name:
                known_files.append(name)

            if summary:
                parts.append(f"code_context: {summary}")

    summary = "Recent conversation summary:\n"
    summary += "\n".join(parts)

    if known_files:
        summary += "\n\nKnown code files: " + ", ".join(known_files)

    return summary[:6000]
