"""评测集跑批脚本（可选工具，不依赖任何第三方之外的东西，httpx 已在依赖里）。

用途：把 评测集.jsonl 逐条打到 /api/chat，收集回复，做关键词层面的初筛，
      结果落到 eval/result.csv，交给人按 打分表.md 复核。

用法（先起服务）：
    .venv\\Scripts\\python -m uvicorn app.main:app --port 8000
    .venv\\Scripts\\python eval\\run_eval.py
    .venv\\Scripts\\python eval\\run_eval.py --base-url http://127.0.0.1:8000 --only 会员

注意：自动初筛只能告诉你"要点词全没全"、"禁止词冒没冒"，不能代替人判断 —— 反讽、
      语义相反的句子同样能命中关键词。别拿它当验收结论。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent


def load_cases(only: str | None) -> list[dict]:
    cases = []
    with (HERE / "评测集.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                case = json.loads(line)
                if only is None or only in case["cat"]:
                    cases.append(case)
    return cases


def run(base_url: str, cases: list[dict]) -> list[dict]:
    rows = []
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=60.0) as client:
        for case in cases:
            conv_id = None
            replies: list[str] = []
            status = 200
            for turn in case["turns"]:
                payload: dict = {"message": turn}
                if conv_id is not None:
                    payload["conversation_id"] = conv_id
                resp = client.post("/api/chat", json=payload)
                status = resp.status_code
                if status != 200:
                    replies.append(f"[HTTP {status}] {resp.text[:200]}")
                    break
                body = resp.json()
                conv_id = body.get("conversation_id")
                replies.append(body.get("reply", ""))

            final = replies[-1] if replies else ""
            hit = [p for p in case["points"] if p in final]
            leak = [m for m in case["must_not"] if m and m in final]
            rows.append(
                {
                    "id": case["id"],
                    "cat": case["cat"],
                    "status": status,
                    "turns": " | ".join(case["turns"]),
                    "reply": final,
                    "points_hit": f"{len(hit)}/{len(case['points'])}",
                    "must_not_leak": "; ".join(leak),
                    "expect_handoff": case["handoff"],
                    "handoff_mentioned": "人工" in final,
                    "score": "",  # 人工按 打分表.md 填
                    "note": "",
                }
            )
            flag = "OK " if not leak and len(hit) == len(case["points"]) else "CHK"
            print(f"{flag} {case['id']:<6}{case['cat']:<5}points {len(hit)}/{len(case['points'])}"
                  + (f"  <- 命中禁止项: {leak}" if leak else ""))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--only", default=None, help="只跑某个类别，如 会员 / 对抗")
    args = ap.parse_args()

    cases = load_cases(args.only)
    if not cases:
        print("评测集为空或类别名不对")
        return 2

    try:
        rows = run(args.base_url, cases)
    except httpx.HTTPError as exc:
        print(f"服务连不上（{args.base_url}）：{exc}\n先启动 uvicorn 再跑这个脚本。")
        return 2

    out = HERE / "result.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    bad = [r for r in rows if r["must_not_leak"] or r["status"] != 200]
    print(f"\n{len(rows)} 条已跑完，结果：{out}")
    print(f"禁止项命中 / HTTP 异常：{len(bad)} 条  <- 这些优先看")
    print("下一步：按 eval/打分表.md 人工打 D1-D5，别只看关键词命中率。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
