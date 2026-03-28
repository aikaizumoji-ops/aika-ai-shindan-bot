import os
import hashlib
import hmac
import base64
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
import urllib.request

CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_API = "https://api.line.me/v2/bot/message/reply"

# ─── 診断データ ────────────────────────────────────────────────
QUESTIONS = [
    {
        "text": "Q1 / 7\n\nAIツール（ChatGPT・Claudeなど）を\n使ったことはありますか？",
        "choices": [
            {"label": "毎日のように使っている", "score": 3},
            {"label": "週に数回使う", "score": 2},
            {"label": "たまに使う程度", "score": 1},
            {"label": "ほとんど使わない", "score": 0},
        ],
    },
    {
        "text": "Q2 / 7\n\n使っているAIツールはどれに近いですか？",
        "choices": [
            {"label": "複数ツールを使い分けている", "score": 3},
            {"label": "ChatGPT有料版を使っている", "score": 2},
            {"label": "無料版のみ使っている", "score": 1},
            {"label": "まだ使ったことがない", "score": 0},
        ],
    },
    {
        "text": "Q3 / 7\n\nAIを仕事・ビジネスに活用していますか？",
        "choices": [
            {"label": "メイン業務に組み込んでいる", "score": 3},
            {"label": "補助的に活用している", "score": 2},
            {"label": "試したことはある", "score": 1},
            {"label": "プライベートのみ／未使用", "score": 0},
        ],
    },
    {
        "text": "Q4 / 7\n\nAIプロンプトを自分でカスタマイズできますか？",
        "choices": [
            {"label": "目的に合わせて自在に書ける", "score": 3},
            {"label": "テンプレを参考に調整できる", "score": 2},
            {"label": "コピペで使っている", "score": 1},
            {"label": "プロンプトって何…？", "score": 0},
        ],
    },
    {
        "text": "Q5 / 7\n\nAIを使って業務を効率化・自動化できていますか？",
        "choices": [
            {"label": "複数の業務を自動化できた", "score": 3},
            {"label": "1〜2つの業務で活用中", "score": 2},
            {"label": "やってみたいけどまだ", "score": 1},
            {"label": "自動化は考えていない", "score": 0},
        ],
    },
    {
        "text": "Q6 / 7\n\nAIの最新情報をキャッチアップしていますか？",
        "choices": [
            {"label": "週1以上チェックしている", "score": 2},
            {"label": "気になったときに調べる", "score": 1},
            {"label": "あまり追っていない", "score": 0},
        ],
    },
    {
        "text": "Q7 / 7（最後の質問です！）\n\nAIをビジネスの収益につなげていますか？",
        "choices": [
            {"label": "すでに収益化できている", "score": 3},
            {"label": "収益化に向けて動いている", "score": 2},
            {"label": "興味はあるけどまだ", "score": 1},
            {"label": "収益化は考えていない", "score": 0},
        ],
    },
]

LEVELS = [
    {
        "min": 0, "max": 4,
        "badge": "LEVEL 1", "emoji": "🌱", "title": "AI入門者", "color": "#FF6B6B",
        "summary": "AIとの出会いはこれから！まずは基礎から一緒に学んでいきましょう🎓",
        "advice": "ChatGPTの無料版に登録して、まず「挨拶」だけしてみてください。それが最初の一歩！",
        "potential": "月10〜20時間の時間削減が期待できます",
        "cta": "✨ 無料相談でAI活用を始めよう",
    },
    {
        "min": 5, "max": 9,
        "badge": "LEVEL 2", "emoji": "🔥", "title": "AI見習い", "color": "#FFA94D",
        "summary": "使い始めてはいるけど、まだ「なんとなく」の段階ですね！",
        "advice": "プロンプトの型を覚えるだけで出力品質が劇的にアップ！「役割設定＋指示」の書き方を学びましょう。",
        "potential": "正しく使えば月20〜30時間削減が見えてきます",
        "cta": "🚀 無料相談でAI活用を加速させよう",
    },
    {
        "min": 10, "max": 14,
        "badge": "LEVEL 3", "emoji": "⚡", "title": "AI活用中級者", "color": "#51CF66",
        "summary": "かなり使いこなしてきてる！あとは「仕組み化」が次のステップです💪",
        "advice": "複数ツールを連携させる「AI業務フロー」を設計しましょう。時間が一気に生まれます。",
        "potential": "フロー構築で月30〜50時間削減＋収益アップのチャンスがあります",
        "cta": "💡 無料相談でAI仕組み化を設計しよう",
    },
    {
        "min": 15, "max": 99,
        "badge": "LEVEL 4", "emoji": "👑", "title": "AIマスター", "color": "#339AF0",
        "summary": "すごい！AIをビジネスレベルで使いこなしていますね✨",
        "advice": "あなたのAI活用ノウハウを商品化・コンテンツ化することで、さらに大きな収益が生まれます。",
        "potential": "ノウハウのパッケージ化でスケールアップ。収益倍増も現実的です",
        "cta": "🌟 無料相談で次のステージを目指そう",
    },
]

def get_level(score):
    for lv in LEVELS:
        if lv["min"] <= score <= lv["max"]:
            return lv
    return LEVELS[0]

# ─── セッション（メモリ）──────────────────────────────────────
sessions = {}  # {user_id: {"step": int, "score": int}}

def get_session(user_id):
    if user_id not in sessions:
        sessions[user_id] = {"step": 0, "score": 0}
    return sessions[user_id]

def reset_session(user_id):
    sessions[user_id] = {"step": 0, "score": 0}

# ─── LINE API ─────────────────────────────────────────────────
def reply(reply_token, messages):
    if not isinstance(messages, list):
        messages = [messages]
    body = json.dumps({"replyToken": reply_token, "messages": messages}).encode("utf-8")
    req = urllib.request.Request(
        LINE_API,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        },
        method="POST",
    )
    try:
        res = urllib.request.urlopen(req)
        print(f"[REPLY OK] status={res.status}", flush=True)
    except Exception as e:
        print(f"[REPLY ERROR] {e}", flush=True)

def make_question_msg(q):
    items = [
        {
            "type": "action",
            "action": {
                "type": "postback",
                "label": c["label"],
                "data": f"score={c['score']}",
                "displayText": c["label"],
            },
        }
        for c in q["choices"]
    ]
    return {"type": "text", "text": q["text"], "quickReply": {"items": items}}

def make_result_flex(score, lv):
    max_score = 17
    pct = round((score / max_score) * 100)
    return {
        "type": "flex",
        "altText": f"診断結果：{lv['badge']} {lv['title']}（{score}/{max_score}点）",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [{"type": "text", "text": lv["badge"], "size": "xs", "weight": "bold", "color": "#ffffff", "align": "center"}],
                        "backgroundColor": lv["color"],
                        "paddingAll": "6px",
                        "cornerRadius": "20px",
                        "width": "80px",
                    },
                    {"type": "text", "text": lv["emoji"], "size": "xxl", "align": "center", "margin": "md"},
                    {"type": "text", "text": lv["title"], "weight": "bold", "size": "xl", "align": "center", "margin": "sm"},
                    {"type": "text", "text": lv["summary"], "size": "sm", "color": "#555555", "align": "center", "wrap": True, "margin": "sm"},
                ],
                "paddingAll": "20px",
                "backgroundColor": "#f8f8f8",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "AI活用スコア", "size": "xs", "color": "#888888"},
                                    {"type": "text", "text": f"{score} / {max_score}点", "size": "xs", "color": "#333333", "weight": "bold", "align": "end"},
                                ],
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "box", "layout": "vertical", "contents": [], "backgroundColor": lv["color"], "height": "10px", "cornerRadius": "5px", "flex": pct},
                                    {"type": "box", "layout": "vertical", "contents": [], "flex": max(1, 100 - pct)},
                                ],
                                "backgroundColor": "#eeeeee",
                                "height": "10px",
                                "cornerRadius": "5px",
                                "margin": "sm",
                            },
                        ],
                        "margin": "md",
                    },
                    {"type": "separator", "margin": "lg"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "🎯", "size": "sm"},
                                    {"type": "text", "text": "今すぐできること", "size": "sm", "weight": "bold", "color": "#333333", "margin": "sm"},
                                ],
                                "alignItems": "center",
                            },
                            {"type": "text", "text": lv["advice"], "size": "sm", "color": "#555555", "wrap": True, "margin": "sm"},
                        ],
                        "margin": "lg",
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "⚡", "size": "sm"},
                                    {"type": "text", "text": "AI化で期待できる変化", "size": "sm", "weight": "bold", "color": "#333333", "margin": "sm"},
                                ],
                                "alignItems": "center",
                            },
                            {"type": "text", "text": lv["potential"], "size": "sm", "color": "#555555", "wrap": True, "margin": "sm"},
                        ],
                        "margin": "lg",
                        "backgroundColor": "#f0fff4",
                        "cornerRadius": "10px",
                        "paddingAll": "12px",
                    },
                ],
                "paddingAll": "20px",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {"type": "uri", "label": lv["cta"], "uri": "https://lin.ee/XuKb1sK"},
                        "style": "primary",
                        "color": "#06C755",
                        "height": "sm",
                    },
                    {"type": "text", "text": "※ 無料個別相談はLINEで受け付けています", "size": "xxs", "color": "#aaaaaa", "align": "center", "margin": "sm"},
                ],
                "paddingAll": "16px",
            },
        },
    }

# ─── イベント処理 ─────────────────────────────────────────────
def handle_event(event):
    user_id = event.get("source", {}).get("userId", "")
    reply_token = event.get("replyToken", "")
    event_type = event.get("type", "")

    if event_type == "message" and event.get("message", {}).get("type") == "text":
        text = event["message"]["text"].strip()
        session = get_session(user_id)

        if text in ["診断", "AI診断", "スタート", "診断スタート"]:
            reset_session(user_id)
            session = get_session(user_id)
            reply(reply_token, [
                {"type": "text", "text": "こんにちは！🤖\nあいかのAI活用レベル診断Botです✨\n\n7つの質問であなたのAI活用レベルを診断します！\nすべてタップで答えられるので、2〜3分で完了します😊\n\nでは早速はじめましょう！"},
                make_question_msg(QUESTIONS[0]),
            ])
            session["step"] = 1
        else:
            if session["step"] == 0:
                reply(reply_token, {"type": "text", "text": "「診断スタート」と送ると\n無料AI活用レベル診断ができます！🤖\n\nぜひ試してみてください✨"})

    elif event_type == "postback":
        session = get_session(user_id)
        data = parse_qs(event["postback"]["data"])
        score = int(data.get("score", ["0"])[0])
        session["score"] += score
        next_step = session["step"]

        if next_step < len(QUESTIONS):
            reply(reply_token, make_question_msg(QUESTIONS[next_step]))
            session["step"] += 1
        else:
            lv = get_level(session["score"])
            reply(reply_token, [
                {"type": "text", "text": f"診断完了です！🎉\nあなたのスコアは {session['score']}/17点でした！\n\n結果をお届けします👇"},
                make_result_flex(session["score"], lv),
            ])
            reset_session(user_id)

# ─── HTTP サーバー ────────────────────────────────────────────
def verify_signature(body, signature):
    hash_ = hmac.new(CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(hash_).decode("utf-8") == signature

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default logs

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"AI Bot running OK")

    def do_POST(self):
        print(f"[POST] path={self.path}", flush=True)
        if self.path not in ("/webhook", "/callback"):
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        signature = self.headers.get("X-Line-Signature", "")
        print(f"[SIG] len={len(body)} sig={signature[:20]}...", flush=True)

        if not verify_signature(body, signature):
            print(f"[403] signature mismatch", flush=True)
            self.send_response(403)
            self.end_headers()
            return

        try:
            data = json.loads(body.decode("utf-8"))
            events = data.get("events", [])
            print(f"[EVENTS] count={len(events)}", flush=True)
            for event in events:
                print(f"[EVENT] type={event.get('type')} userId={event.get('source',{}).get('userId','?')[:8]}", flush=True)
                handle_event(event)
        except Exception as e:
            print(f"[ERROR] {e}", flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"✅ Server running on port {port}")
    server.serve_forever()
